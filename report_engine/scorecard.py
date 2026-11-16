"""Same-date opening-scenario reconciliation for closing reports."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .evidence import audit_evidence_manifest


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} is not a valid decimal value") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def build_opening_forecast_scorecard(
    closing_report: dict[str, Any],
    manifest_directory: str | Path | None,
) -> dict[str, Any]:
    """Compare same-date opening range scenarios with closing-session evidence.

    This is a deterministic range-breakout reconciliation, not a profitability
    score, probability estimate, or proof that a trade was executable.
    """
    if not isinstance(closing_report, dict):
        raise ValueError("closing_report must be an object")
    report_date = closing_report.get("requested_report_date_local")
    if not isinstance(report_date, str):
        raise ValueError("closing report must declare requested_report_date_local")
    if manifest_directory is None:
        return {
            "status": "not_verified",
            "report_date_local": report_date,
            "reason": "No evidence-manifest directory was configured; opening-report existence cannot be checked.",
        }

    directory = Path(manifest_directory).expanduser().resolve()
    opening_path = (directory / f"apertura-mercado_{report_date}.evidence.json").resolve()
    if not opening_path.is_relative_to(directory):
        return {
            "status": "failed", "report_date_local": report_date,
            "reason": "Opening evidence path escaped the configured manifest directory.",
        }
    if not opening_path.is_file():
        return {
            "status": "not_applicable",
            "report_date_local": report_date,
            "reason": "No same-date opening report manifest exists; no opening scenario was available to score.",
        }
    if opening_path.stat().st_size > 50_000_000:
        return {
            "status": "failed", "report_date_local": report_date,
            "reason": "Opening evidence manifest exceeds the 50 MB safety limit.",
        }

    workspace_root = directory.parent.parent
    audit = audit_evidence_manifest(opening_path, workspace_root)
    if audit.get("status") != "passed":
        return {
            "status": "failed", "report_date_local": report_date,
            "opening_manifest": opening_path.name,
            "reason": "Opening evidence failed independent integrity checks: " + "; ".join(audit.get("findings", [])),
        }

    payload = json.loads(opening_path.read_text(encoding="utf-8"))
    opening = payload.get("report")
    try:
        expected_reference_date = (date.fromisoformat(report_date) - timedelta(days=1)).isoformat()
        opening_generated = datetime.fromisoformat(opening["generated_at_utc"].replace("Z", "+00:00"))
        closing_generated = datetime.fromisoformat(closing_report["generated_at_utc"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError):
        return {
            "status": "failed", "report_date_local": report_date,
            "opening_manifest": opening_path.name,
            "reason": "Opening/closing report dates or generation timestamps are missing or invalid.",
        }
    if (
        payload.get("report_type") != "opening"
        or not isinstance(opening, dict)
        or opening.get("requested_report_date_local") != report_date
        or opening.get("report_timezone") != "America/Santo_Domingo"
        or opening.get("report_date_local") != expected_reference_date
        or opening.get("cutoff_resolution") != "previous_local_calendar_day"
        or opening.get("is_partial") is not False
        or closing_report.get("report_date_local") != report_date
        or opening_generated.tzinfo is None
        or opening_generated.utcoffset() != timedelta(0)
        or closing_generated.tzinfo is None
        or closing_generated.utcoffset() != timedelta(0)
        or opening_generated.astimezone(timezone.utc) > closing_generated.astimezone(timezone.utc)
    ):
        return {
            "status": "failed", "report_date_local": report_date,
            "opening_manifest": opening_path.name,
            "reason": "Opening manifest type, request date, or completed-day status does not match the closing report.",
        }

    opening_symbols = opening.get("symbols")
    closing_symbols = closing_report.get("symbols")
    if not isinstance(opening_symbols, dict) or not isinstance(closing_symbols, dict):
        return {
            "status": "failed", "report_date_local": report_date,
            "opening_manifest": opening_path.name,
            "reason": "Opening or closing symbol evidence is missing.",
        }

    results: dict[str, Any] = {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        opened = opening_symbols.get(symbol)
        closed = closing_symbols.get(symbol)
        if not isinstance(opened, dict) or not isinstance(closed, dict):
            return {
                "status": "failed", "report_date_local": report_date,
                "opening_manifest": opening_path.name,
                "reason": f"Mandatory {symbol} evidence is missing from opening or closing report.",
            }
        opening_performance = opened.get("performance")
        closing_performance = closed.get("performance")
        if not isinstance(opening_performance, dict) or not isinstance(closing_performance, dict):
            return {
                "status": "failed", "report_date_local": report_date,
                "opening_manifest": opening_path.name,
                "reason": f"{symbol} performance evidence is missing.",
            }
        try:
            reference_high = _decimal(opening_performance["high"], f"{symbol} opening high")
            reference_low = _decimal(opening_performance["low"], f"{symbol} opening low")
            closing_high = _decimal(closing_performance["high"], f"{symbol} closing high")
            closing_low = _decimal(closing_performance["low"], f"{symbol} closing low")
            closing_price = _decimal(closing_performance["close"], f"{symbol} closing close")
        except (KeyError, ValueError) as exc:
            return {
                "status": "failed", "report_date_local": report_date,
                "opening_manifest": opening_path.name,
                "reason": f"{symbol} scorecard evidence is invalid: {exc}",
            }
        if reference_high < reference_low or closing_high < closing_low:
            return {
                "status": "failed", "report_date_local": report_date,
                "opening_manifest": opening_path.name,
                "reason": f"{symbol} OHLC range is internally inconsistent.",
            }

        upside_breach = closing_high > reference_high
        downside_breach = closing_low < reference_low
        close_above = closing_price > reference_high
        close_below = closing_price < reference_low
        if close_above:
            outcome = "Ruptura alcista confirmada por cierre sobre el máximo de referencia."
        elif close_below:
            outcome = "Ruptura bajista confirmada por cierre bajo el mínimo de referencia."
        elif upside_breach and downside_breach:
            outcome = "Ambos extremos fueron superados intradía; el cierre quedó dentro del rango."
        elif upside_breach:
            outcome = "Ruptura alcista intradía sin confirmación al cierre."
        elif downside_breach:
            outcome = "Ruptura bajista intradía sin confirmación al cierre."
        else:
            outcome = "Rango de referencia conservado; no hubo ruptura observada."

        results[symbol] = {
            "opening_reference_high": str(reference_high),
            "opening_reference_low": str(reference_low),
            "closing_high": str(closing_high),
            "closing_low": str(closing_low),
            "closing_close": str(closing_price),
            "upside_range_breach": upside_breach,
            "downside_range_breach": downside_breach,
            "close_above_opening_high": close_above,
            "close_below_opening_low": close_below,
            "outcome": outcome,
        }

    return {
        "status": "passed",
        "report_date_local": report_date,
        "opening_manifest": opening_path.name,
        "opening_pdf_filename": payload.get("pdf_filename"),
        "opening_pdf_sha256": payload.get("pdf_sha256"),
        "opening_reference_date_local": opening.get("report_date_local"),
        "opening_generated_at_utc": opening.get("generated_at_utc"),
        "closing_generated_at_utc": closing_report.get("generated_at_utc"),
        "closing_report_date_local": closing_report.get("report_date_local"),
        "comparison_basis": "Rango alto/bajo del día de referencia de apertura frente a máximo/mínimo/cierre del día local de cierre.",
        "symbols": results,
        "limitations": (
            "La evaluación identifica rupturas de rango y ubicación del cierre. No mide rentabilidad, "
            "probabilidad, ejecución, deslizamiento ni calidad predictiva; no constituye un backtest."
        ),
    }
