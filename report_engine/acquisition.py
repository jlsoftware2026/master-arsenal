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
from .us_market_calendar import classify_us_equity_session
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
    calendar_evidence = classify_us_equity_session(window.end_utc)
    report["us_equity_calendar"] = calendar_evidence
    report["us_equity_session_state"] = (
        calendar_evidence["session_state"] if calendar_evidence["status"] == "ok"
        else "not_available"
    )
    report["us_equity_calendar_reference"] = "exact_intraday_cutoff"
    report["comparison_basis"] = "Día calendario dominicano; el cambio del ticker móvil de 24 horas se muestra por separado."
    report["limitations"] = (
        "Los saldos, posiciones, comisiones, financiación y PnL ajustado por flujos de la cuenta privada de Binance no están disponibles. "
         "La cobertura de precios del mercado bursátil estadounidense no está integrada; el calendario XNYS clasifica la sesión y sus feriados/horarios, pero no aporta precios. "
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
    summary_points = [
        f"Ventana intradía local: {target_date.isoformat()} desde medianoche hasta {window.end_local.isoformat()} ({REPORT_TIMEZONE}); "
        f"el corte es exclusivo y no se incluyen velas posteriores."
    ]
    for symbol in ("BTCUSDT", "ETHUSDT"):
        item = report["symbols"][symbol]
        performance = item.get("performance") or {}
        change = performance.get("change_percent")
        change_text = f"{change}%" if change is not None else "no disponible"
        summary_points.append(
            f"{symbol}: variación observada desde medianoche {change_text}; "
            f"rango {performance.get('low', 'N/D')}–{performance.get('high', 'N/D')}; "
            f"último cierre completo {performance.get('close', 'N/D')}."
        )
    ticker_parts = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        ticker = report["symbols"][symbol].get("ticker_24h") or {}
        ticker_data = ticker.get("data", ticker) if isinstance(ticker, dict) else {}
        change_24h = ticker_data.get("priceChangePercent") if isinstance(ticker_data, dict) else None
        ticker_parts.append(f"{symbol}: {change_24h}%" if change_24h is not None else f"{symbol}: no disponible")
    summary_points.append(
        "Variación móvil de 24 horas, separada del rendimiento desde medianoche local: " + "; ".join(ticker_parts) + "."
    )
    indicator_parts = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        item = report["symbols"][symbol]
        indicators = item.get("indicators") or {}
        indicator_parts.append(
            f"{symbol} EMA20={indicators.get('ema_20', 'N/D')}, "
            f"EMA50={indicators.get('ema_50', 'N/D')}, RSI14={indicators.get('rsi_14', 'N/D')} "
            f"({item.get('candle_count', 0)} velas locales)"
        )
    summary_points.append("Indicadores y cobertura de velas: " + "; ".join(indicator_parts) + ".")
    feeds = report.get("context_sources") or []
    available_feeds = sum(1 for item in feeds if isinstance(item, dict) and item.get("status") == "ok")
    summary_points.append(
        f"Contexto macroeconómico/noticias: {available_feeds} de {len(feeds)} feeds consultados con estado correcto; "
        "los titulares son contexto, no prueba de causalidad."
    )
    summary_points.append(
        "Estado bursátil XNYS al corte: "
        + (f"{calendar_evidence['session_state']} ({calendar_evidence['as_of_et']}); "
           f"última sesión {calendar_evidence['last_completed_session_date']}; "
           f"próxima sesión {calendar_evidence['next_session_date']}."
           if calendar_evidence["status"] == "ok"
           else "no disponible; no se infiere el estado.")
        + " La cuenta privada Binance y los precios/indicadores del mercado bursátil estadounidense siguen sin integrarse."
    )
    report["executive_summary"] = summary_points
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
