"""Offline tests for the independent skills-audit PDF composer."""
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import unittest

from report_engine.audit import audit_market_report_artifact, build_skills_audit_pdf
from report_engine.session import build_closing_report_pdf, build_opening_report_pdf


class AuditReportTests(unittest.TestCase):
    def test_audit_pdf_with_inspection_evidence(self):
        report = {
            "audit_date_utc": "2026-11-16",
            "audit_date_local": "2026-11-16",
            "report_timezone": "America/Santo_Domingo",
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
            import pymupdf as fitz
            with fitz.open(path) as document:
                extracted = " ".join(page.get_text("text") for page in document)
            self.assertIn("Auditoría independiente de las Skills de Binance", extracted)
            self.assertIn("No se suministró la tabla de resultados por Skill", extracted)
            self.assertNotIn("No per-skill result table", extracted)
            self.assertNotIn("Expected:", extracted)


    def test_findings_count_and_exact_head_ci_evidence_are_rendered_consistently(self):
        report = {
            "audit_date_utc": "2026-11-16",
            "audit_date_local": "2026-11-16",
            "report_timezone": "America/Santo_Domingo",
            "generated_at_utc": "2026-11-16T12:00:00Z",
            "artifacts": [{"filename": "snapshot.pdf", "report_type": "intraday",
                           "qa_status": "passed", "page_count": 1, "size_bytes": 100,
                           "sha256": "a" * 64}],
            "findings": [
                {"severity": "Medio", "title": f"Finding {i}", "impact": "Scope",
                 "evidence": "Evidence", "recommendation": "Document"}
                for i in range(1, 5)
            ],
            "test_evidence": [{
                "suite": "GitHub Actions — Python tests (commit exacto)",
                "status": "passed", "run_id": "123456",
                "details": "SHA: " + "b" * 40 + "; four matrix jobs succeeded.",
            }],
            "test_evidence_scope_note": (
                "La tabla acredita el workflow remoto del SHA exacto; no es una ejecución local separada."
            ),
        }
        with TemporaryDirectory() as temp:
            path = build_skills_audit_pdf(report, temp)
            import pymupdf as fitz
            with fitz.open(path) as document:
                extracted = " ".join(page.get_text("text") for page in document)
            self.assertIn("Hallazgos (4)", extracted)
            self.assertIn("Hallazgos registrados en este informe", extracted)
            for i in range(1, 5):
                self.assertIn(f"Finding {i}", extracted)
            self.assertIn("GitHub Actions", extracted)
            self.assertIn("123456", extracted)
            self.assertIn("workflow remoto del SHA exacto", extracted)
            self.assertNotIn("No se suministró un manifiesto de ejecución de CI", extracted)

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

    def test_closing_pdf_audit_requires_and_accepts_partial_local_day_status(self):
        report = {
            "session_start_utc": "2026-11-16T04:00:00Z",
            "session_end_utc": "2026-11-16T16:30:00Z",
            "report_timezone": "America/Santo_Domingo",
            "report_date_local": "2026-11-16",
            "requested_report_date_local": "2026-11-16",
            "cutoff_resolution": "execution_time_local_default",
            "window_start_local": "2026-11-16T00:00:00-04:00",
            "cutoff_local": "2026-11-16T12:30:00-04:00",
            "window_semantics": "[start, cutoff)",
            "is_partial": True,
            "source": "Binance public REST API",
            "market": "spot",
            "interval": "1h",
            "data_status": "partial",
            "binance_account_data_status": "unavailable",
            "us_equity_market_data_status": "not_integrated",
            "us_equity_session_state": "not_available",
            "activation_timing_status": "not_automated",
            "opening_forecast_scorecard_status": "not_implemented",
            "data_cutoff_utc": "2026-11-16T16:00:00Z",
            "generated_at_utc": "2026-11-16T16:31:00Z",
            "symbols": {"BTCUSDT": {}, "ETHUSDT": {}},
            "executive_summary": "Resumen de prueba.",
            "bullish_scenario": "Escenario alcista condicional de prueba.",
            "bearish_scenario": "Escenario bajista condicional de prueba.",
            "macro_context": "Contexto macroeconómico no disponible en este fixture.",
            "news": "Noticias relevantes no disponibles en este fixture.",
            "limitations": "Datos privados y mercado estadounidense no disponibles.",
        }
        with TemporaryDirectory() as temp:
            artifact = build_closing_report_pdf(report, temp)
            audit = audit_market_report_artifact(artifact, "closing")
            self.assertEqual(audit["status"], "passed", audit["missing_markers"])

    def test_empty_artifact_set_is_allowed_but_reported_as_insufficient(self):
        report = {
            "audit_date_utc": "2026-11-16",
            "audit_date_local": "2026-11-16",
            "report_timezone": "America/Santo_Domingo",
            "generated_at_utc": "2026-11-16T12:00:00Z",
            "artifacts": [], "findings": [],
        }
        with TemporaryDirectory() as temp:
            path = build_skills_audit_pdf(report, temp)
            self.assertTrue(path.is_file())

    def test_audit_timestamp_must_match_audit_date(self):
        report = {
            "audit_date_utc": "2026-11-16",
            "audit_date_local": "2026-11-16",
            "report_timezone": "America/Santo_Domingo",
            "generated_at_utc": "2026-11-15T23:59:00Z",
            "artifacts": [], "findings": [],
        }
        with self.assertRaisesRegex(ValueError, "date must match"):
            build_skills_audit_pdf(report, ".")


if __name__ == "__main__":
    unittest.main()
