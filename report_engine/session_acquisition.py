"""Acquisition-to-PDF adapters for completed UTC market-day reports."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.session import acquire_completed_market_day

from .session import build_closing_report_pdf, build_opening_report_pdf


def acquire_session_report_evidence(
    client: BinancePublicClient,
    session_date: date | None = None,
    interval: str = "1h",
    market: str = "spot",
) -> dict[str, Any]:
    """Acquire a completed UTC day and produce transparent, data-derived summary text."""
    report = acquire_completed_market_day(
        client, session_date=session_date, interval=interval, market=market
    )
    changes = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        performance = report["symbols"][symbol]["performance"]
        value = performance.get("change_percent")
        changes.append(f"{symbol}: {value}% change from first open to final close"
                       if value is not None else f"{symbol}: percentage change unavailable")
    report["executive_summary"] = (
        "Observed session performance (first candle open to final candle close): "
        + "; ".join(changes)
        + ". These are descriptive session measurements, not causal explanations or forecasts."
    )
    report["technical_analysis"] = (
        "Indicator values are calculated from the pre-session warm-up series plus the completed "
        "session candles. The warm-up series is excluded from session charts and performance. "
        "Interpret indicator values alongside the raw candle evidence; unavailable values are "
        "not imputed."
    )
    report["assumptions_and_invalidation"] = (
        "No forward scenario levels were inferred automatically. Add a separately reviewed "
        "technical scenario before using this report for a trading decision."
    )
    report["limitations"] = (
        "This implementation currently acquires Binance market data only. Macroeconomic and "
        "news evidence is not yet connected; no news, event, or causal attribution is asserted."
    )
    return report


def generate_opening_report_pdf(
    client: BinancePublicClient,
    output_directory: Path | str,
    session_date: date | None = None,
    interval: str = "1h",
    market: str = "spot",
) -> Path:
    evidence = acquire_session_report_evidence(client, session_date, interval, market)
    return build_opening_report_pdf(evidence, output_directory)


def generate_closing_report_pdf(
    client: BinancePublicClient,
    output_directory: Path | str,
    session_date: date | None = None,
    interval: str = "1h",
    market: str = "spot",
) -> Path:
    evidence = acquire_session_report_evidence(client, session_date, interval, market)
    return build_closing_report_pdf(evidence, output_directory)
