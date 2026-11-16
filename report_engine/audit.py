"""Independent PDF artifact audit report composer."""
from __future__ import annotations

from datetime import datetime, timezone
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
            ["Audit date UTC", audit_date],
            ["Generated at UTC", generated_at],
            ["Artifacts discovered", str(len(artifacts))],
            ["Artifacts passing structural QA", str(verified)],
            ["Artifacts not verified / failing", str(unverified)],
            ["Overall status", status],
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
    destination = Path(output_directory) / f"auditoria-skills-binance_{audit_date}.pdf"
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
        ),
        "closing": (
            "BTCUSDT", "ETHUSDT", "Bullish / long scenario", "Bearish / short scenario",
            "Macroeconomic context", "Relevant market news", "Data provenance",
            "Macro/news feed retrieval register", "Important notice",
        ),
        "intraday": (
            "BTCUSDT", "ETHUSDT", "Technical indicator", "validation", "Macroeconomic context", "Relevant news",
            "Bullish / long scenario", "Bearish / short scenario",
            "Source and provenance notes", "Macro/news feed retrieval register", "Feed URL", "UTC", "Disclaimer",
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
        "intraday": "snapshot-mercado-",
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
