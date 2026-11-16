"""Adapter from Binance market-window evidence to local-time PDF reports."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.engine import CORE_SYMBOLS
from binance_data_engine.session import acquire_market_window

from .intraday import build_intraday_snapshot_pdf
from .context import collect_market_context
from .evidence import write_evidence_manifest
from .timezone import (
    REPORT_TIMEZONE, LOCAL_TZ, current_local_report_date, local_day_window,
)


def acquire_intraday_evidence(
    client: BinancePublicClient,
    cutoff_utc: datetime | None = None,
    interval: str = "1h",
    market: str = "spot",
    symbols: tuple[str, ...] = CORE_SYMBOLS,
    *,
    cutoff_local: datetime | None = None,
    report_date_local=None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Acquire Dominican midnight through the exact local cutoff.

    If no cutoff is provided, execution-time Dominican local time is used.
    The final incomplete candle is excluded; the requested cutoff remains in
    the report and evidence manifest.
    """
    if cutoff_utc is not None and cutoff_local is not None:
        raise ValueError("Specify cutoff_utc or cutoff_local, not both")
    if cutoff_utc is not None:
        if not isinstance(cutoff_utc, datetime) or cutoff_utc.tzinfo is None or cutoff_utc.utcoffset() != timezone.utc.utcoffset(cutoff_utc):
            raise ValueError("cutoff_utc must be a timezone-aware UTC datetime")
        resolved_local = cutoff_utc.astimezone(LOCAL_TZ)
        target_date = report_date_local or resolved_local.date()
        cutoff = resolved_local
    elif cutoff_local is not None:
        if not isinstance(cutoff_local, datetime):
            raise ValueError("cutoff_local must be a datetime")
        resolved_local = cutoff_local.replace(tzinfo=LOCAL_TZ) if cutoff_local.tzinfo is None else cutoff_local.astimezone(LOCAL_TZ)
        target_date = report_date_local or resolved_local.date()
        cutoff = resolved_local
    else:
        resolved_now = now or datetime.now(LOCAL_TZ)
        resolved_local = resolved_now.astimezone(LOCAL_TZ) if resolved_now.tzinfo else resolved_now.replace(tzinfo=LOCAL_TZ)
        target_date = report_date_local or resolved_local.date()
        cutoff = None

    window = local_day_window(target_date, cutoff, now=now if cutoff is None else None)
    report = acquire_market_window(
        client=client,
        window_start_utc=window.start_utc,
        cutoff_utc=window.end_utc,
        interval=interval,
        market=market,
        symbols=symbols,
        window_metadata=window.as_dict(),
    )
    report["window_start_utc"] = window.start_utc.isoformat().replace("+00:00", "Z")
    report["cutoff_utc"] = window.end_utc.isoformat().replace("+00:00", "Z")
    if datetime.now(timezone.utc) < window.end_utc:
        raise ValueError("Local system clock is behind the requested cutoff; refusing to misstate generation time")
    context = collect_market_context(window.start_utc, window.end_utc)
    report.update(context)
    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report["news_context"] = context["news"]
    if market == "usdm":
        report["derivatives_context"] = {
            symbol: item.get("derivatives", {}) for symbol, item in report["symbols"].items()
        }
    report["binance_account_data_status"] = "unavailable"
    report["us_equity_market_data_status"] = "not_integrated"
    report["us_equity_session_state"] = "not_available"
    report["comparison_basis"] = "Dominican local calendar day; rolling 24-hour ticker is shown separately."
    report["limitations"] = (
        "Private Binance account balances, positions, fees, funding, and flow-adjusted PnL are unavailable. "
         "Full U.S. equity-market coverage, premarket/regular/postmarket classification, and exchange-calendar evidence are not integrated or verified. "
        + context["context_limitations"]
    )
    bullish, bearish = [], []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        candles = report["symbols"][symbol]["candles"]
        high = max(Decimal(candle["high"]) for candle in candles)
        low = min(Decimal(candle["low"]) for candle in candles)
        last = candles[-1]["close"]
        bullish.append(
            f"{symbol}: continuation requires acceptance above observed high {format(high, 'f')}; "
            f"invalidation reference below observed low {format(low, 'f')}. Last fully closed candle: {last}."
        )
        bearish.append(
            f"{symbol}: weakness requires acceptance below observed low {format(low, 'f')}; "
            f"invalidation reference above observed high {format(high, 'f')}. Last fully closed candle: {last}."
        )
    report["bullish_scenario"] = " ".join(bullish) + " Conditional levels only; no probability or target is inferred."
    report["bearish_scenario"] = " ".join(bearish) + " Conditional levels only; no probability or target is inferred."
    report["risk_factors"] = (
        "False breakouts, liquidity changes, volatility expansion, spread/slippage, and events "
        "not represented in the configured feeds may invalidate these reference levels."
    )
    report["executive_summary"] = (
        f"Dominican local-day snapshot for {target_date.isoformat()} through {window.end_local.isoformat()}. "
        "BTCUSDT and ETHUSDT fully closed candles were checked for window boundaries, pagination, "
        "and data integrity. The last incomplete interval is excluded."
    )
    return report


def generate_intraday_snapshot_pdf(
    client: BinancePublicClient,
    cutoff_utc: datetime | None,
    output_directory: Path | str,
    interval: str = "1h",
    market: str = "spot",
    manifest_directory: Path | str | None = None,
    *,
    cutoff_local: datetime | None = None,
) -> Path:
    """Acquire, validate, and render a Dominican local-day intraday PDF."""
    evidence = acquire_intraday_evidence(
        client, cutoff_utc=cutoff_utc, interval=interval, market=market,
        cutoff_local=cutoff_local,
    )
    artifact = build_intraday_snapshot_pdf(evidence, output_directory)
    if manifest_directory is not None:
        try:
            write_evidence_manifest(evidence, "intraday", artifact, manifest_directory)
        except Exception:
            artifact.unlink(missing_ok=True)
            raise
    return artifact
