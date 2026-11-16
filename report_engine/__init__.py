"""MASTER ARSENAL shared PDF reporting infrastructure."""
from .acquisition import acquire_intraday_evidence, generate_intraday_snapshot_pdf
from .charts import MarketChart
from .intraday import build_intraday_snapshot_pdf
from .qa import inspect_pdf_artifact
from .session import build_closing_report_pdf, build_opening_report_pdf

__all__ = [
    "MarketChart",
    "acquire_intraday_evidence",
    "build_closing_report_pdf",
    "build_intraday_snapshot_pdf",
    "build_opening_report_pdf",
    "generate_intraday_snapshot_pdf",
    "inspect_pdf_artifact",
]
