"""Connect strict Binance UTC-day acquisition to intraday PDF rendering."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.engine import CORE_SYMBOLS
from binance_data_engine.intraday import acquire_intraday_day

from .intraday import build_intraday_snapshot_pdf


def acquire_intraday_evidence(
    client: BinancePublicClient,
    cutoff_utc: datetime,
    interval: str = "1h",
    market: str = "spot",
) -> dict:
    """Acquire a complete, aligned UTC-day evidence set for BTC and ETH.

    The underlying Binance engine rejects missing, duplicate, misaligned, invalid,
    or incompletely paginated candles. This adapter adds the PDF composer's summary
    contract without weakening those acquisition guarantees.
    """
    if not isinstance(cutoff_utc, datetime) or cutoff_utc.tzinfo is None:
        raise ValueError("cutoff_utc must be a timezone-aware UTC datetime")
    if cutoff_utc.utcoffset().total_seconds() != 0:
        raise ValueError("cutoff_utc must use UTC")
    report = acquire_intraday_day(
        client=client,
        report_date=cutoff_utc.date(),
        cutoff_utc=cutoff_utc,
        interval=interval,
        market=market,
        symbols=CORE_SYMBOLS,
        include_ticker=True,
    )
    if datetime.now(timezone.utc) < cutoff_utc:
        raise ValueError("Local system clock is behind cutoff_utc; refusing to misstate generation time")
    report["executive_summary"] = (
        "All expected completed candles for BTCUSDT and ETHUSDT passed strict "
        "UTC-window, pagination, and data-integrity checks."
    )
    return report


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
