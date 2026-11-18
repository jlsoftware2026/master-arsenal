"""Strict Binance acquisition for complete UTC-day intraday report windows."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from .client import BinancePublicClient
from .engine import CORE_SYMBOLS, analyze_candles, acquire_derivatives_context
from .validation import interval_milliseconds, validate_candles


def _require_utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a timezone-aware UTC datetime")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _capture_ticker(client: BinancePublicClient, symbol: str, market: str) -> dict[str, Any]:
    try:
        data = client.get_24h_ticker(symbol, market)
        return {"status": "ok", "data": data,
                "response_metadata": dict(client.last_response_metadata)}
    except Exception as exc:
        return {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}",
                "response_metadata": dict(client.last_response_metadata)}


def _validate_series(candles, symbol: str, interval: str, start: datetime,
                     end: datetime, expected_count: int, label: str) -> None:
    issues = validate_candles(candles, interval)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise ValueError(f"{symbol}: invalid {label} candle data: " +
                         "; ".join(issue.message for issue in errors))
    if len(candles) != expected_count:
        raise ValueError(
            f"{symbol}: expected {expected_count} candles, received {len(candles)} ({label})"
        )
    interval_ms = interval_milliseconds(interval)
    for index, candle in enumerate(candles):
        expected_open = start + timedelta(milliseconds=index * interval_ms)
        expected_close = expected_open + timedelta(milliseconds=interval_ms - 1)
        if candle.symbol != symbol:
            raise ValueError(f"{symbol}: {label} response contains candle for {candle.symbol}")
        if candle.open_time != expected_open or candle.close_time != expected_close:
            raise ValueError(
                f"{symbol}: {label} candle {index} is missing, duplicated, misaligned, or not closed"
            )
        if candle.open_time < start or candle.open_time >= end or candle.close_time >= end:
            raise ValueError(f"{symbol}: {label} candle falls outside its exclusive time window")


def acquire_intraday_day(
    client: BinancePublicClient,
    report_date: date,
    cutoff_utc: datetime,
    interval: str = "1h",
    market: str = "spot",
    symbols: tuple[str, ...] | list[str] = CORE_SYMBOLS,
    include_ticker: bool = True,
    indicator_lookback: int = 250,
) -> dict[str, Any]:
    """Acquire a verified UTC-day window plus separate pre-window indicator history.

    Report candles remain exactly in [00:00 UTC, cutoff_utc). The preceding
    lookback is used only to warm up rolling indicators; it is not included in
    report-window counts, charts, or period-performance calculations.
    """
    if not isinstance(report_date, date) or isinstance(report_date, datetime):
        raise ValueError("report_date must be a datetime.date, not a datetime")
    cutoff = _require_utc(cutoff_utc, "cutoff_utc")
    if cutoff.date() != report_date:
        raise ValueError("cutoff_utc must fall on report_date in UTC")
    start = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
    if cutoff <= start:
        raise ValueError("cutoff_utc must be later than 00:00 UTC")
    interval_ms = interval_milliseconds(interval)
    if interval_ms is None or interval_ms < 60_000 or interval in {"1d", "3d", "1w"}:
        raise ValueError(f"Unsupported report interval (minimum 1m): {interval!r}")
    if isinstance(indicator_lookback, bool) or not isinstance(indicator_lookback, int) or indicator_lookback < 200:
        raise ValueError("indicator_lookback must be an integer of at least 200 candles")
    elapsed_ms = int((cutoff - start).total_seconds() * 1000)
    if elapsed_ms % interval_ms:
        raise ValueError("cutoff_utc must align exactly to the requested candle interval")
    expected_count = elapsed_ms // interval_ms
    if expected_count < 1:
        raise ValueError("The requested UTC-day window must contain at least one full candle")
    if market not in {"spot", "usdm"}:
        raise ValueError("market must be 'spot' or 'usdm'")
    requested = tuple(str(symbol).upper() for symbol in symbols)
    missing = [symbol for symbol in CORE_SYMBOLS if symbol not in requested]
    if missing:
        raise ValueError("Mandatory core symbols missing: " + ", ".join(missing))
    if len(set(requested)) != len(requested):
        raise ValueError("symbols must be unique")

    server_time = _require_utc(client.get_server_time(market), "Binance server time")
    if cutoff > server_time:
        raise ValueError("cutoff_utc is later than Binance server time; future candles cannot be acquired")

    history_start = start - timedelta(milliseconds=indicator_lookback * interval_ms)
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "source": "Binance public REST API",
        "market": market,
        "interval": interval,
        "window_start_utc": _iso(start),
        "cutoff_utc": _iso(cutoff),
        "binance_server_time_utc": _iso(server_time),
        "data_status": "complete",
        "indicator_methodology": {
            "calculation_series": "pre-window lookback + report-window candles",
            "lookback_candles": indicator_lookback,
            "report_window_excludes_lookback": True,
            "note": "Historical warm-up candles are excluded from report-window statistics and charts.",
        },
        "read_only": True,
        "symbols": {},
    }
    for symbol in requested:
        history, history_pagination = client.get_historical_klines(
            symbol, interval, history_start, start, market=market
        )
        if not history_pagination.complete:
            raise ValueError(f"{symbol}: indicator-history pagination did not complete")
        if history_pagination.returned != len(history):
            raise ValueError(f"{symbol}: indicator-history pagination metadata count does not match returned candles")
        _validate_series(history, symbol, interval, history_start, start,
                         indicator_lookback, "indicator-history")
        history_metadata = dict(client.last_response_metadata)

        candles, pagination = client.get_historical_klines(
            symbol, interval, start, cutoff, market=market
        )
        candle_metadata = dict(client.last_response_metadata)
        if not pagination.complete:
            raise ValueError(f"{symbol}: Binance pagination did not complete the requested window")
        if pagination.returned != len(candles):
            raise ValueError(f"{symbol}: pagination metadata count does not match returned candles")
        _validate_series(candles, symbol, interval, start, cutoff,
                         expected_count, "report-window")

        item: dict[str, Any] = {
            "candles": [candle.to_dict() for candle in candles],
            "candle_count": len(candles),
            "expected_candle_count": expected_count,
            "first_open_time_utc": _iso(candles[0].open_time),
            "last_close_time_utc": _iso(candles[-1].close_time),
            "validation": [issue.to_dict() for issue in validate_candles(candles, interval)],
            "indicators": analyze_candles(history + candles),
            "indicator_history": {
                "candle_count": len(history),
                "expected_candle_count": indicator_lookback,
                "candles": [candle.to_dict() for candle in history],
                "first_open_time_utc": _iso(history[0].open_time),
                "last_close_time_utc": _iso(history[-1].close_time),
                "pagination": history_pagination.to_dict(),
                "response_metadata": history_metadata,
            },
            "pagination": pagination.to_dict(),
            "response_metadata": {"candles": candle_metadata},
        }
        if include_ticker:
            item["ticker_24h"] = _capture_ticker(client, symbol, market)
        if market == "usdm":
            item["derivatives"] = acquire_derivatives_context(client, symbol, interval)
        result["symbols"][symbol] = item

    generated = datetime.now(timezone.utc)
    result["generated_at_utc"] = _iso(generated)
    result["provenance"] = [
        {"source": "Binance public REST API",
         "retrieved_at_utc": item["response_metadata"]["candles"].get("retrieved_at_utc", "Not supplied"),
         "note": f"{symbol}: {item['candle_count']} verified report-window candles and "
                 f"{item['indicator_history']['candle_count']} separate indicator warm-up candles; "
                 "report window is [00:00 UTC, cutoff_utc)."}
        for symbol, item in result["symbols"].items()
    ]
    return result
