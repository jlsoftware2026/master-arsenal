"""Market-data validation; missing data is never silently repaired."""
from __future__ import annotations
from .models import Candle, ValidationIssue

_FIXED_INTERVALS = {
    "1s": 1000, "1m": 60000, "3m": 180000, "5m": 300000,
    "15m": 900000, "30m": 1800000, "1h": 3600000, "2h": 7200000,
    "4h": 14400000, "6h": 21600000, "8h": 28800000, "12h": 43200000,
    "1d": 86400000, "3d": 259200000, "1w": 604800000,
}

def interval_milliseconds(interval: str) -> int | None:
    return _FIXED_INTERVALS.get(interval)

def validate_candles(candles, expected_interval: str | None = None) -> list[ValidationIssue]:
    rows = list(candles)
    issues: list[ValidationIssue] = []
    cadence = interval_milliseconds(expected_interval) if expected_interval else None
    previous = None
    for index, c in enumerate(rows):
        if c.open_time.tzinfo is None or c.close_time.tzinfo is None:
            issues.append(ValidationIssue("naive_timestamp", "Timestamps must be timezone-aware UTC.", "error", index))
        elif c.open_time.utcoffset().total_seconds() != 0 or c.close_time.utcoffset().total_seconds() != 0:
            issues.append(ValidationIssue("non_utc_timestamp", "Timestamps must be normalized to UTC.", "error", index))
        if c.close_time < c.open_time:
            issues.append(ValidationIssue("invalid_time_range", "Close time precedes open time.", "error", index))
        elif cadence:
            duration = int((c.close_time - c.open_time).total_seconds() * 1000) + 1
            if duration != cadence:
                issues.append(ValidationIssue("invalid_candle_duration", f"Candle duration does not match {expected_interval}.", "error", index))
        if any(x <= 0 for x in (c.open, c.high, c.low, c.close)):
            issues.append(ValidationIssue("non_positive_price", "OHLC prices must be positive.", "error", index))
        if c.high < max(c.open, c.close, c.low):
            issues.append(ValidationIssue("invalid_high", "High must be >= open, close, and low.", "error", index))
        if c.low > min(c.open, c.close, c.high):
            issues.append(ValidationIssue("invalid_low", "Low must be <= open, close, and high.", "error", index))
        if c.volume < 0 or (c.quote_volume is not None and c.quote_volume < 0):
            issues.append(ValidationIssue("negative_volume", "Volume cannot be negative.", "error", index))
        if previous is not None:
            delta = int((c.open_time - previous.open_time).total_seconds() * 1000)
            if delta <= 0:
                issues.append(ValidationIssue("non_increasing_time", "Candles must be strictly ordered and unique.", "error", index))
            elif cadence and delta > cadence:
                issues.append(ValidationIssue("cadence_gap", f"Approximately {max(1, delta // cadence - 1)} missing {expected_interval} candle(s).", "warning", index))
            elif cadence and delta < cadence:
                issues.append(ValidationIssue("unexpected_cadence", f"Spacing is shorter than {expected_interval}.", "warning", index))
        previous = c
    return issues

def require_valid_candles(candles, expected_interval: str | None = None) -> list[Candle]:
    rows = list(candles)
    errors = [x for x in validate_candles(rows, expected_interval) if x.severity == "error"]
    if errors:
        raise ValueError("Invalid candle data: " + "; ".join(x.message for x in errors))
    return rows
