"""UTC-day Binance acquisition and intraday PDF workflow."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.engine import CORE_SYMBOLS, analyze_candles
from binance_data_engine.validation import interval_milliseconds, validate_candles

from .intraday import build_intraday_snapshot_pdf


def acquire_intraday_evidence(
    client: BinancePublicClient,
    cutoff_utc: datetime,
    interval: str = "1h",
    market: str = "spot",
) -> dict[str, Any]:
    """Acquire every completed candle in [00:00 UTC, cutoff), failing closed.

    BTCUSDT and ETHUSDT are mandatory. The cutoff must align to the interval.
    Missing, duplicated, misaligned, invalid, or incompletely paginated candles
    prevent report generation; no synthetic values are inserted.
    """
    if not isinstance(cutoff_utc, datetime) or cutoff_utc.tzinfo is None:
        raise ValueError("cutoff_utc must be a timezone-aware UTC datetime")
    if cutoff_utc.utcoffset().total_seconds() != 0:
        raise ValueError("cutoff_utc must use UTC")
    cutoff = cutoff_utc.astimezone(timezone.utc)
    start = datetime.combine(cutoff.date(), time.min, tzinfo=timezone.utc)
    if cutoff <= start:
        raise ValueError("cutoff_utc must be later than 00:00 UTC")
    cadence = interval_milliseconds(interval)
    if cadence is None or interval in {"1d", "3d", "1w"}:
        raise ValueError(f"Unsupported fixed intraday interval: {interval!r}")
    elapsed_ms = int((cutoff - start).total_seconds() * 1000)
    if elapsed_ms % cadence:
        raise ValueError("cutoff_utc must align exactly to the requested candle interval")
    expected_count = elapsed_ms // cadence
    if expected_count < 1:
        raise ValueError("The report window must contain at least one complete candle")
    if market not in {"spot", "usdm"}:
        raise ValueError("market must be 'spot' or 'usdm'")

    server_time = client.get_server_time(market)
    if server_time.tzinfo is None or server_time.utcoffset().total_seconds() != 0:
        raise ValueError("Binance server time must be timezone-aware UTC")
    if cutoff > server_time:
        raise ValueError("cutoff_utc is later than Binance server time")
    generated = datetime.now(timezone.utc)
    if generated < cutoff:
        raise ValueError("Local system clock is behind cutoff_utc")

    symbols: dict[str, Any] = {}
    for symbol in CORE_SYMBOLS:
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
            expected_open = start + timedelta(milliseconds=index * cadence)
            expected_close = expected_open + timedelta(milliseconds=cadence - 1)
            if candle.symbol != symbol:
                raise ValueError(f"{symbol}: response contains candle for {candle.symbol}")
            if candle.open_time != expected_open or candle.close_time != expected_close:
                raise ValueError(
                    f"{symbol}: candle {index} is missing, duplicated, misaligned, or not closed"
                )
            if candle.close_time >= cutoff:
                raise ValueError(f"{symbol}: candle reaches the exclusive report cutoff")

        candle_metadata = dict(client.last_response_metadata)
        ticker_data = None
        ticker_error = None
        try:
            ticker_data = client.get_24h_ticker(symbol, market)
            ticker = {"status": "ok", "data": ticker_data,
                      "response_metadata": dict(client.last_response_metadata)}
        except Exception as exc:
            ticker_error = f"{type(exc).__name__}: {exc}"
            ticker = {"status": "unavailable", "error": ticker_error,
                      "response_metadata": dict(client.last_response_metadata)}

        symbols[symbol] = {
            "candles": [candle.to_dict() for candle in candles],
            "candle_count": len(candles),
            "expected_candle_count": expected_count,
            "first_open_time_utc": candles[0].open_time.isoformat().replace("+00:00", "Z"),
            "last_close_time_utc": candles[-1].close_time.isoformat().replace("+00:00", "Z"),
            "ticker_24h": ticker,
            "indicators": analyze_candles(candles),
            "validation": [issue.to_dict() for issue in issues],
            "response_metadata": candle_metadata,
            "pagination": pagination.to_dict(),
        }

    generated_text = generated.isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "1.0",
        "window_start_utc": start.isoformat().replace("+00:00", "Z"),
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "generated_at_utc": generated_text,
        "source": "Binance public REST API",
        "market": market,
        "interval": interval,
        "data_status": "complete",
        "executive_summary": (
            "All expected completed candles for BTCUSDT and ETHUSDT passed strict "
            "UTC-window, pagination, and data-integrity checks."
        ),
        "symbols": symbols,
        "provenance": [{
            "source": "Binance public REST API",
            "retrieved_at_utc": item["response_metadata"].get("retrieved_at_utc", "Not supplied"),
            "note": f"{symbol}: {item['candle_count']} verified {interval} candles "
                    "in [00:00 UTC, cutoff_utc).",
        } for symbol, item in symbols.items()],
    }


def generate_intraday_snapshot_pdf(
    client: BinancePublicClient,
    cutoff_utc: datetime,
    output_directory: Path | str,
    interval: str = "1h",
    market: str = "spot",
) -> Path:
    """Acquire, validate, and render a UTC intraday snapshot PDF."""
    evidence = acquire_intraday_evidence(client, cutoff_utc, interval, market)
    return build_intraday_snapshot_pdf(evidence, output_directory)
