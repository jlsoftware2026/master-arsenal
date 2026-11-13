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
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
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


def acquire_intraday_evidence(
    client: BinancePublicClient,
    cutoff_utc: datetime,
    interval: str = "1h",
    market: str = "spot",
    symbols: tuple[str, ...] = CORE_SYMBOLS,
) -> dict[str, Any]:
    """Acquire and verify the UTC-day window [00:00, cutoff), without filling gaps.

    The cutoff must align to the fixed-duration interval. Completeness is checked
    against the exact expected candle grid, inclusive close timestamps, validation
    results, returned-row counts, and Binance pagination metadata. Any integrity
    failure is explicitly marked as incomplete; no candles are synthesized.
    """
    cutoff = _utc(cutoff_utc, "cutoff_utc")
    start = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    cadence = interval_milliseconds(interval)
    if cadence is None or interval in {"1d", "3d", "1w"}:
        raise ValueError(f"Unsupported fixed-duration intraday interval: {interval!r}")
    if cutoff <= start:
        raise ValueError("cutoff_utc must be later than 00:00 UTC")
    elapsed_ms = int((cutoff - start).total_seconds() * 1000)
    if elapsed_ms % cadence:
        raise ValueError("cutoff_utc must align exactly to the requested candle interval")
    if market not in {"spot", "usdm"}:
        raise ValueError("market must be 'spot' or 'usdm'")
    requested = tuple(symbol.upper() for symbol in symbols)
    missing_core = [symbol for symbol in CORE_SYMBOLS if symbol not in requested]
    if missing_core:
        raise ValueError("Core symbols are mandatory: " + ", ".join(missing_core))
    if len(set(requested)) != len(requested):
        raise ValueError("symbols must be unique")

    server_time = _utc(client.get_server_time(market), "Binance server time")
    if cutoff > server_time:
        raise ValueError("cutoff_utc is later than Binance server time")

    expected_opens = [
        start + timedelta(milliseconds=index * cadence)
        for index in range(elapsed_ms // cadence)
    ]
    expected_open_set = set(expected_opens)
    symbols_data: dict[str, Any] = {}
    all_complete = True
    for symbol in requested:
        candles, pagination = client.get_historical_klines(
            symbol, interval, start, cutoff, market=market
        )
        returned = list(candles)
        issues = [issue.to_dict() for issue in validate_candles(returned, interval)]
        eligible = []
        seen_opens = set()
        for index, candle in enumerate(returned):
            if candle.symbol != symbol:
                issues.append({
                    "code": "symbol_mismatch", "severity": "error",
                    "message": f"Expected {symbol}, received {candle.symbol}.",
                    "index": index,
                })
            if candle.open_time < start or candle.open_time >= cutoff or candle.close_time >= cutoff:
                issues.append({
                    "code": "candle_outside_window", "severity": "error",
                    "message": "Returned candle is outside the requested closed-candle window.",
                    "index": index,
                })
                continue
            if candle.open_time in seen_opens:
                issues.append({
                    "code": "duplicate_candle", "severity": "error",
                    "message": "Duplicate candle open timestamp.",
                    "index": index,
                })
            seen_opens.add(candle.open_time)
            expected_close = candle.open_time + timedelta(milliseconds=cadence - 1)
            if candle.open_time not in expected_open_set or candle.close_time != expected_close:
                issues.append({
                    "code": "misaligned_candle", "severity": "error",
                    "message": "Candle open/close timestamps do not match the requested interval grid.",
                    "index": index,
                })
            eligible.append(candle)

        missing_opens = [opened for opened in expected_opens if opened not in seen_opens]
        if missing_opens:
            issues.append({
                "code": "missing_candles", "severity": "error",
                "message": f"{len(missing_opens)} expected completed {interval} candle(s) are missing.",
                "missing_open_times_utc": [_iso(value) for value in missing_opens],
            })
        if pagination.returned != len(returned):
            issues.append({
                "code": "pagination_count_mismatch", "severity": "error",
                "message": "Pagination metadata count does not match the returned candle rows.",
            })
        if not pagination.complete:
            issues.append({
                "code": "pagination_incomplete", "severity": "error",
                "message": "Binance pagination did not confirm the requested time range.",
            })
        if len(returned) != len(expected_opens) and not missing_opens:
            issues.append({
                "code": "candle_count_mismatch", "severity": "error",
                "message": f"Expected {len(expected_opens)} candles, received {len(returned)}.",
            })

        symbol_complete = not any(issue.get("severity") == "error" for issue in issues)
        all_complete = all_complete and symbol_complete and pagination.complete
        candle_metadata = dict(client.last_response_metadata)
        ticker = _capture_ticker(client, symbol, market)
        symbols_data[symbol] = {
            "candles": [candle.to_dict() for candle in eligible],
            "candle_count": len(eligible),
            "expected_candle_count": len(expected_opens),
            "first_open_time_utc": _iso(eligible[0].open_time) if eligible else None,
            "last_close_time_utc": _iso(eligible[-1].close_time) if eligible else None,
            "ticker_24h": ticker,
            "indicators": analyze_candles(eligible),
            "validation": issues,
            "response_metadata": {
                "candles": candle_metadata,
                "ticker_24h": ticker.get("response_metadata", {}),
                "pagination": pagination.to_dict(),
            },
        }

    generated = datetime.now(timezone.utc)
    if generated < cutoff:
        raise ValueError("Local system clock is behind cutoff_utc; refusing to misstate generation time")
    return {
        "window_start_utc": _iso(start),
        "cutoff_utc": _iso(cutoff),
        "generated_at_utc": _iso(generated),
        "source": "Binance public REST API",
        "market": market,
        "interval": interval,
        "binance_server_time_utc": _iso(server_time),
        "data_status": "complete" if all_complete else "incomplete",
        "executive_summary": (
            "All expected completed candles passed acquisition checks."
            if all_complete else
            "One or more symbols have missing, invalid, misaligned, out-of-window, or "
            "incompletely paginated data. This report must be treated as incomplete."
        ),
        "symbols": symbols_data,
        "provenance": [{
            "source": "Binance public REST API",
            "retrieved_at_utc": item["response_metadata"]["candles"].get(
                "retrieved_at_utc", "Not supplied"
            ),
            "note": f"{symbol}: {item['candle_count']}/{item['expected_candle_count']} "
                    f"verified {interval} candles; market={market}; "
                    f"server_time_utc={_iso(server_time)}.",
        } for symbol, item in symbols_data.items()],
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
