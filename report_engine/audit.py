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


def _text_audit(value: Any) -> str:
    if not value:
        return "None reported"
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

    artifacts = report.get("artifacts", [])
    findings = report.get("findings", [])
    if not isinstance(artifacts, list) or not isinstance(findings, list):
        raise ValueError("artifacts and findings must be lists")
    styles = report_styles()
    verified = sum(1 for item in artifacts if isinstance(item, dict) and item.get("qa_status") == "passed")
    unverified = len(artifacts) - verified
    status = "INSUFFICIENT EVIDENCE" if not artifacts or unverified or findings else "STRUCTURAL CHECKS PASSED"
    story = [
        Paragraph("Binance Skills Independent Audit", styles["title"]),
        Paragraph("Evidence-led review of generated report artifacts and verification coverage", styles["subtitle"]),
        data_table(["Audit metadata", "Value"], [
            ["Audit date local", audit_date_local],
            ["Reporting timezone", report_timezone],
            ["Audit date UTC", audit_date],
            ["Generated at UTC", generated_at],
            ["Report engine version", str(report.get("report_engine_version", "Not supplied"))],
            ["Artifacts discovered", str(len(artifacts))],
            ["Artifacts passing structural QA", str(verified)],
            ["Artifacts not verified / failing", str(unverified)],
            ["Structural status", status],
            ["Overall audit verdict", str(report.get("audit_verdict", "No aprobado"))],
        ], styles),
        Spacer(1, 4),
        section_heading("Scope and independence", styles),
        paragraph(
            "This audit inspects available report files independently of their generating skill. "
            "Structural PDF parsing, text extraction, page-bound checks, and raster rendering do not "
            "prove market-data correctness, analytical validity, source authenticity, or investment merit.",
            styles["body"],
        ),
    ]
    if artifacts:
        rows = []
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            rows.append([
                str(item.get("filename", "Unknown")),
                str(item.get("report_type", "Unknown")),
                str(item.get("qa_status", "not verified")),
                str(item.get("page_count", "N/A")),
                str(item.get("size_bytes", "N/A")),
                str(item.get("sha256", "Not supplied")),
                str(item.get("issues", "None supplied")),
            ])
        if rows:
            story.extend([
                section_heading("Artifact inspection register", styles),
                data_table(["File", "Type", "QA", "Pages", "Bytes", "SHA-256", "Issues"],
                           rows, styles, widths=[30*mm, 18*mm, 16*mm, 12*mm, 15*mm, 30*mm, 42*mm]),
            ])
    else:
        story.extend([
            section_heading("Artifact inspection register", styles),
            paragraph("No opening, closing, or intraday PDF artifacts were available. "
                      "Their correctness is NOT VERIFIED.", styles["body"]),
        ])
    if findings:
        story.append(section_heading("Findings", styles))
        rows = []
        for item in findings:
            if not isinstance(item, dict):
                continue
            rows.append([
                str(item.get("severity", "unclassified")),
                str(item.get("title", "Untitled finding")),
                str(item.get("evidence", "No evidence supplied")),
                str(item.get("recommendation", "No recommendation supplied")),
            ])
        if rows:
            story.append(data_table(["Severity", "Finding", "Evidence", "Recommendation"], rows, styles))
    else:
        story.extend([
            section_heading("Findings", styles),
            paragraph("No additional findings were supplied. Absence of findings is not proof that "
                      "the underlying market analysis is correct.", styles["body"]),
        ])
    source_integrity = report.get("source_skill_integrity") or {}
    story.append(section_heading("Original skill package integrity", styles))
    source_packages = source_integrity.get("packages") or []
    if source_packages:
        source_rows = [[
            str(item.get("name", "N/A")),
            str(item.get("status", "not verified")),
            str(item.get("archive_sha256", "Not supplied")),
            str(item.get("source_skill_sha256", "Not supplied")),
            str(item.get("adapted_skill_sha256", "Not supplied")),
        ] for item in source_packages if isinstance(item, dict)]
        if source_rows:
            story.append(data_table(
                ["Package", "Status", "Original ZIP SHA-256", "Original SKILL SHA-256", "Adapted SKILL SHA-256"],
                source_rows, styles, widths=[32*mm, 18*mm, 36*mm, 36*mm, 36*mm],
            ))
    else:
        story.append(paragraph(
            "Original skill package hashes and internal ZIP structure were not verified.",
            styles["body"],
        ))
    if source_integrity.get("findings"):
        story.append(bullet_list([str(item) for item in source_integrity["findings"]], styles))

    desk_checks = report.get("desk_checks") or []
    story.append(section_heading("Original-skill desk-check matrix", styles))
    if desk_checks:
        desk_rows = [[
            str(item.get("id", "N/A")),
            str(item.get("case", "Unspecified")),
            str(item.get("status", "not verified")),
            str(item.get("severity", "unclassified")),
            str(item.get("evidence", "Not supplied")),
            str(item.get("recommendation", "Not supplied")),
        ] for item in desk_checks if isinstance(item, dict)]
        if desk_rows:
            story.append(data_table(
                ["ID", "Desk check", "Status", "Severity", "Evidence", "Recommendation"],
                desk_rows, styles,
                widths=[12*mm, 30*mm, 20*mm, 16*mm, 44*mm, 31*mm],
            ))
    else:
        story.append(paragraph(
            "The original-skill desk-check matrix was not supplied. Full audit parity is NOT VERIFIED.",
            styles["body"],
        ))

    change_history = report.get("change_history") or []
    story.append(section_heading("Version and change history", styles))
    if change_history:
        change_rows = [[
            str(item.get("date", "Not supplied")),
            str(item.get("version", "Not supplied")),
            str(item.get("change", "Not supplied")),
        ] for item in change_history if isinstance(item, dict)]
        if change_rows:
            story.append(data_table(["Date", "Version", "Change"], change_rows, styles,
                                    widths=[28*mm, 25*mm, 100*mm]))
    else:
        story.append(paragraph("No inspectable version/change history was supplied. NOT VERIFIED.",
                               styles["body"]))

    evidence_manifests = report.get("evidence_manifests") or []
    story.append(section_heading("Raw evidence and indicator recalculation", styles))
    if evidence_manifests:
        manifest_rows = [[
            str(item.get("manifest", "Unknown")),
            str(item.get("report_type", "Unknown")),
            str(item.get("status", "not verified")),
            ", ".join(item.get("symbols_checked", [])),
            str(item.get("indicator_recalculation", "not verified")),
            "; ".join(item.get("findings", [])) or "No finding",
        ] for item in evidence_manifests if isinstance(item, dict)]
        if manifest_rows:
            story.append(data_table(
                ["Manifest", "Type", "Status", "Symbols", "Indicators", "Findings"],
                manifest_rows, styles,
                widths=[34*mm, 18*mm, 17*mm, 23*mm, 23*mm, 38*mm],
            ))
    else:
        story.append(paragraph(
            "No internal raw-evidence manifests were available. Indicator recalculation and "
            "source-linked raw-candle validation are NOT VERIFIED.",
            styles["body"],
        ))
    cross_report = report.get("cross_report_consistency") or {}
    story.append(section_heading("Cross-report consistency", styles))
    story.append(paragraph(
        f"Status: {cross_report.get('status', 'not verified')}; "
        f"overlapping candles checked: {cross_report.get('overlapping_candles_checked', 0)}; "
        f"manifests compared: {cross_report.get('manifests_compared', 0)}; "
        f"mismatches: {_text_audit(cross_report.get('mismatches', []))}",
        styles["body"],
    ))
    test_evidence = report.get("test_evidence") or []
    story.append(section_heading("Testing evidence", styles))
    if test_evidence:
        test_rows = [[
            str(item.get("suite", "Unknown")),
            str(item.get("status", "not verified")),
            str(item.get("run_id", "Not supplied")),
            str(item.get("details", "Not supplied")),
        ] for item in test_evidence if isinstance(item, dict)]
        if test_rows:
            story.append(data_table(["Suite", "Status", "Run ID", "Details"], test_rows, styles))
        else:
            story.append(paragraph("Test evidence was supplied but contained no usable records.", styles["body"]))
    else:
        story.append(paragraph(
            "No CI test-run manifest was supplied to this local audit. Offline unit-test status, "
            "live Binance status, and RSS-provider live status are NOT VERIFIED here.",
            styles["body"],
        ))
    story.extend([
        section_heading("Verification boundaries", styles),
        paragraph(
            "This audit does not certify live Binance availability, source-news completeness, "
            "macro-event interpretation, strategy profitability, or the original Claude skill parity. "
            "Those areas remain NOT VERIFIED unless separately supported by inspectable evidence.",
            styles["body"],
        ),
    ])
    destination = Path(output_directory) / f"auditoria-skills-binance_{audit_date_local}.pdf"
    written = write_pdf_atomic(destination, story, "Binance Skills Independent Audit")
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
            "BTCUSDT", "ETHUSDT", "Technical indicator", "validation", "Bullish / long scenario", "Bearish / short scenario",
            "Macroeconomic context", "Relevant market news", "Data provenance",
            "Macro/news feed retrieval register", "Feed URL", "UTC", "Important notice",
            "America/Santo_Domingo", "Local reporting window", "COMPLETED LOCAL DAY",
            "Binance account analytics", "U.S. equity-market coverage", "Activation timing",
        ),
        "closing": (
            "BTCUSDT", "ETHUSDT", "Bullish / long scenario", "Bearish / short scenario",
            "Macroeconomic context", "Relevant market news", "Data provenance",
            "Macro/news feed retrieval register", "Important notice",
            "America/Santo_Domingo", "Local reporting window", "Binance account analytics",
            "U.S. equity-market coverage", "Activation timing", "Opening forecast scorecard",
        ),
        "intraday": (
            "BTCUSDT", "ETHUSDT", "Technical indicator", "validation", "Macroeconomic context", "Relevant news",
            "Bullish / long scenario", "Bearish / short scenario",
            "Source and provenance notes", "Macro/news feed retrieval register", "Feed URL", "UTC", "Disclaimer",
            "America/Santo_Domingo", "Local reporting window", "PARTIAL LOCAL DAY",
            "U.S. equity session state", "Comparison basis", "Binance account analytics",
            "U.S. equity-market coverage", "Last fully closed candle boundary UTC",
        ),
    }
    if report_type not in requirements:
        raise ValueError("report_type must be opening, closing, or intraday")
    source = Path(path).resolve(strict=True)
    structural = inspect_pdf_artifact(source)
    import pymupdf as fitz
    with fitz.open(source) as document:
        extracted = "\\n".join(page.get_text("text") for page in document)
    normalized = extracted.casefold()
    missing = [marker for marker in requirements[report_type]
               if marker.casefold() not in normalized]
    filename_prefix = {
        "opening": "apertura-mercado_",
        "closing": "cierre-mercado_",
        "intraday": "snapshot-mercado_",
    }[report_type]
    filename_ok = source.name.startswith(filename_prefix) and source.suffix.lower() == ".pdf"
    if not filename_ok:
        missing.append(f"Expected filename prefix: {filename_prefix}")
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
