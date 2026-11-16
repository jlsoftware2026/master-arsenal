"""Adapter from strict Binance UTC-day evidence to the PDF report workflow."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.engine import CORE_SYMBOLS
from binance_data_engine.intraday import acquire_intraday_day

from .intraday import build_intraday_snapshot_pdf
from .context import collect_market_context


def acquire_intraday_evidence(
    client: BinancePublicClient,
    cutoff_utc: datetime,
    interval: str = "1h",
    market: str = "spot",
    symbols: tuple[str, ...] = CORE_SYMBOLS,
) -> dict[str, Any]:
    """Acquire a complete, aligned UTC-day evidence set for BTCUSDT and ETHUSDT."""
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
        symbols=symbols,
        include_ticker=True,
    )
    if datetime.now(timezone.utc) < cutoff_utc:
        raise ValueError("Local system clock is behind cutoff_utc; refusing to misstate generation time")
    context = collect_market_context(
        datetime.combine(cutoff_utc.date(), datetime.min.time(), tzinfo=timezone.utc),
        cutoff_utc,
    )
    report.update(context)
    report["news_context"] = context["news"]
    report["limitations"] = context["context_limitations"]
    bullish, bearish = [], []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        candles = report["symbols"][symbol]["candles"]
        high = max(Decimal(candle["high"]) for candle in candles)
        low = min(Decimal(candle["low"]) for candle in candles)
        last = candles[-1]["close"]
        bullish.append(
            f"{symbol}: remaining-session continuation requires acceptance above the "
            f"observed high {format(high, 'f')}; invalidation reference is below the observed low {format(low, 'f')}. "
            f"Last close: {last}."
        )
        bearish.append(
            f"{symbol}: remaining-session weakness requires acceptance below the "
            f"observed low {format(low, 'f')}; invalidation reference is above the observed high {format(high, 'f')}. "
            f"Last close: {last}."
        )
    report["bullish_scenario"] = " ".join(bullish) + " Conditional levels only; no probability or target is inferred."
    report["bearish_scenario"] = " ".join(bearish) + " Conditional levels only; no probability or target is inferred."
    report["risk_factors"] = (
        "False breakouts, liquidity changes, volatility expansion, spread/slippage, and events "
        "not represented in the configured RSS feeds may invalidate these reference levels."
    )
    report["executive_summary"] = (
        "All expected completed candles for BTCUSDT and ETHUSDT passed strict "
        "UTC-window, pagination, and data-integrity checks. Macro/news context is "
        + context["context_status"] + " and is reported with publication timestamps and source URLs."
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
