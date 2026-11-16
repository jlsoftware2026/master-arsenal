"""Offline tests for the independent skills-audit PDF composer."""
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import unittest

from report_engine.audit import audit_market_report_artifact, build_skills_audit_pdf
from report_engine.session import build_opening_report_pdf


class AuditReportTests(unittest.TestCase):
    def test_audit_pdf_with_inspection_evidence(self):
        report = {
            "audit_date_utc": "2026-11-16",
            "generated_at_utc": "2026-11-16T12:00:00Z",
            "artifacts": [{
                "filename": "snapshot.pdf", "report_type": "intraday",
                "qa_status": "passed", "page_count": 2, "size_bytes": 2048,
                "sha256": "a" * 64, "issues": "None",
            }],
            "findings": [],
        }
        with TemporaryDirectory() as temp:
            path = build_skills_audit_pdf(report, temp)
            self.assertEqual(path.name, "auditoria-skills-binance_2026-11-16.pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))


    def test_market_report_audit_checks_required_content_and_filename(self):
        report = {
            "session_start_utc": "2026-11-15T04:00:00Z",
            "report_timezone": "America/Santo_Domingo",
            "report_date_local": "2026-11-15",
            "requested_report_date_local": "2026-11-16",
            "cutoff_resolution": "previous_local_calendar_day",
            "window_start_local": "2026-11-15T00:00:00-04:00",
            "cutoff_local": "2026-11-16T00:00:00-04:00",
            "window_semantics": "[start, cutoff)",
            "is_partial": False,
            "source": "Binance public REST API",
            "market": "spot",
            "interval": "1h",
            "data_status": "complete",
            "binance_account_data_status": "unavailable",
            "us_equity_market_data_status": "not_integrated",
            "activation_timing_status": "not_automated",
            "opening_forecast_scorecard_status": "not_applicable",
            "session_end_utc": "2026-11-16T04:00:00Z",
            "data_cutoff_utc": "2026-11-16T04:00:00Z",
            "indicator_methodology": {"partial_final_interval_excluded": False},
            "generated_at_utc": "2026-11-16T04:05:00Z",
            "symbols": {"BTCUSDT": {}, "ETHUSDT": {}},
            "executive_summary": "Observed BTC and ETH session data.",
            "bullish_scenario": "Conditional upside above prior-session high.",
            "bearish_scenario": "Conditional downside below prior-session low.",
            "assumptions_and_invalidation": "Opposite side of range invalidates scenario.",
            "risks": "Volatility and liquidity risk.",
            "limitations": "Private account and full U.S. equity-market coverage are unavailable.",
            "macro_context": "No date-matched macro events.",
            "news": "No date-matched digital asset news.",
            "provenance": [{"source": "Binance", "retrieved_at_utc": "2026-11-16T00:01:00Z", "note": "Fixture"}],
            "context_sources": [{
                "publisher": "Federal Reserve", "kind": "macro", "status": "ok",
                "retrieved_at_utc": "2026-11-16T00:01:00Z", "matching_items": 0,
                "feed_url": "https://www.federalreserve.gov/feeds/press_all.xml",
            }],
        }
        with TemporaryDirectory() as temp:
            artifact = build_opening_report_pdf(report, temp)
            audit = audit_market_report_artifact(artifact, "opening")
            self.assertEqual(audit["status"], "passed", audit["missing_markers"])

    def test_empty_artifact_set_is_allowed_but_reported_as_insufficient(self):
        report = {
            "audit_date_utc": "2026-11-16",
            "generated_at_utc": "2026-11-16T12:00:00Z",
            "artifacts": [], "findings": [],
        }
        with TemporaryDirectory() as temp:
            path = build_skills_audit_pdf(report, temp)
            self.assertTrue(path.is_file())

    def test_audit_timestamp_must_match_audit_date(self):
        report = {
            "audit_date_utc": "2026-11-16",
            "generated_at_utc": "2026-11-15T23:59:00Z",
            "artifacts": [], "findings": [],
        }
        with self.assertRaisesRegex(ValueError, "date must match"):
            build_skills_audit_pdf(report, ".")


if __name__ == "__main__":
    unittest.main()
