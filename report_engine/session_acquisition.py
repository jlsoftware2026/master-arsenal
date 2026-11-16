"""Acquisition-to-PDF adapters for completed UTC market-day reports."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.session import acquire_completed_market_day
from .context import collect_market_context
from .evidence import write_evidence_manifest

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
    bullish, bearish = [], []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        performance = report["symbols"][symbol]["performance"]
        high, low, close = performance["high"], performance["low"], performance["close"]
        bullish.append(
            f"{symbol}: bullish continuation is conditional on acceptance above the prior-session "
            f"high {high}; the scenario is invalidated below the prior-session low {low}. "
            f"Last session close: {close}."
        )
        bearish.append(
            f"{symbol}: bearish continuation is conditional on acceptance below the prior-session "
            f"low {low}; the scenario is invalidated above the prior-session high {high}. "
            f"Last session close: {close}."
        )
    report["bullish_scenario"] = " ".join(bullish) + " These are conditional reference levels, not price targets or probability forecasts."
    report["bearish_scenario"] = " ".join(bearish) + " These are conditional reference levels, not price targets or probability forecasts."
    report["assumptions_and_invalidation"] = (
        "Breakout acceptance must be independently confirmed with current price action and volume. "
        "The opposite side of the prior-session range is used as a simple invalidation reference; "
        "no target or probability is inferred."
    )
    report["risks"] = (
        "False breakouts, low liquidity, volatility shocks, spread/slippage, and events outside "
        "the configured RSS feeds can invalidate these reference scenarios."
    )
    start = datetime.fromisoformat(report["session_start_utc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(report["session_end_utc"].replace("Z", "+00:00"))
    context = collect_market_context(start, end)
    report.update(context)
    report["limitations"] = (
        "RSS context is date-bounded but not exhaustive. Feed outages and missing publication "
        "timestamps are disclosed. Headlines are candidate context only; no causal attribution "
        "to price movements is asserted. "
        + context["context_limitations"]
    )
    return report


def generate_opening_report_pdf(
    client: BinancePublicClient,
    output_directory: Path | str,
    session_date: date | None = None,
    interval: str = "1h",
    market: str = "spot",
    manifest_directory: Path | str | None = None,
) -> Path:
    evidence = acquire_session_report_evidence(client, session_date, interval, market)
    artifact = build_opening_report_pdf(evidence, output_directory)
    if manifest_directory is not None:
        write_evidence_manifest(evidence, "opening", artifact, manifest_directory)
    return artifact


def generate_closing_report_pdf(
    client: BinancePublicClient,
    output_directory: Path | str,
    session_date: date | None = None,
    interval: str = "1h",
    market: str = "spot",
    manifest_directory: Path | str | None = None,
) -> Path:
    evidence = acquire_session_report_evidence(client, session_date, interval, market)
    artifact = build_closing_report_pdf(evidence, output_directory)
    if manifest_directory is not None:
        write_evidence_manifest(evidence, "closing", artifact, manifest_directory)
    return artifact
