"""MASTER ARSENAL shared PDF reporting infrastructure."""
from .acquisition import acquire_intraday_evidence
from .intraday import build_intraday_snapshot_pdf

__all__ = ["acquire_intraday_evidence", "build_intraday_snapshot_pdf"]
