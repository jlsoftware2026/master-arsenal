"""Standalone pre-investment opportunity PDF composer."""
from __future__ import annotations

import re
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from .pdf import data_table, key_value_table, paragraph, report_styles, section_heading, write_pdf_atomic
from .qa import inspect_pdf_artifact
from .research import build_research_packet
from .scenarios import calculate_long_scenarios
from .position_sizing import calculate_cash_position_size
from .fundamentals import calculate_financial_ratios, calculate_valuation_multiples
from .peer_comparables import calculate_peer_comparables
from .tokenomics import calculate_tokenomics
from .biotech_valuation import assess_biotech_valuation

from .sec_edgar import SEC_TICKER_EXCHANGE_URL, SECEdgarCompanyFacts
from .binance_venue import BINANCE_SPOT_EXCHANGE_INFO_URL

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


def _issuer_identity_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return SECEdgarCompanyFacts._normalize_issuer_name(value)


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
    fundamental_metrics = report.get("fundamental_metrics")
    if fundamental_metrics is not None:
        if (not isinstance(fundamental_metrics, dict)
                or fundamental_metrics.get("schema") != "ma.financial-ratios/v1"
                or fundamental_metrics.get("instrument_key") != key):
            raise ValueError("fundamental_metrics must match the instrument and use ma.financial-ratios/v1")
    valuation_metrics = report.get("valuation_metrics")
    if valuation_metrics is not None:
        if (not isinstance(valuation_metrics, dict)
                or valuation_metrics.get("schema") != "ma.valuation-multiples/v1"
                or valuation_metrics.get("instrument_key") != key):
            raise ValueError("valuation_metrics must match the instrument and use ma.valuation-multiples/v1")
    peer_comparables = report.get("peer_comparables")
    if peer_comparables is not None:
        if (not isinstance(peer_comparables, dict)
                or peer_comparables.get("schema") != "ma.peer-comparables/v1"
                or peer_comparables.get("candidate_instrument_key") != key):
            raise ValueError("peer_comparables must match the instrument and use ma.peer-comparables/v1")
    biotech_valuation = report.get("biotech_valuation")
    biotech_valuation_inputs = report.get("biotech_valuation_inputs")
    if biotech_valuation is not None or biotech_valuation_inputs is not None:
        if not isinstance(biotech_valuation, dict) or biotech_valuation.get("schema") != "ma.biotech-valuation/v1":
            raise ValueError("biotech_valuation must use ma.biotech-valuation/v1")
        if biotech_valuation.get("instrument_key") != key:
            raise ValueError("biotech_valuation instrument_key does not match instrument")
        if not isinstance(biotech_valuation_inputs, dict) or biotech_valuation_inputs.get("instrument_key") != key:
            raise ValueError("biotech_valuation_inputs must match the instrument and be retained for audit")
        if assess_biotech_valuation(**biotech_valuation_inputs) != biotech_valuation:
            raise ValueError("biotech_valuation does not match its explicit source-attributed inputs")
    tokenomics = report.get("tokenomics")
    tokenomics_inputs = report.get("tokenomics_inputs")
    if tokenomics is not None or tokenomics_inputs is not None:
        if instrument.get("asset_class") != "crypto":
            raise ValueError("tokenomics analysis is only supported for crypto instruments")
        if not isinstance(tokenomics, dict) or tokenomics.get("schema") != "ma.tokenomics/v1":
            raise ValueError("tokenomics must use ma.tokenomics/v1")
        if tokenomics.get("instrument_key") != key:
            raise ValueError("tokenomics instrument_key does not match instrument")
        if not isinstance(tokenomics_inputs, dict):
            raise ValueError("tokenomics_inputs are required for independent recalculation")
        if tokenomics_inputs.get("instrument_key") != key:
            raise ValueError("tokenomics_inputs instrument_key does not match instrument")
        if calculate_tokenomics(**tokenomics_inputs) != tokenomics:
            raise ValueError("tokenomics does not match its explicit calculation inputs")
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


def _validate_valuation_calculation(report: dict[str, Any], instrument: dict[str, Any],
                                    packet: dict[str, Any]) -> None:
    stored = report.get("valuation_metrics")
    if stored is None:
        return
    rebuilt = calculate_valuation_multiples(
        packet.get("facts", []),
        instrument_key=instrument["instrument_key"],
        market_cap=stored.get("market_cap"),
        earnings_period_basis=stored.get("earnings_period_basis"),
    )
    if rebuilt != stored:
        raise ValueError("valuation_metrics do not match an independent calculation from the supplied evidence")


def _validate_biotech_valuation(report: dict[str, Any]) -> None:
    stored = report.get("biotech_valuation")
    if stored is None:
        return
    inputs = report.get("biotech_valuation_inputs")
    if not isinstance(inputs, dict):
        raise ValueError("biotech_valuation_inputs are required for independent recalculation")
    rebuilt = assess_biotech_valuation(**inputs)
    if rebuilt != stored:
        raise ValueError("biotech_valuation does not match independent calculations from the supplied evidence")


def _validate_peer_comparables(report: dict[str, Any]) -> None:
    stored = report.get("peer_comparables")
    if stored is None:
        return
    rebuilt = calculate_peer_comparables(
        stored.get("candidate"), stored.get("peers"),
        minimum_peer_count=stored.get("minimum_peer_count"),
    )
    if rebuilt != stored:
        raise ValueError("peer_comparables do not match independent calculations from the supplied peer evidence")


def build_opportunity_report_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Render a source-attributed opportunity report from validated structured evidence."""
    instrument, packet, generated = _validate(report)
    _validate_valuation_calculation(report, instrument, packet)
    _validate_peer_comparables(report)
    _validate_biotech_valuation(report)
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
            f"Hechos no verificados: {_text(data_quality.get('unverified_fact_ids'))}. "
            f"Hechos en conflicto: {_text(data_quality.get('conflicted_fact_ids'))}.",
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

    conflicts = data_quality.get("conflicts") or []
    if conflicts:
        conflict_rows = [[
            _text(item.get("dimension")),
            _text(item.get("label")),
            _text(item.get("unit")),
            _text(item.get("as_of_utc")),
            _text([
                f"{variant.get('value')} ({', '.join(variant.get('sources') or [])})"
                for variant in item.get("variants", [])
            ]),
            _text(item.get("resolution_status")),
        ] for item in conflicts if isinstance(item, dict)]
        story.extend([
            section_heading("Conflictos de evidencia no resueltos", styles),
            paragraph(
                "Se detectaron valores externos diferentes para la misma métrica, unidad y periodo. "
                "No se selecciona automáticamente una fuente ni se promedian los valores; la discrepancia "
                "requiere revisión y reconciliación antes de apoyar una conclusión de inversión.",
                styles["body"],
            ),
            data_table(
                ["Dimensión", "Métrica", "Unidad", "Periodo", "Valores / fuentes", "Estado"],
                conflict_rows, styles,
                widths=[18*mm, 28*mm, 14*mm, 25*mm, 65*mm, 17*mm],
            ),
        ])

    fundamental_metrics = report.get("fundamental_metrics")
    if fundamental_metrics:
        metric_rows = [[
            name,
            f"{item.get('value')} {item.get('unit')}",
            item.get("formula"),
            item.get("as_of_utc"),
            _text(item.get("source_fact_ids")),
        ] for name, item in (fundamental_metrics.get("metrics") or {}).items()]
        story.append(section_heading("Ratios financieros derivados", styles))
        if metric_rows:
            story.append(data_table(
                ["Métrica", "Valor", "Fórmula", "Periodo", "Hechos fuente"],
                metric_rows, styles,
                widths=[32*mm, 24*mm, 44*mm, 32*mm, 42*mm],
            ))
        else:
            story.append(paragraph("No hay datos suficientes para calcular ratios financieros.", styles["body"]))
        if fundamental_metrics.get("missing_metrics"):
            story.append(paragraph(
                "Métricas no calculadas: " + _text(fundamental_metrics["missing_metrics"]),
                styles["small"],
            ))

    valuation_metrics = report.get("valuation_metrics")
    if valuation_metrics is not None:
        valuation_rows = [[
            name,
            f"{item.get('value')} {item.get('unit')}",
            item.get("formula"),
            item.get("financial_period_end_utc"),
            item.get("financial_source_fact_id"),
            item.get("market_cap_source_id"),
        ] for name, item in (valuation_metrics.get("metrics") or {}).items()]
        story.append(section_heading("Múltiplos de valoración", styles))
        market_cap = valuation_metrics.get("market_cap") or {}
        story.append(paragraph(
            f"Capitalización bursátil: {_text(market_cap.get('value'))} {_text(market_cap.get('unit'))}; "
            f"observada en UTC: {_text(market_cap.get('as_of_utc'))}; "
            f"fuente: {_text(market_cap.get('source_id'))}; URL: {_text(market_cap.get('source_url'))}. "
            f"Base de resultados declarada: {_text(valuation_metrics.get('earnings_period_basis'))}. "
            f"Estado: {_text(valuation_metrics.get('status'))}.",
            styles["body"],
        ))
        if valuation_rows:
            story.append(data_table(
                ["Múltiplo", "Valor", "Fórmula", "Periodo financiero", "Hecho fuente", "Fuente capitalización"],
                valuation_rows, styles,
                widths=[25*mm, 18*mm, 37*mm, 29*mm, 34*mm, 31*mm],
            ))
        else:
            story.append(paragraph("No hay evidencia suficiente para calcular múltiplos de valoración.", styles["body"]))
        if valuation_metrics.get("missing_metrics"):
            story.append(paragraph(
                "Múltiplos no calculados: " + _text(valuation_metrics["missing_metrics"]),
                styles["small"],
            ))
        if valuation_metrics.get("limitations"):
            story.append(paragraph("Limitaciones: " + _text(valuation_metrics["limitations"]), styles["small"]))

    biotech_valuation = report.get("biotech_valuation")
    if biotech_valuation is not None:
        story.append(section_heading("Diligencia biotech: etapa, runway y catalizadores", styles))
        story.append(paragraph(
            f"Etapa declarada: {_text(biotech_valuation.get('development_stage'))}. "
            f"Estado del análisis: {_text(biotech_valuation.get('status'))}.",
            styles["body"],
        ))
        biotech_rows = [[name, _text(item.get("value")), _text(item.get("unit")),
                         _text(item.get("formula")), _text(item.get("as_of_utc") or
                         item.get("market_cap_as_of_utc")), _text(item.get("cash_source_id") or
                         item.get("market_cap_source_id"))]
                        for name, item in (biotech_valuation.get("metrics") or {}).items()]
        if biotech_rows:
            story.append(data_table(
                ["Métrica", "Valor", "Unidad", "Fórmula", "Observado UTC", "Fuente ID"],
                biotech_rows, styles,
                widths=[28*mm, 20*mm, 18*mm, 48*mm, 34*mm, 34*mm],
            ))
        if biotech_valuation.get("missing_metrics"):
            story.append(paragraph("Métricas no calculadas: " + _text(biotech_valuation["missing_metrics"]), styles["small"]))
        catalysts = biotech_valuation.get("clinical_catalysts") or []
        if catalysts:
            story.append(data_table(
                ["NCT", "Fase", "Estado", "Finalización primaria", "Fuente"],
                [[_text(item.get("nct_id")), _text(item.get("phase")), _text(item.get("status")),
                  _text(item.get("primary_completion_date")), _text(item.get("source_url"))]
                 for item in catalysts], styles,
                widths=[23*mm, 25*mm, 30*mm, 38*mm, 66*mm],
            ))
        story.append(paragraph(_text(biotech_valuation.get("warnings")), styles["small"]))

    tokenomics = report.get("tokenomics")
    if tokenomics:
        supply = tokenomics.get("supply") or {}
        valuation = tokenomics.get("valuation") or {}
        story.extend([
            section_heading("Tokenomics: oferta y valoración diluida", styles),
            key_value_table([
                ("Oferta circulante", supply.get("circulating")),
                ("Oferta total", supply.get("total")),
                ("Oferta máxima", supply.get("max") or "No suministrada"),
                ("Circulante / total", f"{_text(supply.get('circulating_pct_of_total'))}%"),
                ("Circulante / máximo", f"{_text(supply.get('circulating_pct_of_max'))}%" if supply.get("circulating_pct_of_max") is not None else "No calculado"),
                ("Precio de referencia", f"{_text(valuation.get('price'))} {_text(valuation.get('quote_currency'))}"),
                ("Capitalización estimada", _text(valuation.get("market_cap"))),
                ("FDV estimada", _text(valuation.get("fully_diluted_valuation"))),
            ], styles),
            paragraph(
                "La capitalización y FDV son cálculos aritméticos sobre precio y oferta suministrados; "
                "no constituyen una valoración independiente. Las definiciones de oferta deben revisarse.",
                styles["small"],
            ),
        ])
        unlocks = tokenomics.get("unlock_schedule") or {}
        story.append(section_heading("Calendario de desbloqueos conocidos", styles))
        story.append(key_value_table([
            ("Estado de cobertura", unlocks.get("status")),
            ("Desbloqueos conocidos futuros", unlocks.get("known_future_unlock_total")),
            ("Próximos 30 días (% oferta circulante)", (unlocks.get("known_unlocks_pct_of_circulating") or {}).get("30d")),
            ("Próximos 90 días (% oferta circulante)", (unlocks.get("known_unlocks_pct_of_circulating") or {}).get("90d")),
            ("Próximos 365 días (% oferta circulante)", (unlocks.get("known_unlocks_pct_of_circulating") or {}).get("365d")),
        ], styles))
        if unlocks.get("events"):
            story.append(data_table(
                ["Evento", "Fecha UTC", "Cantidad", "Categoría"],
                [[item.get("event_id"), item.get("unlock_at_utc"), item.get("amount"), item.get("recipient_category")]
                 for item in unlocks["events"]],
                styles, widths=[30*mm, 45*mm, 35*mm, 55*mm],
            ))
        holders = tokenomics.get("holder_concentration") or {}
        story.append(section_heading("Concentración de tenedores observada", styles))
        story.append(key_value_table([
            ("Estado", holders.get("status")),
            ("Cobertura declarada", f"{_text(holders.get('coverage_pct'))}%" if holders.get("coverage_pct") is not None else "No evaluada"),
            ("Top 1 observado / circulante", f"{_text(holders.get('top_1_observed_pct'))}%"),
            ("Top 5 observado / circulante", f"{_text(holders.get('top_5_observed_pct'))}%"),
            ("Carteras incluidas", holders.get("holder_count")),
        ], styles))
        story.append(paragraph(
            "La concentración se limita a las carteras suministradas y a la cobertura declarada; "
            "una dirección no equivale necesariamente a un beneficiario económico. "
            "Datos ausentes no significan cero desbloqueos ni concentración nula.",
            styles["small"],
        ))

    peer_comparables = report.get("peer_comparables")
    if peer_comparables is not None:
        story.append(section_heading("Comparables de valoración", styles))
        story.append(paragraph(
            f"Estado: {_text(peer_comparables.get('status'))}. "
            f"Método de selección: {_text(peer_comparables.get('peer_selection_method'))}. "
            f"Peers seleccionados: {_text(peer_comparables.get('peer_count'))}; "
            f"mínimo requerido: {_text(peer_comparables.get('minimum_peer_count'))}.",
            styles["body"],
        ))
        comparable_rows = [[
            name, item.get("median"), item.get("minimum"), item.get("maximum"),
            item.get("peer_count"), item.get("candidate_value"),
            item.get("candidate_premium_discount_pct_vs_median"),
        ] for name, item in (peer_comparables.get("metrics") or {}).items()]
        if comparable_rows:
            story.append(data_table(
                ["Múltiplo", "Mediana", "Mínimo", "Máximo", "N peers", "Candidato", "Prima / descuento %"],
                comparable_rows, styles,
                widths=[26*mm, 20*mm, 20*mm, 20*mm, 14*mm, 22*mm, 52*mm],
            ))
        if peer_comparables.get("missing_metrics"):
            story.append(paragraph(
                "Comparaciones no publicadas: " + _text(peer_comparables["missing_metrics"]),
                styles["small"],
            ))
        peer_rows = [[
            _text(item.get("name")), _text(item.get("instrument_key")),
            _text((item.get("selection_criteria") or {}).get("sector")),
            _text((item.get("selection_criteria") or {}).get("business_model")),
            _text((item.get("selection_criteria") or {}).get("geography")),
            _text((item.get("selection_criteria") or {}).get("market_cap_band")),
            _text((item.get("selection_criteria") or {}).get("rationale")),
        ] for item in peer_comparables.get("peers", [])]
        if peer_rows:
            story.append(data_table(
                ["Peer", "Instrumento", "Sector", "Modelo", "Geografía", "Tamaño", "Racional de selección"],
                peer_rows, styles,
                widths=[18*mm, 25*mm, 18*mm, 22*mm, 18*mm, 16*mm, 57*mm],
            ))
        story.append(paragraph(
            "La selección de comparables es suministrada por el analista y no se certifica automáticamente. "
            "Las medianas son descriptivas; diferencias de crecimiento, apalancamiento, mezcla de ingresos, "
            "capitalización, contabilidad y riesgo pueden limitar la comparabilidad.",
            styles["small"],
        ))
        if peer_comparables.get("limitations"):
            story.append(paragraph("Limitaciones: " + _text(peer_comparables["limitations"]), styles["small"]))

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


def write_opportunity_manifest(
    report: dict[str, Any],
    pdf_path: Path | str,
    manifest_directory: Path | str,
) -> Path:
    """Write a fixed-schema, PDF-hash-bound sidecar for independent opportunity audit."""
    instrument, packet, _ = _validate(report)
    _validate_valuation_calculation(report, instrument, packet)
    _validate_peer_comparables(report)
    _validate_biotech_valuation(report)
    pdf = Path(pdf_path).resolve(strict=True)
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise ValueError("Opportunity manifest requires an existing PDF artifact")
    payload = pdf.read_bytes()
    if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-1024:]:
        raise ValueError("Opportunity PDF failed signature validation before manifest creation")
    directory = Path(manifest_directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "ma.opportunity-evidence/v1",
        "manifest_generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pdf_filename": pdf.name,
        "pdf_sha256": hashlib.sha256(payload).hexdigest(),
        "report": report,
    }
    destination = directory / f"{pdf.stem}.opportunity.json"
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.stem}.", suffix=".tmp", dir=directory)
    os.close(fd)
    try:
        Path(temporary).write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        with open(temporary, "r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return destination


def audit_opportunity_manifest(
    manifest_path: Path | str,
    workspace_root: Path | str,
) -> dict[str, Any]:
    """Independently revalidate the opportunity packet, calculations, and linked PDF."""
    findings: list[str] = []
    root = Path(workspace_root).resolve()
    manifest_directory = (root / "data" / "manifests" / "opportunities").resolve()
    try:
        manifest = Path(manifest_path).resolve(strict=True)
        if not manifest.is_relative_to(manifest_directory):
            raise ValueError("Opportunity manifest escapes its fixed directory")
        if manifest.stat().st_size > 20_000_000:
            raise ValueError("Opportunity manifest exceeds the 20 MB safety limit")
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != "ma.opportunity-evidence/v1":
            raise ValueError("Unsupported opportunity evidence manifest schema")
        report = payload.get("report")
        instrument, packet, generated = _validate(report)
        manifest_generated = _utc(payload.get("manifest_generated_at_utc"), "manifest_generated_at_utc")
        if manifest_generated < generated:
            findings.append("Manifest generation timestamp precedes opportunity report generation.")

        pdf_filename = payload.get("pdf_filename")
        if not isinstance(pdf_filename, str) or Path(pdf_filename).name != pdf_filename or not pdf_filename.lower().endswith(".pdf"):
            raise ValueError("Opportunity PDF filename is invalid")
        pdf_directory = (root / "reports" / "opportunities").resolve()
        pdf = (pdf_directory / pdf_filename).resolve(strict=True)
        if not pdf.is_relative_to(pdf_directory) or not pdf.is_file():
            raise ValueError("Linked opportunity PDF is missing or escapes its fixed directory")
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != payload.get("pdf_sha256"):
            findings.append("Opportunity PDF SHA-256 does not match its evidence manifest.")
        page_count = 0
        try:
            qa = inspect_pdf_artifact(pdf)
            page_count = int(qa.get("page_count", 0))
            if page_count < 1:
                findings.append("Opportunity PDF structural QA did not return a valid page count.")
        except Exception as exc:
            findings.append(f"Opportunity PDF structural QA failed: {type(exc).__name__}: {exc}")

        issuer_mapping_status = "not_applicable"
        provider_status = report.get("provider_status")
        sec_provider = provider_status.get("sec_edgar") if isinstance(provider_status, dict) else None
        if isinstance(sec_provider, dict):
            resolution = sec_provider.get("ticker_resolution")
            if resolution is None:
                issuer_mapping_status = "manual_cik_not_independently_verified"
            else:
                issuer_mapping_status = "passed"
                mapping_issues: list[str] = []
                if not isinstance(resolution, dict) or resolution.get("status") != "resolved":
                    mapping_issues.append("Recorded SEC ticker resolution is not in resolved state.")
                else:
                    if instrument.get("asset_class") != "listed_equity":
                        mapping_issues.append("Automatic SEC ticker resolution is only valid for listed_equity.")
                    if resolution.get("ticker") != instrument.get("symbol"):
                        mapping_issues.append("SEC ticker resolution symbol does not match the normalized instrument.")
                    if str(resolution.get("exchange", "")).casefold() != str(instrument.get("exchange", "")).casefold():
                        mapping_issues.append("SEC ticker resolution exchange does not match the normalized instrument.")
                    if _issuer_identity_key(resolution.get("issuer_name")) != _issuer_identity_key(instrument.get("issuer")):
                        mapping_issues.append("SEC ticker resolution issuer name does not match the normalized instrument.")
                    if resolution.get("source_url") != SEC_TICKER_EXCHANGE_URL:
                        mapping_issues.append("SEC ticker resolution source URL is not the official exchange-aware directory.")
                    try:
                        mapping_retrieved = _utc(resolution.get("retrieved_at_utc"), "SEC ticker mapping retrieved_at_utc")
                        if mapping_retrieved > generated:
                            mapping_issues.append("SEC ticker mapping retrieval timestamp is later than report generation.")
                    except Exception as exc:
                        mapping_issues.append(f"SEC ticker mapping timestamp is invalid: {type(exc).__name__}.")
                    resolved_cik = sec_provider.get("cik")
                    if not isinstance(resolved_cik, str) or len(resolved_cik) != 10 or not resolved_cik.isdigit():
                        mapping_issues.append("SEC provider CIK is not a zero-padded 10-digit identifier.")
                    else:
                        for fact in packet.get("facts", []):
                            if not isinstance(fact, dict):
                                continue
                            if str(fact.get("fact_id", "")).startswith("sec-"):
                                if not str(fact.get("fact_id", "")).startswith(f"sec-{resolved_cik}-"):
                                    mapping_issues.append("SEC fact ID CIK does not match the resolved provider CIK.")
                                    break
                                if f"CIK {resolved_cik};" not in str(fact.get("source_reference", "")):
                                    mapping_issues.append("SEC fact source reference does not match the resolved provider CIK.")
                                    break
                if mapping_issues:
                    issuer_mapping_status = "failed"
                    findings.extend(mapping_issues)

        venue_mapping_status = "not_applicable"
        binance_provider = provider_status.get("binance_spot") if isinstance(provider_status, dict) else None
        venue_verification = instrument.get("venue_verification") or {}
        if isinstance(binance_provider, dict):
            venue_mapping_status = "passed"
            venue_issues: list[str] = []
            provider_venue_status = binance_provider.get("status")
            if provider_venue_status not in {"verified", "unavailable", "not_verified"}:
                venue_issues.append("Recorded Binance Spot provider status is invalid.")
            if venue_verification.get("status") != provider_venue_status:
                venue_issues.append("Instrument venue-verification status does not match Binance provider status.")
            if provider_venue_status == "verified":
                declared = instrument.get("venue") or {}
                expected_product = f"{instrument.get('symbol', '').upper()}{instrument.get('quote_currency', '').upper()}"
                if instrument.get("asset_class") != "crypto":
                    venue_issues.append("Automatic Binance Spot verification is only valid for crypto candidates.")
                if declared.get("name") != "Binance" or declared.get("product_id") != expected_product or declared.get("market_type") != "spot":
                    venue_issues.append("Verified Binance Spot product identity does not match the normalized instrument.")
                if binance_provider.get("product_id") != expected_product:
                    venue_issues.append("Binance Spot provider product ID does not match the candidate base/quote.")
                if binance_provider.get("base_asset") != instrument.get("symbol"):
                    venue_issues.append("Binance Spot provider base asset does not match the instrument symbol.")
                if binance_provider.get("quote_asset") != instrument.get("quote_currency"):
                    venue_issues.append("Binance Spot provider quote asset does not match the instrument quote currency.")
                if binance_provider.get("product_status") != "TRADING" or binance_provider.get("is_spot_trading_allowed") is not True:
                    venue_issues.append("Binance Spot product is not recorded as TRADING with Spot permission enabled.")
            if binance_provider.get("source_url") not in {None, BINANCE_SPOT_EXCHANGE_INFO_URL}:
                venue_issues.append("Binance Spot evidence source URL is not the official exchangeInfo endpoint.")
            provider_observed = binance_provider.get("observed_at_utc")
            instrument_observed = venue_verification.get("observed_at_utc")
            if provider_observed != instrument_observed:
                venue_issues.append("Binance Spot provider and instrument observation timestamps differ.")
            if provider_observed:
                try:
                    if _utc(provider_observed, "Binance Spot observed_at_utc") > generated:
                        venue_issues.append("Binance Spot observation timestamp is later than report generation.")
                except Exception as exc:
                    venue_issues.append(f"Binance Spot observation timestamp is invalid: {type(exc).__name__}.")
            if provider_venue_status in {"unavailable", "not_verified"}:
                if binance_provider.get("reason") != venue_verification.get("reason"):
                    venue_issues.append("Binance Spot provider reason does not match the instrument venue evidence.")
            if venue_issues:
                venue_mapping_status = "failed"
                findings.extend(venue_issues)
        elif venue_verification.get("status") in {"verified", "unavailable"}:
            venue_mapping_status = "manual_venue_evidence_not_independently_verified"

        freshness = report.get("freshness_limits_hours") or {}
        rebuilt_packet = build_research_packet(
            instrument["instrument_key"], packet.get("facts", []),
            now=generated, freshness_limits_hours=freshness,
        )
        if rebuilt_packet != packet:
            findings.append("Independent research-packet reconstruction differs from the stored packet.")

        stored_fundamentals = report.get("fundamental_metrics")
        fundamental_status = "not_applicable"
        if stored_fundamentals is not None:
            rebuilt_fundamentals = calculate_financial_ratios(
                packet.get("facts", []), instrument_key=instrument["instrument_key"]
            )
            if rebuilt_fundamentals != stored_fundamentals:
                findings.append("Independent financial-ratio recalculation differs from the stored metrics.")
                fundamental_status = "failed"
            else:
                fundamental_status = "passed"

        stored_valuation = report.get("valuation_metrics")
        valuation_status = "not_applicable"
        if stored_valuation is not None:
            try:
                market_cap = stored_valuation.get("market_cap")
                rebuilt_valuation = calculate_valuation_multiples(
                    packet.get("facts", []),
                    instrument_key=instrument["instrument_key"],
                    market_cap=market_cap,
                    earnings_period_basis=stored_valuation.get("earnings_period_basis"),
                )
                if rebuilt_valuation != stored_valuation:
                    findings.append("Independent valuation-multiple recalculation differs from the stored metrics.")
                    valuation_status = "failed"
                else:
                    valuation_status = "passed"
            except Exception as exc:
                findings.append(f"Valuation-multiple recalculation failed: {type(exc).__name__}: {exc}")
                valuation_status = "failed"

        stored_biotech = report.get("biotech_valuation")
        biotech_status = "not_applicable"
        if stored_biotech is not None:
            try:
                rebuilt_biotech = assess_biotech_valuation(**report["biotech_valuation_inputs"])
                if rebuilt_biotech != stored_biotech:
                    findings.append("Independent biotech valuation/runway recalculation differs from the stored result.")
                    biotech_status = "failed"
                else:
                    biotech_status = "passed"
            except Exception as exc:
                findings.append(f"Biotech valuation/runway recalculation failed: {type(exc).__name__}: {exc}")
                biotech_status = "failed"

        stored_peers = report.get("peer_comparables")
        peer_status = "not_applicable"
        if stored_peers is not None:
            try:
                rebuilt_peers = calculate_peer_comparables(
                    stored_peers.get("candidate"), stored_peers.get("peers"),
                    minimum_peer_count=stored_peers.get("minimum_peer_count"),
                )
                if rebuilt_peers != stored_peers:
                    findings.append("Independent peer-comparables recalculation differs from the stored result.")
                    peer_status = "failed"
                else:
                    peer_status = "passed"
            except Exception as exc:
                findings.append(f"Peer-comparables recalculation failed: {type(exc).__name__}: {exc}")
                peer_status = "failed"

        stored_tokenomics = report.get("tokenomics")
        tokenomics_status = "not_applicable"
        if stored_tokenomics is not None:
            try:
                rebuilt_tokenomics = calculate_tokenomics(**report["tokenomics_inputs"])
                if rebuilt_tokenomics != stored_tokenomics:
                    findings.append("Independent tokenomics recalculation differs from the stored result.")
                    tokenomics_status = "failed"
                else:
                    tokenomics_status = "passed"
            except Exception as exc:
                findings.append(f"Tokenomics recalculation failed: {type(exc).__name__}: {exc}")
                tokenomics_status = "failed"

        scenario = report.get("scenarios")
        scenario_status = "not_applicable"
        if scenario is not None:
            inputs = scenario.get("hypothetical_inputs") or {}
            cases = scenario.get("scenarios") or {}
            try:
                rebuilt_scenario = calculate_long_scenarios(
                    instrument_key=instrument["instrument_key"],
                    quote_currency=scenario["quote_currency"],
                    reference_entry_price=inputs["reference_entry_price"],
                    invalidation_price=inputs["invalidation_price"],
                    bull_case={"price": cases["bull"]["price"], "assumptions": cases["bull"]["assumptions"]},
                    base_case={"price": cases["base"]["price"], "assumptions": cases["base"]["assumptions"]},
                    bear_case={"price": cases["bear"]["price"], "assumptions": cases["bear"]["assumptions"]},
                    invalidation_basis=inputs["invalidation_basis"],
                    horizon=scenario["horizon"],
                    as_of_utc=scenario["as_of_utc"],
                )
                if rebuilt_scenario != scenario:
                    findings.append("Independent bull/base/bear scenario recalculation differs from the stored result.")
                else:
                    scenario_status = "passed"
            except Exception as exc:
                findings.append(f"Scenario recalculation failed: {type(exc).__name__}: {exc}")
                scenario_status = "failed"

        sizing = report.get("position_sizing")
        sizing_status = "not_applicable"
        if sizing is not None:
            try:
                rebuilt_sizing = calculate_cash_position_size(
                    instrument_key=sizing["instrument_key"],
                    as_of_utc=sizing["as_of_utc"],
                    entry_price_basis=sizing["entry_price_basis"],
                    invalidation_basis=sizing["invalidation_basis"],
                    available_capital=sizing["available_capital"],
                    quote_currency=sizing["quote_currency"],
                    entry_price=sizing["entry_price"],
                    invalidation_price=sizing["invalidation_price"],
                    risk_budget_pct=sizing["risk_budget_pct"],
                    max_allocation_pct=sizing["max_allocation_pct"],
                    entry_fee_bps=sizing["entry_fee_bps"],
                    exit_fee_bps=sizing["exit_fee_bps"],
                    entry_slippage_bps=sizing["entry_slippage_bps"],
                    exit_slippage_bps=sizing["exit_slippage_bps"],
                )
                if rebuilt_sizing != sizing:
                    findings.append("Independent cash-only position-size recalculation differs from the stored result.")
                else:
                    sizing_status = "passed"
            except Exception as exc:
                findings.append(f"Position-size recalculation failed: {type(exc).__name__}: {exc}")
                sizing_status = "failed"

        return {
            "manifest": manifest.name,
            "pdf_filename": pdf_filename,
            "pdf_sha256": digest,
            "pdf_page_count": page_count,
            "instrument_key": instrument["instrument_key"],
            "conclusion": report["conclusion"],
            "fact_count": packet.get("fact_count", 0),
            "data_quality_status": (packet.get("data_quality") or {}).get("status"),
            "fundamental_metrics_status": fundamental_status,
            "valuation_metrics_status": valuation_status,
            "valuation_metrics_quality_status": (
                (stored_valuation or {}).get("status", "not_applicable")
            ),
            "peer_comparables_status": peer_status,
            "biotech_valuation_status": biotech_status,
            "peer_comparables_quality_status": (
                (stored_peers or {}).get("status", "not_applicable")
            ),
            "tokenomics_status": tokenomics_status,
            "issuer_mapping_status": issuer_mapping_status,
            "venue_mapping_status": venue_mapping_status,
            "fundamental_metrics_quality_status": (
                (stored_fundamentals or {}).get("status", "not_applicable")
            ),
            "scenario_status": scenario_status,
            "position_sizing_status": sizing_status,
            "status": "passed" if not findings else "failed",
            "findings": findings,
        }
    except Exception as exc:
        return {
            "manifest": Path(manifest_path).name,
            "status": "failed",
            "findings": findings + [f"{type(exc).__name__}: {exc}"],
        }
