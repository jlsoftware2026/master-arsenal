"""Strict acquisition for completed 24-hour UTC market sessions."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from .client import BinancePublicClient
from .engine import CORE_SYMBOLS, analyze_candles, acquire_derivatives_context
from .intraday import _validate_series
from .validation import interval_milliseconds, validate_candles


def acquire_completed_market_day(
    client: BinancePublicClient,
    session_date: date | None = None,
    interval: str = "1h",
    market: str = "spot",
    symbols: tuple[str, ...] | list[str] = CORE_SYMBOLS,
    indicator_lookback: int = 250,
) -> dict[str, Any]:
    """Acquire a complete UTC calendar day and separate pre-session indicator history."""
    if interval_milliseconds(interval) is None or interval_milliseconds(interval) < 60_000 or interval in {"1d", "3d", "1w"}:
        raise ValueError(f"Unsupported report interval (minimum 1m): {interval!r}")
    interval_ms = interval_milliseconds(interval)
    if 86_400_000 % interval_ms:
        raise ValueError("The selected interval must divide a 24-hour UTC day exactly")
    if isinstance(indicator_lookback, bool) or not isinstance(indicator_lookback, int) or indicator_lookback < 200:
        raise ValueError("indicator_lookback must be an integer of at least 200 candles")
    if market not in {"spot", "usdm"}:
        raise ValueError("market must be 'spot' or 'usdm'")

    server_time = client.get_server_time(market)
    if server_time.tzinfo is None or server_time.utcoffset() != timedelta(0):
        raise ValueError("Binance server time must be timezone-aware UTC")
    server_time = server_time.astimezone(timezone.utc)
    target_date = session_date or (server_time.date() - timedelta(days=1))
    if not isinstance(target_date, date) or isinstance(target_date, datetime):
        raise ValueError("session_date must be a datetime.date")
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    if end > server_time:
        raise ValueError("The requested UTC market day is not yet complete according to Binance server time")

    requested = tuple(str(symbol).upper() for symbol in symbols)
    missing = [symbol for symbol in CORE_SYMBOLS if symbol not in requested]
    if missing:
        raise ValueError("Mandatory core symbols missing: " + ", ".join(missing))
    if len(set(requested)) != len(requested):
        raise ValueError("symbols must be unique")

    per_day = 86_400_000 // interval_ms
    history_start = start - timedelta(milliseconds=indicator_lookback * interval_ms)
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "source": "Binance public REST API",
        "market": market,
        "interval": interval,
        "session_start_utc": start.isoformat().replace("+00:00", "Z"),
        "session_end_utc": end.isoformat().replace("+00:00", "Z"),
        "binance_server_time_utc": server_time.isoformat().replace("+00:00", "Z"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data_status": "complete",
        "indicator_methodology": {
            "lookback_candles": indicator_lookback,
            "report_window_excludes_lookback": True,
        },
        "read_only": True,
        "symbols": {},
    }
    for symbol in requested:
        history, history_page = client.get_historical_klines(
            symbol, interval, history_start, start, market=market
        )
        if not history_page.complete:
            raise ValueError(f"{symbol}: indicator-history pagination did not complete")
        if history_page.returned != len(history):
            raise ValueError(f"{symbol}: indicator-history pagination metadata count mismatch")
        _validate_series(history, symbol, interval, history_start, start,
                         indicator_lookback, "indicator-history")
        history_metadata = dict(client.last_response_metadata)

        candles, page = client.get_historical_klines(
            symbol, interval, start, end, market=market
        )
        candle_metadata = dict(client.last_response_metadata)
        if not page.complete:
            raise ValueError(f"{symbol}: session pagination did not complete")
        if page.returned != len(candles):
            raise ValueError(f"{symbol}: session pagination metadata count mismatch")
        _validate_series(candles, symbol, interval, start, end, per_day, "session")
        validation = validate_candles(candles, interval)
        opening = candles[0].open
        closing = candles[-1].close
        change_pct = ((closing - opening) / opening * Decimal("100")) if opening else None
        item = {
            "candles": [candle.to_dict() for candle in candles],
            "candle_count": len(candles),
            "expected_candle_count": per_day,
            "first_open_time_utc": candles[0].open_time.isoformat().replace("+00:00", "Z"),
            "last_close_time_utc": candles[-1].close_time.isoformat().replace("+00:00", "Z"),
            "performance": {
                "open": str(opening), "close": str(closing),
                "change_percent": str(change_pct) if change_pct is not None else None,
                "high": str(max(c.high for c in candles)),
                "low": str(min(c.low for c in candles)),
                "base_volume": str(sum((c.volume for c in candles), Decimal("0"))),
            },
            "validation": [issue.to_dict() for issue in validation],
            "indicators": analyze_candles(history + candles),
            "indicator_history": {
                "candle_count": len(history),
                "candles": [candle.to_dict() for candle in history],
                "first_open_time_utc": history[0].open_time.isoformat().replace("+00:00", "Z"),
                "last_close_time_utc": history[-1].close_time.isoformat().replace("+00:00", "Z"),
                "pagination": history_page.to_dict(),
                "response_metadata": history_metadata,
            },
            "pagination": page.to_dict(),
            "response_metadata": {"candles": candle_metadata},
        }
        try:
            ticker = client.get_24h_ticker(symbol, market)
            item["ticker_24h"] = {
                "status": "ok", "data": ticker,
                "response_metadata": dict(client.last_response_metadata),
            }
        except Exception as exc:
            item["ticker_24h"] = {
                "status": "unavailable", "error": f"{type(exc).__name__}: {exc}",
                "response_metadata": dict(client.last_response_metadata),
            }
        if market == "usdm":
            item["derivatives"] = acquire_derivatives_context(client, symbol, interval)
        result["symbols"][symbol] = item
    result["provenance"] = [
        {"source": "Binance public REST API",
         "retrieved_at_utc": item["response_metadata"]["candles"].get("retrieved_at_utc", "Not supplied"),
         "note": f"{symbol}: {item['candle_count']} verified session candles and "
                 f"{item['indicator_history']['candle_count']} separate indicator warm-up candles."}
        for symbol, item in result["symbols"].items()
    ]
    return result

def acquire_market_window(
    client: BinancePublicClient,
    window_start_utc: datetime,
    cutoff_utc: datetime,
    interval: str = "1h",
    market: str = "spot",
    symbols: tuple[str, ...] | list[str] = CORE_SYMBOLS,
    indicator_lookback: int = 250,
    window_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Acquire every fully closed candle in an arbitrary half-open UTC window.

    The requested cutoff is preserved exactly. If it falls inside a candle,
    that unfinished candle is excluded and data_cutoff_utc records the last
    fully closed interval boundary. This supports partial local calendar days
    without leaking post-cutoff or incomplete candle data.
    """
    def require_utc(value: datetime, field: str) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError(f"{field} must be a timezone-aware UTC datetime")
        return value.astimezone(timezone.utc)

    start = require_utc(window_start_utc, "window_start_utc")
    cutoff = require_utc(cutoff_utc, "cutoff_utc")
    if cutoff <= start:
        raise ValueError("cutoff_utc must be later than window_start_utc")
    interval_ms = interval_milliseconds(interval)
    if interval_ms is None or interval_ms < 60_000 or interval in {"1d", "3d", "1w"}:
        raise ValueError(f"Unsupported report interval (minimum 1m): {interval!r}")
    if 86_400_000 % interval_ms:
        raise ValueError("The selected interval must divide a 24-hour day exactly")
    if isinstance(indicator_lookback, bool) or not isinstance(indicator_lookback, int) or indicator_lookback < 200:
        raise ValueError("indicator_lookback must be an integer of at least 200 candles")
    if market not in {"spot", "usdm"}:
        raise ValueError("market must be 'spot' or 'usdm'")

    server_time = require_utc(client.get_server_time(market), "Binance server time")
    if cutoff > server_time:
        raise ValueError("cutoff_utc is later than Binance server time")
    elapsed_ms = int((cutoff - start).total_seconds() * 1000)
    expected_count = elapsed_ms // interval_ms
    if expected_count < 1:
        raise ValueError("The requested window contains no fully closed candle")
    data_end = start + timedelta(milliseconds=expected_count * interval_ms)

    requested = tuple(str(symbol).upper() for symbol in symbols)
    missing = [symbol for symbol in CORE_SYMBOLS if symbol not in requested]
    if missing:
        raise ValueError("Mandatory core symbols missing: " + ", ".join(missing))
    if len(set(requested)) != len(requested):
        raise ValueError("symbols must be unique")

    history_start = start - timedelta(milliseconds=indicator_lookback * interval_ms)
    metadata = dict(window_metadata or {})
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "source": "Binance public REST API",
        "market": market,
        "interval": interval,
        "session_start_utc": start.isoformat().replace("+00:00", "Z"),
        "session_end_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "window_start_utc": start.isoformat().replace("+00:00", "Z"),
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "data_cutoff_utc": data_end.isoformat().replace("+00:00", "Z"),
        "binance_server_time_utc": server_time.isoformat().replace("+00:00", "Z"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data_status": "partial" if metadata.get("is_partial", cutoff < start + timedelta(days=1)) else "complete",
        "indicator_methodology": {
            "lookback_candles": indicator_lookback,
            "report_window_excludes_lookback": True,
            "partial_final_interval_excluded": data_end < cutoff,
        },
        "read_only": True,
        **metadata,
        "symbols": {},
    }
    for symbol in requested:
        history, history_page = client.get_historical_klines(
            symbol, interval, history_start, start, market=market
        )
        if not history_page.complete or history_page.returned != len(history):
            raise ValueError(f"{symbol}: indicator-history pagination is incomplete or inconsistent")
        _validate_series(history, symbol, interval, history_start, start,
                         indicator_lookback, "indicator-history")
        history_metadata = dict(client.last_response_metadata)

        candles, page = client.get_historical_klines(
            symbol, interval, start, data_end, market=market
        )
        candle_metadata = dict(client.last_response_metadata)
        if not page.complete or page.returned != len(candles):
            raise ValueError(f"{symbol}: report-window pagination is incomplete or inconsistent")
        _validate_series(candles, symbol, interval, start, data_end,
                         expected_count, "report-window")
        opening, closing = candles[0].open, candles[-1].close
        change_pct = ((closing - opening) / opening * Decimal("100")) if opening else None
        item: dict[str, Any] = {
            "candles": [candle.to_dict() for candle in candles],
            "candle_count": len(candles),
            "expected_candle_count": expected_count,
            "first_open_time_utc": candles[0].open_time.isoformat().replace("+00:00", "Z"),
            "last_close_time_utc": candles[-1].close_time.isoformat().replace("+00:00", "Z"),
            "performance": {
                "open": str(opening), "close": str(closing),
                "change_percent": str(change_pct) if change_pct is not None else None,
                "high": str(max(c.high for c in candles)),
                "low": str(min(c.low for c in candles)),
                "base_volume": str(sum((c.volume for c in candles), Decimal("0"))),
            },
            "validation": [issue.to_dict() for issue in validate_candles(candles, interval)],
            "indicators": analyze_candles(history + candles),
            "indicator_history": {
                "candle_count": len(history),
                "expected_candle_count": indicator_lookback,
                "candles": [candle.to_dict() for candle in history],
                "first_open_time_utc": history[0].open_time.isoformat().replace("+00:00", "Z"),
                "last_close_time_utc": history[-1].close_time.isoformat().replace("+00:00", "Z"),
                "pagination": history_page.to_dict(),
                "response_metadata": history_metadata,
            },
            "pagination": page.to_dict(),
            "response_metadata": {"candles": candle_metadata},
        }
        try:
            ticker = client.get_24h_ticker(symbol, market)
            item["ticker_24h"] = {
                "status": "ok", "data": ticker,
                "response_metadata": dict(client.last_response_metadata),
            }
        except Exception as exc:
            item["ticker_24h"] = {
                "status": "unavailable", "error": f"{type(exc).__name__}: {exc}",
                "response_metadata": dict(client.last_response_metadata),
            }
        if market == "usdm":
            item["derivatives"] = acquire_derivatives_context(client, symbol, interval)
        result["symbols"][symbol] = item
    result["provenance"] = [
        {
            "source": "Binance public REST API",
            "retrieved_at_utc": item["response_metadata"]["candles"].get("retrieved_at_utc", "Not supplied"),
            "note": f"{symbol}: {item['candle_count']} fully closed report-window candles; "
                    f"{item['indicator_history']['candle_count']} separate indicator warm-up candles.",
        }
        for symbol, item in result["symbols"].items()
    ]
    return result

