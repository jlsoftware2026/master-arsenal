"""Acquisition-to-PDF adapters using Dominican local calendar-day windows."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.session import acquire_market_window
from .context import collect_market_context
from .evidence import write_evidence_manifest
from .session import build_closing_report_pdf, build_opening_report_pdf
from .scorecard import build_opening_forecast_scorecard
from .us_market_calendar import classify_us_equity_session
from .timezone import (
    LOCAL_TZ, REPORT_TIMEZONE, completed_local_day, current_local_report_date,
    local_day_window, opening_reference_date,
)


def acquire_session_report_evidence(
    client: BinancePublicClient,
    session_date: date | None = None,
    interval: str = "1h",
    market: str = "spot",
    *,
    report_kind: str = "completed",
    cutoff_local: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Acquire opening, closing, or completed local-day evidence.

    For opening, session_date is the local request date and the Binance
    reference is its previous Dominican calendar day. For closing, session_date
    is the local report date and cutoff_local defaults to execution time.
    """
    if report_kind not in {"opening", "closing", "completed"}:
        raise ValueError("report_kind must be opening, closing, or completed")
    if cutoff_local is not None and report_kind != "closing":
        raise ValueError("cutoff_local is supported only for closing reports")
    execution_now = now or datetime.now(LOCAL_TZ)
    request_date = session_date or current_local_report_date(execution_now)
    if not isinstance(request_date, date) or isinstance(request_date, datetime):
        raise ValueError("session_date must be datetime.date")
    if report_kind == "opening":
        target_date = opening_reference_date(request_date)
        window = completed_local_day(target_date)
    elif report_kind == "closing":
        target_date = request_date
        execution_date = current_local_report_date(execution_now)
        if cutoff_local is None and target_date < execution_date:
            window = completed_local_day(target_date)
        else:
            window = local_day_window(target_date, cutoff_local, now=execution_now)
    else:
        target_date = request_date
        window = completed_local_day(target_date)

    report = acquire_market_window(
        client,
        window.start_utc,
        window.end_utc,
        interval=interval,
        market=market,
        window_metadata=window.as_dict(),
    )
    report["session_start_utc"] = report["window_start_utc"]
    report["session_end_utc"] = report["cutoff_utc"]
    report["report_kind"] = report_kind
    report["requested_report_date_local"] = request_date.isoformat()
    report["report_date_local"] = target_date.isoformat()
    report["cutoff_resolution"] = (
        "previous_local_calendar_day" if report_kind == "opening" else
        "explicit_local_cutoff" if cutoff_local is not None else
        "execution_time_local_default" if report_kind == "closing" and target_date == current_local_report_date(execution_now) else
        "completed_historical_local_day"
    )
    report["report_timezone"] = REPORT_TIMEZONE
    report["binance_account_data_status"] = "unavailable"
    report["us_equity_market_data_status"] = "not_integrated"
    eastern = ZoneInfo("America/New_York")
    if report_kind == "opening":
        calendar_reference = datetime.combine(request_date, time(9, 10), tzinfo=eastern)
        report["us_equity_calendar_reference"] = "opening_pre_market_reference_09:10_ET"
    elif window.is_partial:
        calendar_reference = window.end_local
        report["us_equity_calendar_reference"] = "exact_local_report_cutoff"
    else:
        calendar_reference = datetime.combine(target_date, time(16, 20), tzinfo=eastern)
        report["us_equity_calendar_reference"] = "post_close_reference_16:20_ET"
    calendar_evidence = classify_us_equity_session(calendar_reference)
    report["us_equity_calendar"] = calendar_evidence
    report["us_equity_session_state"] = (
        calendar_evidence["session_state"] if calendar_evidence["status"] == "ok"
        else "not_available"
    )
    report["opening_forecast_scorecard_status"] = (
        "not_verified" if report_kind == "closing" else "not_applicable"
    )
    report["activation_timing_status"] = "not_automated"
    report["source_skill_limitations"] = [
        "Los saldos, posiciones, comisiones, financiación y PnL ajustado por flujos de la cuenta privada de Binance no están disponibles; las velas públicas del mercado no son datos de cuenta.",
        "Los índices bursátiles estadounidenses, VIX, tasas, DXY, materias primas y amplitud sectorial no están integrados; el calendario XNYS se consulta por separado y puede quedar no disponible si falla su proveedor.",
        "El horario de activación de apertura/cierre no está automatizado; el scorecard compara escenarios solo cuando existe un manifiesto de apertura íntegro de la misma fecha.",
    ]

    changes = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        performance = report["symbols"][symbol]["performance"]
        value = performance.get("change_percent")
        changes.append(
            f"{symbol}: variación de {value}% desde la primera apertura observada hasta la última vela completamente cerrada"
            if value is not None else f"{symbol}: variación porcentual no disponible"
        )
    period_label = "día calendario local anterior" if report_kind == "opening" else (
        "día calendario local parcial hasta la hora de corte indicada" if window.is_partial
        else "día calendario local completado"
    )
    summary_points = [
        f"Referencia Binance: {period_label} ({target_date.isoformat()}, {REPORT_TIMEZONE}); ventana local {window.start_local.isoformat()} a {window.end_local.isoformat()}.",
    ]
    for symbol in ("BTCUSDT", "ETHUSDT"):
        item = report["symbols"][symbol]
        performance = item["performance"]
        change = performance.get("change_percent")
        change_text = f"{change}%" if change is not None else "no disponible"
        summary_points.append(
            f"{symbol}: variación observada {change_text}; rango {performance.get('low')}–{performance.get('high')}; "
            f"último cierre completo {performance.get('close')}."
        )
    summary_points.append(
        "Calidad de datos: BTCUSDT "
        f"{report['symbols']['BTCUSDT'].get('candle_count', 0)} velas y ETHUSDT "
        f"{report['symbols']['ETHUSDT'].get('candle_count', 0)} velas; se excluyen las velas incompletas."
    )
    indicator_parts = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        indicators = report["symbols"][symbol].get("indicators") or {}
        indicator_parts.append(
            f"{symbol} EMA20={indicators.get('ema_20', 'N/D')}, "
            f"EMA50={indicators.get('ema_50', 'N/D')}, RSI14={indicators.get('rsi_14', 'N/D')}"
        )
    summary_points.append("Indicadores técnicos calculados: " + "; ".join(indicator_parts) + ".")
    feeds = report.get("context_sources") or []
    available_feeds = sum(1 for item in feeds if isinstance(item, dict) and item.get("status") == "ok")
    summary_points.append(
        f"Contexto macroeconómico/noticias: {available_feeds} de {len(feeds)} feeds consultados con estado correcto; "
        "los titulares son contexto y no prueban causalidad."
    )
    summary_points.append(
        "Calendario bursátil XNYS: "
        + (f"{calendar_evidence['session_state']} a {calendar_evidence['as_of_et']}; "
           f"última sesión completada {calendar_evidence['last_completed_session_date']}; "
           f"próxima sesión {calendar_evidence['next_session_date']}."
           if calendar_evidence["status"] == "ok"
           else "no disponible; no se infiere el estado bursátil.")
        + " La cobertura de índices/indicadores estadounidenses y los datos privados de cuenta Binance "
          "siguen sin integrarse; la activación automática tampoco está implementada."
    )
    report["executive_summary"] = summary_points
    report["technical_analysis"] = (
        "Los indicadores utilizan una serie independiente de calentamiento previa a la ventana y velas completamente cerradas "
        "de la ventana del informe. Las velas de calentamiento se excluyen del rendimiento del período y de los gráficos."
    )
    bullish, bearish = [], []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        performance = report["symbols"][symbol]["performance"]
        high, low, close = performance["high"], performance["low"], performance["close"]
        bullish.append(
            f"{symbol}: la continuación alcista depende de la aceptación por encima del máximo observado {high}; "
            f"el escenario se invalida por debajo del mínimo observado {low}. Último cierre: {close}."
        )
        bearish.append(
            f"{symbol}: la continuación bajista depende de la aceptación por debajo del mínimo observado {low}; "
            f"el escenario se invalida por encima del máximo observado {high}. Último cierre: {close}."
        )
    report["bullish_scenario"] = " ".join(bullish) + " Niveles de referencia condicionales, no objetivos ni probabilidades."
    report["bearish_scenario"] = " ".join(bearish) + " Niveles de referencia condicionales, no objetivos ni probabilidades."
    report["assumptions_and_invalidation"] = (
        "La aceptación de una ruptura requiere confirmación independiente de la acción del precio y del volumen actuales. "
        "Los extremos opuestos del período son referencias simples de invalidación; no se infiere ningún objetivo ni probabilidad."
    )
    report["risks"] = (
        "Las rupturas falsas, la baja liquidez, los choques de volatilidad, el spread/deslizamiento y los eventos fuera "
        "de los feeds configurados pueden invalidar estos escenarios de referencia."
    )
    context = collect_market_context(window.start_utc, window.end_utc)
    report.update(context)
    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report["limitations"] = (
        "El contexto RSS está limitado por fecha, pero no es exhaustivo. El calendario XNYS se integra solo para horario/feriados "
        "y no aporta precios; la cobertura completa del mercado bursátil estadounidense, el análisis de la cuenta privada de Binance "
        "y la activación automática de apertura/cierre "
        "no están disponibles en esta versión. El scorecard de apertura/cierre depende de un manifiesto íntegro de apertura de la misma fecha. "
        + context.get("context_limitations", "No se suministraron limitaciones de los feeds.")
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
    evidence = acquire_session_report_evidence(
        client, session_date, interval, market, report_kind="opening"
    )
    artifact = build_opening_report_pdf(evidence, output_directory)
    if manifest_directory is not None:
        try:
            write_evidence_manifest(evidence, "opening", artifact, manifest_directory)
        except Exception:
            artifact.unlink(missing_ok=True)
            raise
    return artifact


def generate_closing_report_pdf(
    client: BinancePublicClient,
    output_directory: Path | str,
    session_date: date | None = None,
    interval: str = "1h",
    market: str = "spot",
    manifest_directory: Path | str | None = None,
    cutoff_local: datetime | None = None,
) -> Path:
    evidence = acquire_session_report_evidence(
        client, session_date, interval, market,
        report_kind="closing", cutoff_local=cutoff_local,
    )
    scorecard = build_opening_forecast_scorecard(evidence, manifest_directory)
    evidence["opening_forecast_scorecard"] = scorecard
    evidence["opening_forecast_scorecard_status"] = scorecard["status"]
    evidence["limitations"] = (
        evidence.get("limitations", "") + " Scorecard apertura/cierre: "
        + scorecard["status"] + ". " + scorecard.get("reason", scorecard.get("limitations", ""))
    )
    artifact = build_closing_report_pdf(evidence, output_directory)
    if manifest_directory is not None:
        try:
            write_evidence_manifest(evidence, "closing", artifact, manifest_directory)
        except Exception:
            artifact.unlink(missing_ok=True)
            raise
    return artifact
