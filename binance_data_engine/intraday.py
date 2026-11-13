"""Strict Binance acquisition for complete UTC-day intraday report windows."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from .client import BinancePublicClient
from .engine import CORE_SYMBOLS, analyze_candles
from .validation import interval_milliseconds, validate_candles


def _require_utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a timezone-aware UTC datetime")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    # Preserve the millisecond precision of Binance candle close timestamps.
    return value.isoformat().replace("+00:00", "Z")


def _capture_ticker(client: BinancePublicClient, symbol: str, market: str) -> dict[str, Any]:
    try:
        data = client.get_24h_ticker(symbol, market)
        return {"status": "ok", "data": data,
                "response_metadata": dict(client.last_response_metadata)}
    except Exception as exc:
        return {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}",
                "response_metadata": dict(client.last_response_metadata)}


def acquire_intraday_day(
    client: BinancePublicClient,
    report_date: date,
    cutoff_utc: datetime,
    interval: str = "1h",
    market: str = "spot",
    symbols: tuple[str, ...] | list[str] = CORE_SYMBOLS,
    include_ticker: bool = True,
) -> dict[str, Any]:
    """Acquire and verify every closed candle in [00:00 UTC, cutoff_utc).

    The cutoff must align to the requested fixed intraday interval. Missing,
    duplicated, misaligned, partial, or invalid candles cause acquisition to fail;
    no interpolation or synthetic candles are produced.
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
    if interval_ms is None or interval in {"1d", "3d", "1w"}:
        raise ValueError(f"Unsupported fixed intraday interval: {interval!r}")
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

    result: dict[str, Any] = {
        "schema_version": "1.0",
        "source": "Binance public REST API",
        "market": market,
        "interval": interval,
        "window_start_utc": _iso(start),
        "cutoff_utc": _iso(cutoff),
        "binance_server_time_utc": _iso(server_time),
        "data_status": "complete",
        "read_only": True,
        "symbols": {},
    }
    for symbol in requested:
        candles, pagination = client.get_historical_klines(
            symbol, interval, start, cutoff, market=market
        )
        if not pagination.complete:
            raise ValueError(f"{symbol}: Binance pagination did not complete the requested window")
        if len(candles) != expected_count:
            raise ValueError(
                f"{symbol}: expected {expected_count} candles, received {len(candles)}; "
                "the UTC-day window is incomplete"
            )
        issues = validate_candles(candles, interval)
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            raise ValueError(f"{symbol}: invalid candle data: " +
                             "; ".join(issue.message for issue in errors))
        for index, candle in enumerate(candles):
            expected_open = start + timedelta(milliseconds=index * interval_ms)
            expected_close = expected_open + timedelta(milliseconds=interval_ms - 1)
            if candle.symbol != symbol:
                raise ValueError(f"{symbol}: response contains candle for {candle.symbol}")
            if candle.open_time != expected_open or candle.close_time != expected_close:
                raise ValueError(
                    f"{symbol}: candle {index} is missing, duplicated, misaligned, or not closed"
                )
            if candle.close_time >= cutoff:
                raise ValueError(f"{symbol}: candle close time reaches the exclusive cutoff")

        response_metadata = dict(client.last_response_metadata)
        item: dict[str, Any] = {
            "candles": [candle.to_dict() for candle in candles],
            "candle_count": len(candles),
            "expected_candle_count": expected_count,
            "first_open_time_utc": _iso(candles[0].open_time),
            "last_close_time_utc": _iso(candles[-1].close_time),
            "validation": [issue.to_dict() for issue in issues],
            "indicators": analyze_candles(candles),
            "pagination": pagination.to_dict(),
            "response_metadata": response_metadata,
        }
        if include_ticker:
            item["ticker_24h"] = _capture_ticker(client, symbol, market)
        result["symbols"][symbol] = item

    generated = datetime.now(timezone.utc)
    result["generated_at_utc"] = _iso(generated)
    result["provenance"] = [
        {"source": "Binance public REST API",
         "retrieved_at_utc": item["response_metadata"].get("retrieved_at_utc", "Not supplied"),
         "note": f"{symbol}: {item['candle_count']} verified {interval} candles; "
                 "window is [00:00 UTC, cutoff_utc)."}
        for symbol, item in result["symbols"].items()
    ]
    return result
