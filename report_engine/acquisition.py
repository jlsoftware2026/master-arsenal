"""UTC-day intraday evidence acquisition for Binance public market data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.engine import CORE_SYMBOLS, analyze_candles
from binance_data_engine.validation import interval_milliseconds, validate_candles
from .intraday import build_intraday_snapshot_pdf


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field} must be a timezone-aware UTC datetime")
    return value.astimezone(timezone.utc)


def acquire_intraday_evidence(
    client: BinancePublicClient,
    cutoff_utc: datetime,
    interval: str = "1h",
    market: str = "spot",
    symbols: tuple[str, ...] = CORE_SYMBOLS,
) -> dict[str, Any]:
    """Acquire only completed candles in [00:00 UTC, cutoff), preserving gaps.

    Missing candles are disclosed in validation metadata; they are never filled or
    interpolated. The report is marked incomplete whenever expected candles are absent.
    """
    cutoff = _utc(cutoff_utc, "cutoff_utc")
    start = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    cadence = interval_milliseconds(interval)
    if cadence is None:
        raise ValueError(f"Unsupported fixed-duration interval: {interval}")
    if market not in {"spot", "usdm"}:
        raise ValueError("market must be 'spot' or 'usdm'")
    requested = tuple(symbol.upper() for symbol in symbols)
    missing_core = [symbol for symbol in CORE_SYMBOLS if symbol not in requested]
    if missing_core:
        raise ValueError("Core symbols are mandatory: " + ", ".join(missing_core))
    if len(set(requested)) != len(requested):
        raise ValueError("symbols must be unique")

    server_time = client.get_server_time(market)
    if cutoff > server_time:
        raise ValueError("cutoff_utc is later than Binance server time")

    # Only candles whose inclusive close timestamp is strictly before cutoff are
    # eligible. A candle still forming at cutoff is excluded.
    expected_opens = []
    cursor = start
    while cursor + timedelta(milliseconds=cadence) <= cutoff:
        expected_opens.append(cursor)
        cursor += timedelta(milliseconds=cadence)

    symbols_data: dict[str, Any] = {}
    all_complete = True
    for symbol in requested:
        candles, pagination = client.get_historical_klines(
            symbol, interval, start, cutoff, market=market
        )
        eligible = [c for c in candles if c.open_time >= start and c.close_time < cutoff]
        eligible.sort(key=lambda candle: candle.open_time)
        issues = [issue.to_dict() for issue in validate_candles(eligible, interval)]
        actual_opens = {c.open_time for c in eligible}
        missing_opens = [opened for opened in expected_opens if opened not in actual_opens]
        if missing_opens:
            issues.append({
                "code": "missing_candles",
                "severity": "error",
                "message": f"{len(missing_opens)} expected completed {interval} candle(s) are missing.",
                "missing_open_times_utc": [
                    value.isoformat().replace("+00:00", "Z") for value in missing_opens
                ],
            })
        if not pagination.complete:
            issues.append({
                "code": "pagination_incomplete",
                "severity": "error",
                "message": "Binance pagination did not confirm the requested time range.",
            })
        if any(issue.get("severity") == "error" for issue in issues) or not pagination.complete:
            all_complete = False

        candle_metadata = dict(client.last_response_metadata)
        ticker = None
        ticker_error = None
        try:
            ticker = client.get_24h_ticker(symbol, market)
        except Exception as exc:
            ticker_error = f"{type(exc).__name__}: {exc}"

        symbols_data[symbol] = {
            "candles": [candle.to_dict() for candle in eligible],
            "candle_count": len(eligible),
            "expected_candle_count": len(expected_opens),
            "first_open_time_utc": (
                eligible[0].open_time.isoformat().replace("+00:00", "Z") if eligible else None
            ),
            "last_close_time_utc": (
                eligible[-1].close_time.isoformat().replace("+00:00", "Z") if eligible else None
            ),
            "ticker_24h": ticker if ticker is not None else {
                "status": "unavailable", "error": ticker_error
            },
            "indicators": analyze_candles(eligible),
            "validation": issues,
            "response_metadata": {
                "candles": candle_metadata,
                "pagination": pagination.to_dict(),
            },
        }

    generated = datetime.now(timezone.utc)
    if generated < cutoff:
        raise ValueError("Local system clock is behind cutoff_utc; refusing to misstate generation time")
    return {
        "window_start_utc": start.isoformat().replace("+00:00", "Z"),
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
        "source": "Binance public REST API",
        "market": market,
        "interval": interval,
        "data_status": "complete" if all_complete else "incomplete",
        "executive_summary": (
            "All expected completed candles passed acquisition checks."
            if all_complete else
            "One or more symbols have missing, invalid, or incompletely paginated data. "
            "This report must be treated as incomplete."
        ),
        "symbols": symbols_data,
        "provenance": [{
            "source": "Binance public REST API",
            "retrieved_at_utc": generated.isoformat().replace("+00:00", "Z"),
            "note": f"Market={market}; interval={interval}; server_time_utc="
                   f"{server_time.isoformat().replace('+00:00', 'Z')}",
        }],
    }


def generate_intraday_snapshot_pdf(
    client: BinancePublicClient,
    cutoff_utc: datetime,
    output_directory: Path | str,
    interval: str = "1h",
    market: str = "spot",
) -> Path:
    """Acquire, validate, and render a UTC intraday snapshot PDF."""
    evidence = acquire_intraday_evidence(
        client, cutoff_utc=cutoff_utc, interval=interval, market=market
    )
    return build_intraday_snapshot_pdf(evidence, output_directory)
