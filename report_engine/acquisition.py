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
    cutoff_resolution = "explicit_utc_cutoff"
    if cutoff_utc is not None:
        if not isinstance(cutoff_utc, datetime) or cutoff_utc.tzinfo is None or cutoff_utc.utcoffset() != timezone.utc.utcoffset(cutoff_utc):
            raise ValueError("cutoff_utc must be a timezone-aware UTC datetime")
        resolved_local = cutoff_utc.astimezone(LOCAL_TZ)
        target_date = report_date_local or resolved_local.date()
        cutoff = resolved_local
    elif cutoff_local is not None:
        cutoff_resolution = "explicit_local_cutoff"
        if not isinstance(cutoff_local, datetime):
            raise ValueError("cutoff_local must be a datetime")
        resolved_local = cutoff_local.replace(tzinfo=LOCAL_TZ) if cutoff_local.tzinfo is None else cutoff_local.astimezone(LOCAL_TZ)
        target_date = report_date_local or resolved_local.date()
        cutoff = resolved_local
    else:
        cutoff_resolution = "execution_time_local_default"
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
    report["cutoff_resolution"] = cutoff_resolution
    report["requested_report_date_local"] = target_date.isoformat()
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
    report["comparison_basis"] = "Día calendario dominicano; el cambio del ticker móvil de 24 horas se muestra por separado."
    report["limitations"] = (
        "Los saldos, posiciones, comisiones, financiación y PnL ajustado por flujos de la cuenta privada de Binance no están disponibles. "
         "La cobertura completa del mercado bursátil estadounidense, la clasificación premercado/regular/posmercado y la evidencia del calendario bursátil no están integradas ni verificadas. "
        + context["context_limitations"]
    )
    bullish, bearish = [], []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        candles = report["symbols"][symbol]["candles"]
        high = max(Decimal(candle["high"]) for candle in candles)
        low = min(Decimal(candle["low"]) for candle in candles)
        last = candles[-1]["close"]
        bullish.append(
            f"{symbol}: la continuación requiere aceptación por encima del máximo observado {format(high, 'f')}; "
            f"referencia de invalidación por debajo del mínimo observado {format(low, 'f')}. Última vela completamente cerrada: {last}."
        )
        bearish.append(
            f"{symbol}: la debilidad requiere aceptación por debajo del mínimo observado {format(low, 'f')}; "
            f"referencia de invalidación por encima del máximo observado {format(high, 'f')}. Última vela completamente cerrada: {last}."
        )
    report["bullish_scenario"] = " ".join(bullish) + " Solo niveles condicionales; no se infieren probabilidades ni objetivos."
    report["bearish_scenario"] = " ".join(bearish) + " Solo niveles condicionales; no se infieren probabilidades ni objetivos."
    report["risk_factors"] = (
        "Las rupturas falsas, los cambios de liquidez, la expansión de volatilidad, el spread/deslizamiento y los eventos "
        "no representados en los feeds configurados pueden invalidar estos niveles de referencia."
    )
    report["executive_summary"] = (
        f"Snapshot del día calendario dominicano {target_date.isoformat()} hasta {window.end_local.isoformat()}. "
        "Se verificaron las velas completamente cerradas de BTCUSDT y ETHUSDT respecto a los límites de la ventana, la paginación "
        "y la integridad de los datos. El último intervalo incompleto se excluye."
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
