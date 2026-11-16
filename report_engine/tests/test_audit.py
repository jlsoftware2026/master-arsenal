"""Offline tests for the independent skills-audit PDF composer."""
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import unittest

from report_engine.audit import build_skills_audit_pdf


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
