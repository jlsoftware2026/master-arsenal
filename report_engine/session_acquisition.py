"""Acquisition-to-PDF adapters using Dominican local calendar-day windows."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from binance_data_engine.client import BinancePublicClient
from binance_data_engine.session import acquire_market_window
from .context import collect_market_context
from .evidence import write_evidence_manifest
from .session import build_closing_report_pdf, build_opening_report_pdf
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
    report["us_equity_session_state"] = "not_available"
    report["opening_forecast_scorecard_status"] = (
        "not_implemented" if report_kind == "closing" else "not_applicable"
    )
    report["activation_timing_status"] = "not_automated"
    report["source_skill_limitations"] = [
        "Los saldos, posiciones, comisiones, financiación y PnL ajustado por flujos de la cuenta privada de Binance no están disponibles; las velas públicas del mercado no son datos de cuenta.",
        "Los índices bursátiles estadounidenses, VIX, tasas, DXY, materias primas, amplitud sectorial y calendario bursátil completo no están integrados ni verificados.",
        "El horario de activación de apertura/cierre no está automatizado; la comparación del pronóstico de apertura con el cierre de esa misma fecha no está implementada.",
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
    report["executive_summary"] = (
        "Referencia de Binance: {period_label} ({target_date.isoformat()} {REPORT_TIMEZONE}). "
        "Rendimiento observado (desde la apertura de la primera vela hasta el cierre de la última vela completa): "
        + "; ".join(changes)
        + ". Mediciones descriptivas únicamente; no se infieren causas ni pronósticos."
    )
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
        "El contexto RSS está limitado por fecha, pero no es exhaustivo. La cobertura completa del mercado bursátil estadounidense, "
        "el análisis de la cuenta privada de Binance y la activación automática de apertura/cierre "
        "no están disponibles en esta versión. La comparación del pronóstico de apertura con el cierre de esa misma fecha no está implementada. "
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
    artifact = build_closing_report_pdf(evidence, output_directory)
    if manifest_directory is not None:
        try:
            write_evidence_manifest(evidence, "closing", artifact, manifest_directory)
        except Exception:
            artifact.unlink(missing_ok=True)
            raise
    return artifact
