"""Independent PDF artifact audit report composer."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from .pdf import data_table, paragraph, report_styles, section_heading, write_pdf_atomic
from .qa import inspect_pdf_artifact


def _status_es(value: Any) -> str:
    return {
        "passed": "Aprobado",
        "failed": "Fallido",
        "not_verified": "No verificado",
        "not_implemented": "No implementado",
        "not_applicable": "No aplica",
        "not_exercised": "No probado",
        "disclosed": "Declarado",
        "opening": "Apertura", "closing": "Cierre", "intraday": "Intradía",
        "not verified": "No verificado", "not_verified": "No verificado",
        "not available": "No disponible", "not_available": "No disponible",
        "not integrated": "No integrado", "not_integrated": "No integrado",
        "not implemented": "No implementado", "not_implemented": "No implementado",
        "not_automated": "No automatizado", "not_applicable": "No aplica",
        "not_exercised": "No probado", "not_automated": "No automatizado",
    }.get(str(value), str(value))


def _text_audit(value: Any) -> str:
    if not value:
        return "No informado"
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value)


def build_skills_audit_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Render an evidence-led audit; missing evidence is explicitly not verified."""
    if not isinstance(report, dict):
        raise ValueError("Audit input must be an object")
    audit_date = report.get("audit_date_utc")
    generated_at = report.get("generated_at_utc")
    if not isinstance(audit_date, str):
        raise ValueError("audit_date_utc must be YYYY-MM-DD")
    try:
        parsed_date = datetime.strptime(audit_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("audit_date_utc must be YYYY-MM-DD") from exc
    if parsed_date.isoformat() != audit_date:
        raise ValueError("audit_date_utc must be canonical YYYY-MM-DD")
    if not isinstance(generated_at, str):
        raise ValueError("generated_at_utc must be an ISO-8601 UTC timestamp")
    try:
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at_utc must be an ISO-8601 UTC timestamp") from exc
    if generated.tzinfo is None or generated.utcoffset().total_seconds() != 0:
        raise ValueError("generated_at_utc must include UTC timezone")
    if generated.astimezone(timezone.utc).date().isoformat() != audit_date:
        raise ValueError("generated_at_utc date must match audit_date_utc")
    report_timezone = report.get("report_timezone", "America/Santo_Domingo")
    if report_timezone != "America/Santo_Domingo":
        raise ValueError("report_timezone must be America/Santo_Domingo")
    audit_date_local = report.get("audit_date_local")
    if not isinstance(audit_date_local, str):
        raise ValueError("audit_date_local must be YYYY-MM-DD")
    try:
        parsed_local_date = datetime.strptime(audit_date_local, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("audit_date_local must be YYYY-MM-DD") from exc
    if parsed_local_date.isoformat() != audit_date_local:
        raise ValueError("audit_date_local must be canonical YYYY-MM-DD")
    if generated.astimezone(ZoneInfo(report_timezone)).date().isoformat() != audit_date_local:
        raise ValueError("audit_date_local must match generated_at_utc in the report timezone")
    audit_verdict = report.get("audit_verdict", "No aprobado")
    if audit_verdict not in {"No aprobado", "Aprobado con reservas", "Aprobado"}:
        raise ValueError("audit_verdict must be one of the three original-skill verdicts")
    desk_checks_input = report.get("desk_checks") or []
    for item in desk_checks_input:
        if not isinstance(item, dict) or item.get("severity") not in {"Crítico", "Alto", "Medio", "Bajo", "Critical", "High", "Medium", "Low", "critical", "high", "medium", "low"}:
            raise ValueError("Every desk check must declare a recognized severity")

    artifacts = report.get("artifacts", [])
    findings = report.get("findings", [])
    if not isinstance(artifacts, list) or not isinstance(findings, list):
        raise ValueError("artifacts and findings must be lists")
    styles = report_styles()
    verified = sum(1 for item in artifacts if isinstance(item, dict) and item.get("qa_status") == "passed")
    unverified = len(artifacts) - verified
    status = "EVIDENCIA INSUFICIENTE" if not artifacts or unverified else "VERIFICACIÓN ESTRUCTURAL APROBADA"
    story = [
        Paragraph("Auditoría independiente de las Skills de Binance", styles["title"]),
        Paragraph("Revisión basada en evidencia de los informes generados y de su cobertura de verificación", styles["subtitle"]),
        data_table(["Metadatos de auditoría", "Valor"], [
            ["Fecha de auditoría local", audit_date_local],
            ["Zona horaria", report_timezone],
            ["Fecha de auditoría UTC", audit_date],
            ["Generado en UTC", generated_at],
            ["Versión del motor de informes", str(report.get("report_engine_version", "No indicada"))],
            ["Identidad de las Skills adaptadas", _status_es((report.get("source_skill_integrity") or {}).get("adaptation_status", "not_verified"))],
            ["Contenido de archivos originales", _status_es((report.get("source_skill_integrity") or {}).get("status", "not_verified"))],
            ["Informes encontrados", str(len(artifacts))],
            ["Informes que superan QA estructural", str(verified)],
            ["Informes no verificados o fallidos", str(unverified)],
            ["Estado estructural", status],
            ["Veredicto general", str(report.get("audit_verdict", "No aprobado"))],
        ], styles),
        Spacer(1, 4),
        section_heading("Alcance e independencia", styles),
        paragraph(
            "Esta auditoría inspecciona los archivos de informe disponibles de forma independiente de la Skill que los generó. "
            "El análisis estructural del PDF, la extracción de texto, la comprobación de límites de página y la renderización no "
            "demuestran la exactitud de los datos de mercado, la validez analítica, la autenticidad de las fuentes ni el mérito de una inversión.",
            styles["body"],
        ),
    ]
    executive_summary = report.get("executive_summary") or []
    story.append(section_heading("Resumen ejecutivo", styles))
    if executive_summary:
        for item in executive_summary[:7]:
            story.append(paragraph(f"• {item}", styles["body"]))
    else:
        story.append(paragraph("No se suministró un resumen ejecutivo.", styles["body"]))

    skill_results = report.get("skill_results") or []
    story.append(section_heading("Resultado por Skill", styles))
    if skill_results:
        skill_rows = [[
            str(item.get("name", "Desconocido")),
            _status_es(item.get("package_integrity", "not_verified")),
            _status_es(item.get("temporal_coherence", "not_verified")),
            _status_es(item.get("data_security", "not_verified")),
            _status_es(item.get("methodology", "not_verified")),
            str(item.get("status", "No aprobado")),
        ] for item in skill_results if isinstance(item, dict)]
        if skill_rows:
            story.append(data_table(
                ["Skill", "Integridad", "Coherencia temporal", "Seguridad", "Metodología", "Estado"],
                skill_rows, styles, widths=[38*mm, 24*mm, 28*mm, 22*mm, 25*mm, 24*mm],
            ))
    else:
        story.append(paragraph("No se suministró la tabla de resultados por Skill. NO VERIFICADO.", styles["body"]))

    if artifacts:
        rows = []
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            rows.append([
                str(item.get("filename", "Desconocido")),
                _status_es(item.get("report_type", "Desconocido")),
                _status_es(item.get("qa_status", "not_verified")),
                str(item.get("page_count", "N/A")),
                str(item.get("size_bytes", "N/A")),
                str(item.get("sha256", "No indicado")),
                str(item.get("issues", "No se suministraron hallazgos")),
            ])
        if rows:
            story.extend([
                section_heading("Registro de inspección de informes", styles),
                data_table(["Archivo", "Tipo", "QA", "Páginas", "Bytes", "SHA-256", "Hallazgos"],
                           rows, styles, widths=[30*mm, 18*mm, 16*mm, 12*mm, 15*mm, 30*mm, 42*mm]),
            ])
    else:
        story.extend([
            section_heading("Registro de inspección de informes", styles),
            paragraph("No había informes PDF de apertura, cierre o intradía disponibles. "
                      "Su exactitud NO ESTÁ VERIFICADA.", styles["body"]),
        ])
    if findings:
        story.append(section_heading("Hallazgos", styles))
        rows = []
        for item in findings:
            if not isinstance(item, dict):
                continue
            rows.append([
                str(item.get("severity", "Sin clasificar")),
                str(item.get("title", "Hallazgo sin título")),
                str(item.get("impact", "Impacto no indicado")),
                str(item.get("evidence", "No se suministró evidencia")),
                str(item.get("recommendation", "No se indicó corrección")),
            ])
        if rows:
            story.append(data_table(["Severidad", "Hallazgo", "Impacto", "Evidencia observada", "Corrección"], rows, styles))
    else:
        story.extend([
            section_heading("Hallazgos", styles),
            paragraph("No se suministraron hallazgos adicionales. La ausencia de hallazgos no demuestra que "
                      "el análisis de mercado subyacente sea correcto.", styles["body"]),
        ])
    source_integrity = report.get("source_skill_integrity") or {}
    story.append(section_heading("Integridad de los paquetes originales de Skills", styles))
    source_packages = source_integrity.get("packages") or []
    if source_packages:
        source_rows = [[
            str(item.get("name", "N/A")),
            _status_es(item.get("status", "not_verified")),
            str(item.get("adapted_version", "No indicado")),
            str(item.get("last_reviewed", "No indicado")),
            str(item.get("archive_sha256", "No indicado")),
            str(item.get("source_skill_sha256", "No indicado")),
            str(item.get("adapted_skill_sha256", "No indicado")),
        ] for item in source_packages if isinstance(item, dict)]
        if source_rows:
            story.append(data_table(
                ["Skill", "Estado", "Versión", "Revisión", "SHA-256 ZIP original", "SHA-256 SKILL original", "SHA-256 SKILL adaptada"],
                source_rows, styles, widths=[26*mm, 17*mm, 14*mm, 20*mm, 27*mm, 27*mm, 27*mm],
            ))
    else:
        story.append(paragraph(
            "Los hashes de los paquetes originales y su estructura ZIP interna no fueron verificados.",
            styles["body"],
        ))
    if source_integrity.get("findings"):
        for finding in source_integrity["findings"]:
            story.append(paragraph(f"• {finding}", styles["body"]))

    desk_checks = report.get("desk_checks") or []
    story.append(section_heading("Matriz de pruebas de escritorio de las Skills originales", styles))
    if desk_checks:
        desk_rows = [[
            str(item.get("id", "N/A")),
            str(item.get("case", "No especificado")),
            _status_es(item.get("status", "not_verified")),
            str(item.get("severity", "Sin clasificar")),
            "Esperado: " + str(item.get("expected", "No indicado")) + " Observado: " + str(item.get("observed", item.get("evidence", "No indicado"))),
            str(item.get("impact", "Impacto no indicado")),
            str(item.get("recommendation", "No indicado")),
        ] for item in desk_checks if isinstance(item, dict)]
        if desk_rows:
            story.append(data_table(
                ["ID", "Caso", "Estado", "Severidad", "Esperado / observado", "Impacto", "Corrección"],
                desk_rows, styles,
                widths=[10*mm, 25*mm, 17*mm, 14*mm, 48*mm, 25*mm, 24*mm],
            ))
    else:
        story.append(paragraph(
            "No se suministró la matriz de pruebas de escritorio original. La paridad completa de auditoría NO ESTÁ VERIFICADA.",
            styles["body"],
        ))

    story.append(section_heading("Cambios aplicados", styles))
    changes_applied = report.get("changes_applied") or []
    if changes_applied:
        for item in changes_applied:
            story.append(paragraph(f"• {item}", styles["body"]))
    else:
        story.append(paragraph("No se registraron cambios aplicados.", styles["body"]))

    story.append(section_heading("Pendientes", styles))
    pending_items = report.get("pending_items") or []
    if pending_items:
        for item in pending_items:
            story.append(paragraph(f"• {item}", styles["body"]))
    else:
        story.append(paragraph("No se suministraron elementos pendientes.", styles["body"]))

    story.append(section_heading("Archivos revisados", styles))
    files_reviewed = report.get("files_reviewed") or []
    if files_reviewed:
        for item in files_reviewed:
            story.append(paragraph(f"• {item}", styles["body"]))
    else:
        story.append(paragraph("No se suministró una lista de archivos.", styles["body"]))

    change_history = report.get("change_history") or []
    story.append(section_heading("Versionado e historial de cambios", styles))
    if change_history:
        change_rows = [[
            str(item.get("date", "No indicado")),
            str(item.get("version", "No indicado")),
            str(item.get("change", "No indicado")),
        ] for item in change_history if isinstance(item, dict)]
        if change_rows:
            story.append(data_table(["Fecha", "Versión", "Cambio"], change_rows, styles,
                                    widths=[28*mm, 25*mm, 100*mm]))
    else:
        story.append(paragraph("No se suministró un historial de versiones/cambios inspeccionable. NO VERIFICADO.",
                               styles["body"]))

    evidence_manifests = report.get("evidence_manifests") or []
    story.append(section_heading("Evidencia original y recálculo de indicadores", styles))
    if evidence_manifests:
        manifest_rows = [[
            str(item.get("manifest", "Desconocido")),
            str(item.get("report_type", "Desconocido")),
            str(item.get("status", "no verificado")),
            ", ".join(item.get("symbols_checked", [])),
            str(item.get("indicator_recalculation", "no verificado")),
            "; ".join(item.get("findings", [])) or "No finding",
        ] for item in evidence_manifests if isinstance(item, dict)]
        if manifest_rows:
            story.append(data_table(
                ["Manifiesto", "Tipo", "Estado", "Símbolos", "Indicadores", "Hallazgos"],
                manifest_rows, styles,
                widths=[34*mm, 18*mm, 17*mm, 23*mm, 23*mm, 38*mm],
            ))
    else:
        story.append(paragraph(
            "No había manifiestos internos de evidencia original. El recálculo de indicadores y la "
            "validación de velas vinculadas a sus fuentes NO ESTÁN VERIFICADOS.",
            styles["body"],
        ))
    cross_report = report.get("cross_report_consistency") or {}
    story.append(section_heading("Consistencia entre informes", styles))
    story.append(paragraph(
        f"Estado: {cross_report.get('status', 'no verificado')}; "
        f"velas coincidentes comprobadas: {cross_report.get('overlapping_candles_checked', 0)}; "
        f"manifiestos comparados: {cross_report.get('manifests_compared', 0)}; "
        f"discrepancias: {_text_audit(cross_report.get('mismatches', []))}",
        styles["body"],
    ))
    test_evidence = report.get("test_evidence") or []
    story.append(section_heading("Evidencia de pruebas", styles))
    if test_evidence:
        test_rows = [[
            str(item.get("suite", "Desconocido")),
            str(item.get("status", "no verificado")),
            str(item.get("run_id", "No indicado")),
            str(item.get("details", "No indicado")),
        ] for item in test_evidence if isinstance(item, dict)]
        if test_rows:
            story.append(data_table(["Suite", "Estado", "ID de ejecución", "Detalles"], test_rows, styles))
        else:
            story.append(paragraph("Test evidence was supplied but contained no usable records.", styles["body"]))
    else:
        story.append(paragraph(
            "No se suministró un manifiesto de ejecución de CI a esta auditoría local. El estado de las pruebas unitarias offline, "
            "el estado de Binance en vivo y el estado en vivo de los proveedores RSS NO ESTÁN VERIFICADOS aquí.",
            styles["body"],
        ))
    story.extend([
        section_heading("Límites de verificación", styles),
        paragraph(
            "Esta auditoría no certifica la disponibilidad de Binance en vivo, la integridad de las noticias, "
            "la interpretación de eventos macroeconómicos, la rentabilidad de estrategias ni la paridad con las Skills originales de Claude. "
            "Esas áreas permanecen NO VERIFICADAS salvo que exista evidencia inspeccionable independiente.",
            styles["body"],
        ),
    ])
    destination = Path(output_directory) / f"auditoria-skills-binance_{audit_date_local}.pdf"
    written = write_pdf_atomic(destination, story, "Auditoría independiente de las Skills de Binance")
    try:
        inspect_pdf_artifact(written)
    except Exception:
        written.unlink(missing_ok=True)
        raise
    return written


def audit_market_report_artifact(path: str | Path, report_type: str) -> dict[str, Any]:
    """Independently check PDF structure and minimum report-content requirements."""
    requirements = {
        "opening": (
            "BTCUSDT", "ETHUSDT", "Indicador técnico", "Validación de datos", "Escenario alcista / largo", "Escenario bajista / corto",
            "Contexto macroeconómico", "Noticias relevantes del mercado", "Procedencia de los datos",
            "Registro de consulta de fuentes macro/noticias", "URL del feed", "UTC", "Aviso importante",
            "America/Santo_Domingo", "Ventana de análisis local", "DÍA LOCAL COMPLETO",
            "Análisis de la cuenta Binance", "Cobertura del mercado bursátil estadounidense", "Horario de la sesión bursátil estadounidense", "Horario de activación",
            "Hora programada de apertura regular de EE. UU. (ET / hora local)", "Generado en hora local", "Generado en ET",
        ),
        "closing": (
            "BTCUSDT", "ETHUSDT", "Indicador técnico", "Validación de datos",
            "Escenario alcista / largo", "Escenario bajista / corto",
            "Contexto macroeconómico", "Noticias relevantes del mercado", "Procedencia de los datos",
            "Registro de consulta de fuentes macro/noticias", "Aviso importante",
            "America/Santo_Domingo", "Ventana de análisis local", "Análisis de la cuenta Binance",
            "Cobertura del mercado bursátil estadounidense", "Horario de la sesión bursátil estadounidense",
            "Horario de activación", "Comparación del pronóstico de apertura",
            "Hora programada de cierre regular de EE. UU. (ET / hora local)", "Generado en hora local", "Generado en ET",
        ),
        "intraday": (
            "BTCUSDT", "ETHUSDT", "Indicador técnico", "Validación de datos", "Contexto macroeconómico", "Noticias relevantes",
            "Escenario alcista / largo", "Escenario bajista / corto",
            "Fuentes y notas de procedencia", "Registro de consulta de fuentes macro/noticias", "URL del feed", "UTC", "Aviso",
            "America/Santo_Domingo", "Ventana de análisis local", "DÍA LOCAL PARCIAL",
            "Estado de la sesión bursátil estadounidense", "Base de comparación", "Análisis de la cuenta Binance",
            "Cobertura del mercado bursátil estadounidense", "Límite de la última vela cerrada (UTC)",
            "Hora de corte ET", "Generado en hora local", "Generado en ET",
        ),
    }
    if report_type not in requirements:
        raise ValueError("report_type must be opening, closing, or intraday")
    source = Path(path).resolve(strict=True)
    structural = inspect_pdf_artifact(source)
    import pymupdf as fitz
    with fitz.open(source) as document:
        extracted = "\\n".join(page.get_text("text") for page in document)
    normalized = " ".join(extracted.casefold().split())
    missing = [marker for marker in requirements[report_type]
               if " ".join(marker.casefold().split()) not in normalized]
    filename_prefix = {
        "opening": "apertura-mercado_",
        "closing": "cierre-mercado_",
        "intraday": "snapshot-mercado_",
    }[report_type]
    filename_ok = source.name.startswith(filename_prefix) and source.suffix.lower() == ".pdf"
    if not filename_ok:
        missing.append(f"Expected filename prefix: {filename_prefix}")
    if report_type == "closing" and not any(marker in normalized for marker in ("día local parcial", "día local completo")):
        missing.append("El informe de cierre debe identificar el día local como parcial o completo.")
    return {
        "structural_qa": structural,
        "report_type": report_type,
        "content_checks": {
            "required_markers": list(requirements[report_type]),
            "missing_markers": missing,
            "filename_contract": filename_ok,
        },
        "status": "passed" if not missing else "failed",
        "missing_markers": missing,
    }
