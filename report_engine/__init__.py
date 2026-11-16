"""MASTER ARSENAL shared PDF reporting infrastructure."""
from .acquisition import acquire_intraday_evidence, generate_intraday_snapshot_pdf
from .audit import audit_market_report_artifact, build_skills_audit_pdf
from .charts import MarketChart
from .evidence import audit_cross_report_consistency, audit_evidence_manifest, write_evidence_manifest
from .intraday import build_intraday_snapshot_pdf
from .qa import inspect_pdf_artifact
from .session import build_closing_report_pdf, build_opening_report_pdf
from .session_acquisition import generate_closing_report_pdf, generate_opening_report_pdf

__all__ = [
    "MarketChart",
    "acquire_intraday_evidence",
    "audit_cross_report_consistency",
    "audit_evidence_manifest",
    "audit_market_report_artifact",
    "build_closing_report_pdf",
    "build_intraday_snapshot_pdf",
    "build_opening_report_pdf",
    "build_skills_audit_pdf",
    "generate_closing_report_pdf",
    "generate_intraday_snapshot_pdf",
    "generate_opening_report_pdf",
    "inspect_pdf_artifact",
    "write_evidence_manifest",
]
