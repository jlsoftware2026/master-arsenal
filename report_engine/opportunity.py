"""Standalone pre-investment opportunity PDF composer."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from .pdf import data_table, key_value_table, paragraph, report_styles, section_heading, write_pdf_atomic
from .qa import inspect_pdf_artifact

CONCLUSIONS_ES = {
    "potential_candidate_for_further_diligence": "Candidato potencial para diligencia adicional",
    "wait_for_confirmation": "Esperar confirmación",
    "insufficient_evidence": "Evidencia insuficiente",
    "avoid_for_now": "Evitar por ahora",
}


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def _text(value: Any) -> str:
    if value is None:
        return "No suministrado"
    if isinstance(value, list):
        return "; ".join(_text(item) for item in value) if value else "Ninguno"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_text(item)}" for key, item in value.items())
    return str(value)


def _safe_component(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    value = value.strip("-.")
    if not value:
        raise ValueError("Instrument name/symbol cannot form a safe report filename")
    return value[:64]


def _validate(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], datetime]:
    if not isinstance(report, dict):
        raise ValueError("Opportunity report input must be an object")
    generated = _utc(report.get("generated_at_utc"), "generated_at_utc")
    instrument = report.get("instrument")
    if not isinstance(instrument, dict):
        raise ValueError("instrument must be a normalized instrument record")
    key = instrument.get("instrument_key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("instrument.instrument_key is required")
    if instrument.get("asset_class") not in {"listed_equity", "tokenized_equity", "crypto"}:
        raise ValueError("instrument.asset_class is unsupported")
    packet = report.get("research_packet")
    if not isinstance(packet, dict) or packet.get("schema") != "ma.investment-research/v1":
        raise ValueError("research_packet must use schema ma.investment-research/v1")
    if packet.get("instrument_key") != key:
        raise ValueError("research_packet instrument_key does not match instrument")
    facts = packet.get("facts")
    if not isinstance(facts, list):
        raise ValueError("research_packet.facts must be a list")
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict) or fact.get("instrument_key") != key:
            raise ValueError(f"research fact {index} does not match instrument identity")
    conclusion = report.get("conclusion")
    if conclusion not in CONCLUSIONS_ES:
        raise ValueError(f"conclusion must be one of: {', '.join(CONCLUSIONS_ES)}")
    packet_quality = (packet.get("data_quality") or {}).get("status")
    if packet_quality == "insufficient_evidence" and conclusion == "potential_candidate_for_further_diligence":
        raise ValueError("insufficient evidence cannot support a potential-candidate conclusion")
    scenarios = report.get("scenarios")
    if scenarios is not None:
        if not isinstance(scenarios, dict) or scenarios.get("schema") != "ma.price-scenarios/v1":
            raise ValueError("scenarios must use schema ma.price-scenarios/v1")
        if scenarios.get("instrument_key") != key:
            raise ValueError("scenario instrument_key does not match instrument")
        if scenarios.get("probabilities") is not None or scenarios.get("expected_return") is not None:
            raise ValueError("scenario report must not contain invented probabilities or expected return")
    sizing = report.get("position_sizing")
    if sizing is not None:
        if not isinstance(sizing, dict) or sizing.get("schema") != "ma.cash-position-size/v1":
            raise ValueError("position_sizing must use schema ma.cash-position-size/v1")
        if sizing.get("instrument_key") != key:
            raise ValueError("position sizing instrument_key does not match instrument")
        if sizing.get("analysis_type") != "hypothetical_cash_only":
            raise ValueError("position sizing must be explicitly hypothetical and cash-only")
    return instrument, packet, generated


def build_opportunity_report_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Render a source-attributed opportunity report from validated structured evidence."""
    instrument, packet, generated = _validate(report)
    asset = _safe_component(instrument.get("asset_class", "asset"))
    symbol = _safe_component(instrument.get("symbol", "candidate"))
    report_date = generated.strftime("%Y-%m-%d")
    destination = Path(output_directory) / f"oportunidad-{asset}-{symbol}_{report_date}.pdf"
    styles = report_styles()
    venue = instrument.get("venue_verification") or {"status": "not_verified"}
    venue_status = venue.get("status", "not_verified")
    conclusion = report["conclusion"]
    facts = packet.get("facts") or []
    data_quality = packet.get("data_quality") or {}
    story = [
        Paragraph("Informe de oportunidad de inversión", styles["title"]),
        Paragraph("Diligencia preinversión basada en evidencia y supuestos explícitos", styles["subtitle"]),
        key_value_table([
            ("Activo / instrumento", _text(instrument.get("name"))),
            ("Símbolo", _text(instrument.get("symbol"))),
            ("Clase de activo", _text(instrument.get("asset_class"))),
            ("Identificador interno", instrument["instrument_key"]),
            ("Moneda de cotización", _text(instrument.get("quote_currency"))),
            ("Emisor / protocolo", _text(instrument.get("issuer") or instrument.get("underlying_issuer") or instrument.get("protocol"))),
            ("Bolsa / red", _text(instrument.get("exchange") or instrument.get("network"))),
            ("Venue / producto", _text(instrument.get("venue"))),
            ("Verificación de disponibilidad", _text(venue_status)),
            ("Evidencia del venue observada en UTC", _text(venue.get("observed_at_utc"))),
            ("Conclusión de diligencia", CONCLUSIONS_ES[conclusion]),
            ("Calidad del paquete de evidencia", _text(data_quality.get("status"))),
            ("Hechos registrados", str(packet.get("fact_count", len(facts)))),
            ("Generado en UTC", generated.isoformat().replace("+00:00", "Z")),
        ], styles),
        Spacer(1, 3 * mm),
        section_heading("Resumen ejecutivo", styles),
    ]
    executive = report.get("executive_summary") or []
    if isinstance(executive, list):
        for item in executive[:10]:
            story.append(paragraph(f"• {_text(item)}", styles["body"]))
    else:
        story.append(paragraph(_text(executive), styles["body"]))

    story.extend([
        section_heading("Cobertura y calidad de evidencia", styles),
        paragraph(
            f"Estado: {_text(data_quality.get('status'))}. "
            f"Dimensiones cubiertas: {_text(packet.get('dimensions_covered'))}. "
            f"Hechos obsoletos: {_text(data_quality.get('stale_fact_ids'))}. "
            f"Hechos futuros: {_text(data_quality.get('future_dated_fact_ids'))}. "
            f"Hechos disputados: {_text(data_quality.get('disputed_fact_ids'))}. "
            f"Hechos no verificados: {_text(data_quality.get('unverified_fact_ids'))}.",
            styles["body"],
        ),
    ])
    if facts:
        fact_rows = []
        for fact in facts:
            freshness = fact.get("freshness") or {}
            fact_rows.append([
                _text(fact.get("dimension")),
                _text(fact.get("label")),
                f"{_text(fact.get('value'))} {_text(fact.get('unit'))}",
                _text(fact.get("source_kind")),
                _text(freshness.get("status")),
                _text(fact.get("as_of_utc")),
            ])
        story.extend([
            section_heading("Hechos y observaciones de investigación", styles),
            data_table(
                ["Dimensión", "Métrica / hecho", "Valor", "Tipo de fuente", "Frescura", "Observado en UTC"],
                fact_rows, styles,
                widths=[25*mm, 42*mm, 30*mm, 27*mm, 18*mm, 25*mm],
            ),
        ])
    else:
        story.extend([
            section_heading("Hechos y observaciones de investigación", styles),
            paragraph("No se proporcionaron hechos de investigación verificables.", styles["body"]),
        ])

    source_rows = []
    for fact in facts:
        source_rows.append([
            _text(fact.get("source_name") or fact.get("source_kind")),
            _text(fact.get("source_reference") or fact.get("assumption_note")),
            _text(fact.get("source_url") or "Supuesto explícito; sin URL externa"),
            _text(fact.get("published_at_utc") or fact.get("as_of_utc")),
            _text(fact.get("retrieved_at_utc")),
        ])
    if source_rows:
        story.extend([
            section_heading("Registro de fuentes y supuestos", styles),
            data_table(
                ["Fuente / tipo", "Referencia específica / supuesto", "URL", "Fecha fuente", "Consultado en UTC"],
                source_rows, styles,
                widths=[28*mm, 44*mm, 48*mm, 22*mm, 25*mm],
            ),
        ])

    scenarios = report.get("scenarios")
    if scenarios:
        story.extend([
            section_heading("Escenarios hipotéticos de precio", styles),
            paragraph(
                f"Horizonte: {_text(scenarios.get('horizon'))}. "
                f"Precio de referencia: {_text((scenarios.get('hypothetical_inputs') or {}).get('reference_entry_price'))} "
                f"{_text(scenarios.get('quote_currency'))}. "
                f"Invalidación: {_text((scenarios.get('hypothetical_inputs') or {}).get('invalidation_price'))}. "
                f"Riesgo a invalidación: {_text(scenarios.get('downside_to_invalidation_pct'))}%.",
                styles["body"],
            ),
            data_table(
                ["Escenario", "Precio supuesto", "Retorno simple", "Racional / supuestos"],
                [[name, _text(item.get("price")), f"{_text(item.get('return_pct'))}%",
                  _text(item.get("assumptions"))]
                 for name, item in (scenarios.get("scenarios") or {}).items()],
                styles, widths=[24*mm, 28*mm, 27*mm, 88*mm],
            ),
            key_value_table([
                ("Relación recompensa/riesgo alcista", scenarios.get("bull_reward_to_risk")),
                ("Relación recompensa/riesgo base", scenarios.get("base_reward_to_risk")),
                ("Probabilidades", "No calculadas"),
                ("Retorno esperado", "No calculado"),
            ], styles),
        ])

    sizing = report.get("position_sizing")
    if sizing:
        story.extend([
            section_heading("Dimensionamiento hipotético — solo efectivo", styles),
            key_value_table([
                ("Capital disponible supuesto", f"{sizing.get('available_capital')} {sizing.get('quote_currency')}"),
                ("Presupuesto de riesgo", f"{sizing.get('risk_budget_pct')}% ({sizing.get('risk_budget_amount')})"),
                ("Asignación máxima", f"{sizing.get('max_allocation_pct')}% ({sizing.get('max_allocation_amount')})"),
                ("Precio de entrada supuesto", sizing.get("entry_price")),
                ("Invalidación supuesta", sizing.get("invalidation_price")),
                ("Unidades estimadas", sizing.get("estimated_units")),
                ("Notional estimado", sizing.get("estimated_notional")),
                ("Pérdida planificada en invalidación", sizing.get("planned_loss_at_invalidation")),
                ("Restricción limitante", sizing.get("limiting_constraint")),
            ], styles),
        ])

    for key, heading in (
        ("risks", "Riesgos y contraevidencia"),
        ("thesis_invalidation", "Condiciones de invalidación de tesis"),
        ("unresolved_questions", "Preguntas pendientes"),
        ("provider_status", "Estado de proveedores y cobertura"),
        ("methodology_notes", "Metodología y limitaciones"),
    ):
        value = report.get(key)
        if value:
            story.extend([section_heading(heading, styles), paragraph(_text(value), styles["body"])])

    limitations = data_quality.get("limitations") or []
    if limitations:
        story.extend([
            section_heading("Limitaciones del paquete de evidencia", styles),
            paragraph(_text(limitations), styles["small"]),
        ])
    story.extend([
        Spacer(1, 4 * mm),
        paragraph(
            "Aviso: Este informe es una herramienta informativa de diligencia preinversión, no asesoramiento financiero. "
            "Los hechos dependen de sus fuentes y fechas; los escenarios y dimensionamientos son hipotéticos. "
            "No representa una posición real, no garantiza la ejecución de un nivel de invalidación y no envía órdenes.",
            styles["small"],
        ),
    ])
    artifact = write_pdf_atomic(destination, story, f"MASTER ARSENAL - Oportunidad {symbol}")
    try:
        inspect_pdf_artifact(artifact)
    except Exception:
        artifact.unlink(missing_ok=True)
        raise
    return artifact
