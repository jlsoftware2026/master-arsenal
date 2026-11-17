import hashlib
import json
import multiprocessing
import shutil
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance_data_engine.client import PaginationMetadata
from binance_data_engine.models import Candle

from local_engine.protocol import JobValidationError, new_job, validate_job
from local_engine.runtime import JobManager, JobRunner, Workspace, verify_original_skill_packages


def _process_submit(root, job, queue):
    try:
        JobManager(Workspace(root)).submit(job)
        queue.put("submitted")
    except JobValidationError:
        queue.put("duplicate")


def _process_claim(root, job_id, queue):
    try:
        JobManager(Workspace(root)).claim(job_id)
        queue.put("claimed")
    except JobValidationError:
        queue.put("unavailable")


class FakeBinanceClient:
    def __init__(self):
        self.cutoff = datetime(2026, 11, 13, 3, 0, tzinfo=timezone.utc)
        self.last_response_metadata = {
            "http_status": 200,
            "retrieved_at_utc": "2026-11-13T03:01:00Z",
        }

    def get_server_time(self, market):
        return datetime.now(timezone.utc) + timedelta(minutes=1)

    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        self.last_response_metadata = {"http_status": 200, "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        rows = []
        window_hours = int((end - start).total_seconds() // 3600)
        expected = 250 if window_hours >= 200 else window_hours
        for index in range(expected):
            opened = start + timedelta(hours=index)
            price = Decimal("100") + index
            rows.append(Candle(
                symbol=symbol, interval=interval, open_time=opened,
                close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
                open=price, high=price + 1, low=price - 1, close=price,
                volume=Decimal("10"),
            ))
        return rows, PaginationMetadata(
            pages=1, returned=len(rows), requested_start=start.isoformat(),
            requested_end=end.isoformat(), complete=True,
        )

    def get_24h_ticker(self, symbol, market):
        return {"symbol": symbol, "priceChangePercent": "1.0"}


def fake_us_market_snapshot(as_of):
    cutoff = as_of.astimezone(timezone.utc)
    observed = cutoff - timedelta(minutes=5)
    retrieved = datetime.now(timezone.utc)
    period1 = int((cutoff - timedelta(days=7)).timestamp())
    period2 = int(cutoff.timestamp()) + 1
    source_url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
        f"?period1={period1}&period2={period2}&interval=5m&includePrePost=true"
    )
    return {
        "status": "partial", "instrument_snapshot_status": "complete",
        "provider": "Yahoo Finance public chart endpoint (best effort)",
        "as_of_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "expected_instruments": 1, "available_instruments": 1,
        "unavailable_symbols": [],
        "groups": {"indices": [{
            "status": "ok", "name": "S&P 500", "symbol": "^GSPC",
            "category": "indices", "unit": "index_points", "last_price": 6000.0,
            "previous_close": 5990.0, "change": 10.0, "change_percent": 0.1669,
            "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
            "source": "Yahoo Finance public chart endpoint (best effort)",
            "source_url": source_url,
            "retrieved_at_utc": retrieved.isoformat().replace("+00:00", "Z"),
        }]},
        "sector_leaders": [], "sector_laggards": [],
        "market_breadth": {"status": "not_available"},
        "limitations": "Fixture quote only; not a complete market feed.",
    }


class LocalEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "workspace"
        self.manager = JobManager(Workspace(root))
        self.second_manager = JobManager(Workspace(root))

    def tearDown(self):
        self.temp.cleanup()

    def _approved_job(self, job_type="engine.health_check", parameters=None):
        job = new_job(job_type, parameters)
        self.manager.submit(job)
        self.manager.validate_pending(job["job_id"])
        self.manager.approve(job["job_id"])
        return job

    def test_new_job_requires_explicit_approval(self):
        job = new_job("engine.health_check")
        self.assertEqual(validate_job(job), job)
        self.assertTrue(job["approval"]["required"])
        self.assertFalse(job["approval"]["granted"])

    def test_rejects_unknown_fields_and_job_types(self):
        job = new_job("engine.health_check")
        job["command"] = "whoami"
        with self.assertRaises(JobValidationError):
            validate_job(job)
        job = new_job("engine.health_check")
        job["job_type"] = "arbitrary.execute"
        with self.assertRaises(JobValidationError):
            validate_job(job)

    def test_rejects_non_string_enum_values(self):
        job = new_job("engine.health_check")
        job["requested_by"] = {}
        with self.assertRaises(JobValidationError):
            validate_job(job)

    def test_rejects_path_traversal(self):
        job = new_job("engine.health_check")
        job["output"]["directory"] = "..\\..\\outside"
        with self.assertRaises(JobValidationError):
            validate_job(job)

    def test_rejects_job_id_path_traversal(self):
        with self.assertRaises(ValueError):
            self.manager.workspace.job_path("inbox", "../../outside")

    def test_job_requires_validation_and_approval(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        self.assertEqual(self.manager.validate_pending(job["job_id"]), "awaiting_approval")
        with self.assertRaises(JobValidationError):
            self.manager.claim(job["job_id"])
        self.manager.approve(job["job_id"])
        self.assertEqual(self.manager.get(job["job_id"])["status"], "validated")

    def test_health_check_completes(self):
        job = self._approved_job()
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue(self.manager.get(job["job_id"])["result"]["read_only"])

    def test_report_jobs_default_to_fixed_pdf_outputs(self):
        self.assertEqual(new_job("market.opening_report")["output"],
                         {"format": "pdf", "directory": "reports/opening"})
        self.assertEqual(new_job("market.closing_report")["output"],
                         {"format": "pdf", "directory": "reports/closing"})
        self.assertEqual(new_job("market.intraday_snapshot")["output"],
                         {"format": "pdf", "directory": "reports/intraday"})
        self.assertEqual(new_job("skills.audit")["output"],
                         {"format": "pdf", "directory": "reports/audit"})
        self.assertEqual(new_job("investment.opportunity_report")["output"],
                         {"format": "pdf", "directory": "reports/opportunities"})

    def test_opportunity_report_job_generates_pdf_after_approval(self):
        now = datetime.now(timezone.utc)
        stamp = now.isoformat().replace("+00:00", "Z")
        instrument_key = "listed_equity|exm|usd|example corp|nasdaq"
        parameters = {
            "instrument_candidate": {
                "asset_class": "listed_equity", "name": "Example Corp",
                "symbol": "EXM", "quote_currency": "USD",
                "issuer": "Example Corp", "exchange": "NASDAQ",
            },
            "research_facts": [{
                "fact_id": "local-fact-1", "instrument_key": instrument_key,
                "dimension": "revenue", "label": "Reported revenue",
                "value": "1000000", "unit": "USD",
                "source_kind": "issuer_disclosure", "evidence_quality": "verified_source",
                "source_name": "Example Corp filing",
                "source_url": "https://www.sec.gov/Archives/edgar/data/123/filing/",
                "source_reference": "FY2025 revenue table",
                "as_of_utc": stamp, "retrieved_at_utc": stamp,
            }],
            "freshness_limits_hours": {"revenue": 24},
            "conclusion": "potential_candidate_for_further_diligence",
            "executive_summary": ["Evidence is preliminary.", "Further diligence remains necessary."],
            "risks": ["Competitive pressure may affect margins."],
            "thesis_invalidation": ["Revenue growth fails to materialize."],
        }
        job = self._approved_job("investment.opportunity_report", parameters)
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed", result)
        report = result["result"]
        self.assertTrue(report["artifact_path"].startswith("reports/opportunities/"))
        self.assertEqual(report["fact_count"], 1)
        self.assertEqual(report["conclusion"], "potential_candidate_for_further_diligence")
        self.assertEqual(report["data_quality_status"], "evidence_recorded")
        self.assertEqual(report["venue_verification_status"], "not_verified")
        self.assertTrue(report["read_only"])
        self.assertTrue(report["hypothetical_only"])
        self.assertTrue(report["manifest_path"].startswith("data/manifests/opportunities/"))
        manifest = self.manager.workspace.directory(report["manifest_path"])
        self.assertTrue(manifest.is_file())
        self.assertEqual(report["manifest_sha256"], hashlib.sha256(manifest.read_bytes()).hexdigest())
        artifact = self.manager.workspace.directory(report["artifact_path"])
        self.assertTrue(artifact.is_file())
        payload = artifact.read_bytes()
        self.assertTrue(payload.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", payload[-1024:])
        self.assertEqual(report["sha256"], hashlib.sha256(payload).hexdigest())

        audit_job = self._approved_job("skills.audit", {})
        audit_result = JobRunner(self.manager).run(audit_job["job_id"])
        self.assertEqual(audit_result["status"], "completed", audit_result)
        self.assertEqual(audit_result["result"]["opportunity_reports_checked"], 1)
        self.assertEqual(audit_result["result"]["opportunity_audit_status"], "passed")
        opportunity_audit = next(
            item for item in audit_result["result"]["opportunity_artifacts"]
            if item["filename"] == report["filename"]
        )
        self.assertEqual(opportunity_audit["fundamental_metrics_status"], "passed")


    def test_opportunity_report_can_resolve_sec_ticker_automatically(self):
        now = datetime.now(timezone.utc)
        stamp = now.isoformat().replace("+00:00", "Z")
        key = "listed_equity|exm|usd|example corp|nasdaq"

        class FakeSEC:
            def __init__(self):
                pass

            def resolve_ticker(self, **kwargs):
                self.lookup = kwargs
                return {
                    "status": "resolved", "ticker": "EXM", "exchange": "NASDAQ",
                    "issuer_name": "EXAMPLE CORP", "cik": "0000000123",
                    "source_url": "https://www.sec.gov/files/company_tickers_exchange.json",
                    "retrieved_at_utc": stamp, "limitations": ["Fixture mapping only."],
                }

            def fetch_facts(self, **kwargs):
                self.fetch = kwargs
                return {
                    "cik": "0000000123", "provider_entity_name": "EXAMPLE CORP",
                    "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json",
                    "missing_dimensions": ["net_income"],
                    "facts": [{
                        "fact_id": "sec-fixture-revenue", "instrument_key": key,
                        "dimension": "revenue", "label": "Example Corp revenue",
                        "value": "1000000", "unit": "USD",
                        "source_kind": "audited_financials", "evidence_quality": "verified_source",
                        "source_name": "SEC EDGAR Company Facts",
                        "source_url": "https://www.sec.gov/Archives/edgar/data/123/filing/",
                        "source_reference": "CIK 0000000123; us-gaap:Revenues; form 10-K",
                        "as_of_utc": stamp, "published_at_utc": stamp,
                        "retrieved_at_utc": stamp,
                    }],
                }

        parameters = {
            "instrument_candidate": {
                "asset_class": "listed_equity", "name": "Example Corp",
                "symbol": "EXM", "quote_currency": "USD",
                "issuer": "Example Corp", "exchange": "NASDAQ",
            },
            "sec_edgar": {"resolve_ticker": True, "period": "annual"},
            "conclusion": "insufficient_evidence",
        }
        with patch("local_engine.runtime.SECEdgarCompanyFacts", FakeSEC):
            job = self._approved_job("investment.opportunity_report", parameters)
            result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed", result)
        provider = result["result"]["provider_status"]["sec_edgar"]
        self.assertEqual(provider["cik"], "0000000123")
        self.assertEqual(provider["ticker_resolution"]["status"], "resolved")
        self.assertEqual(provider["ticker_resolution"]["ticker"], "EXM")
        self.assertEqual(result["result"]["fact_count"], 1)

    def test_sec_ticker_auto_resolution_rejects_non_unique_mapping(self):
        class FakeSEC:
            def __init__(self):
                pass

            def resolve_ticker(self, **kwargs):
                return {"status": "ambiguous"}

        parameters = {
            "instrument_candidate": {
                "asset_class": "listed_equity", "name": "Example Corp",
                "symbol": "EXM", "quote_currency": "USD",
                "issuer": "Example Corp", "exchange": "NASDAQ",
            },
            "sec_edgar": {"resolve_ticker": True},
            "conclusion": "insufficient_evidence",
        }
        with patch("local_engine.runtime.SECEdgarCompanyFacts", FakeSEC):
            job = self._approved_job("investment.opportunity_report", parameters)
            result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("ambiguous", result["error"])



    def test_opportunity_report_can_verify_binance_spot_product_read_only(self):
        stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        class FakeVerifier:
            def verify_spot_product(self, candidate):
                self.candidate = candidate
                return {
                    "status": "verified", "venue": "Binance",
                    "product_id": "BTCUSDT", "market_type": "spot",
                    "base_asset": "BTC", "quote_asset": "USDT",
                    "product_status": "TRADING", "is_spot_trading_allowed": True,
                    "observed_at_utc": stamp,
                    "source_url": "https://api.binance.com/api/v3/exchangeInfo",
                    "evidence_note": "Exact product fixture.",
                }

        parameters = {
            "instrument_candidate": {
                "asset_class": "crypto", "name": "Bitcoin",
                "symbol": "BTC", "quote_currency": "USDT",
            },
            "binance_spot_check": True,
            "conclusion": "insufficient_evidence",
        }
        with patch("local_engine.runtime.BinanceSpotProductVerifier", FakeVerifier):
            job = self._approved_job("investment.opportunity_report", parameters)
            result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed", result)
        report = result["result"]
        self.assertEqual(report["venue_verification_status"], "verified")
        provider = report["provider_status"]["binance_spot"]
        self.assertEqual(provider["product_id"], "BTCUSDT")
        self.assertEqual(provider["product_status"], "TRADING")
        self.assertTrue(provider["is_spot_trading_allowed"])
        self.assertEqual(provider["source_url"], "https://api.binance.com/api/v3/exchangeInfo")

    def test_opportunity_report_rejects_manual_and_automatic_venue_evidence_together(self):
        parameters = {
            "instrument_candidate": {
                "asset_class": "crypto", "name": "Bitcoin",
                "symbol": "BTC", "quote_currency": "USDT",
            },
            "venue_evidence": {"status": "not_verified", "venue": "Binance"},
            "binance_spot_check": True,
            "conclusion": "insufficient_evidence",
        }
        job = self._approved_job("investment.opportunity_report", parameters)
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("not both", result["error"])


    def test_opportunity_report_requires_approval(self):
        job = new_job("investment.opportunity_report", {
            "instrument_candidate": {"asset_class": "crypto", "name": "Example",
                                     "symbol": "EXM", "quote_currency": "USDT"},
            "conclusion": "insufficient_evidence",
        })
        self.manager.submit(job)
        self.assertEqual(self.manager.validate_pending(job["job_id"]), "awaiting_approval")
        with self.assertRaises(JobValidationError):
            JobRunner(self.manager).run(job["job_id"])

    def test_opportunity_report_rejects_unsafe_output_directory(self):
        job = new_job("investment.opportunity_report")
        job["output"]["directory"] = "reports/../../outside"
        with self.assertRaises(JobValidationError):
            validate_job(job)

    def test_opportunity_report_does_not_promote_empty_evidence(self):
        job = self._approved_job("investment.opportunity_report", {
            "instrument_candidate": {
                "asset_class": "crypto", "name": "Example Token",
                "symbol": "EXM", "quote_currency": "USDT",
            },
            "conclusion": "potential_candidate_for_further_diligence",
        })
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("insufficient evidence", result["error"])

    def test_intraday_snapshot_job_generates_pdf(self):
        job = self._approved_job(
            "market.intraday_snapshot",
            {"cutoff_utc": "2026-11-13T03:00:00Z", "interval": "1h", "market": "spot"},
        )
        with patch("local_engine.runtime.BinancePublicClient", return_value=FakeBinanceClient()), \
             patch("report_engine.acquisition.collect_market_context", return_value={
                 "macro_context": "No macro items.", "news": "No news items.",
                 "macro_sources": [], "news_sources": [], "context_status": "complete",
                   "context_limitations": "Fixture context only.",
             }), patch("report_engine.acquisition.collect_us_market_snapshot", side_effect=fake_us_market_snapshot):
            result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed")
        artifact = result["result"]["artifact_path"]
        self.assertTrue(artifact.startswith("reports/intraday/"))
        path = self.manager.workspace.directory(artifact)
        self.assertTrue(path.is_file())
        pdf_bytes = path.read_bytes()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf_bytes[-1024:])
        self.assertEqual(result["result"]["size_bytes"], len(pdf_bytes))
        self.assertEqual(
            result["result"]["sha256"], hashlib.sha256(pdf_bytes).hexdigest()
        )
        self.assertEqual(result["result"]["artifact_path"], artifact)
        manifest = self.manager.workspace.directory(result["result"]["manifest_path"])
        self.assertTrue(manifest.is_file())
        self.assertEqual(result["result"]["manifest_sha256"], hashlib.sha256(manifest.read_bytes()).hexdigest())
        record = self.manager.get(job["job_id"])
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["result"]["format"], "pdf")


    def test_opening_and_closing_jobs_generate_pdf_after_approval(self):
        account_export_directory = self.manager.workspace.directory("data/account_exports")
        (account_export_directory / "transaction-history.csv").write_text(
            "User_ID,UTC_Time,Account,Operation,Coin,Change,Remark\n"
            "private-user-123,2026-11-11T14:00:00Z,Spot,Deposit,USDT,100,private note\n"
            "private-user-123,2026-11-16T14:00:00Z,USD-M Futures,Funding Fee,USDT,-0.5,private note\n"
            "private-user-123,2026-11-16 14:30:00,Spot,Deposit,USDT,1,private note\n",
            encoding="utf-8",
        )
        for job_type, expected_dir, expected_name, report_date in (
            ("market.opening_report", "reports/opening", "apertura-mercado_2026-11-12.pdf", "2026-11-12"),
            ("market.closing_report", "reports/closing", "cierre-mercado_2026-11-11.pdf", "2026-11-11"),
        ):
            parameters = {"session_date_local": report_date, "interval": "1h", "market": "spot"}
            if job_type == "market.closing_report":
                parameters["cutoff_local"] = "2026-11-11T12:00:00-04:00"
            job = self._approved_job(job_type, parameters)
            with patch("local_engine.runtime.BinancePublicClient", return_value=FakeBinanceClient()), \
                 patch("report_engine.session_acquisition.collect_market_context", return_value={
                     "macro_context": "No macro items.", "news": "No news items.",
                     "macro_sources": [], "news_sources": [], "context_status": "complete",
                     "context_limitations": "Fixture context only.",
                     "context_sources": [{
                         "publisher": "Federal Reserve", "kind": "macro", "status": "ok",
                         "retrieved_at_utc": "2026-11-13T03:02:00Z", "matching_items": 0,
                         "feed_url": "https://www.federalreserve.gov/feeds/press_all.xml",
                     }],
                 }), patch("report_engine.session_acquisition.collect_us_market_snapshot", side_effect=fake_us_market_snapshot):
                result = JobRunner(self.manager).run(job["job_id"])
            self.assertEqual(result["status"], "completed", result)
            self.assertTrue(result["result"]["artifact_path"].startswith(expected_dir + "/"))
            self.assertEqual(result["result"]["filename"], expected_name)
            self.assertTrue(self.manager.workspace.directory(result["result"]["artifact_path"]).is_file())
            manifest = self.manager.workspace.directory(result["result"]["manifest_path"])
            self.assertTrue(manifest.is_file())
            if job_type == "market.closing_report":
                manifest_text = manifest.read_text(encoding="utf-8")
                self.assertNotIn("private-user-123", manifest_text)
                self.assertNotIn("private note", manifest_text)

        intraday_job = self._approved_job("market.intraday_snapshot", {
            "interval": "1h", "market": "spot"
        })
        with patch("local_engine.runtime.BinancePublicClient", return_value=FakeBinanceClient()), patch(
            "report_engine.acquisition.collect_market_context", return_value={
                "macro_context": "No macro items.", "news": "No news items.",
                "macro_sources": [], "news_sources": [], "context_status": "complete",
                "context_limitations": "Fixture context only.",
            }
        ), patch("report_engine.acquisition.collect_us_market_snapshot", side_effect=fake_us_market_snapshot):
            intraday_result = JobRunner(self.manager).run(intraday_job["job_id"])
        self.assertEqual(intraday_result["status"], "completed", intraday_result)
        self.assertTrue(intraday_result["result"]["filename"].startswith("snapshot-mercado_"))

        audit_job = self._approved_job("skills.audit")
        audit_result = JobRunner(self.manager).run(audit_job["job_id"])
        self.assertEqual(audit_result["status"], "completed", audit_result)
        audit = audit_result["result"]
        self.assertEqual(audit["artifacts_inspected"], 3)
        self.assertEqual(audit["evidence_manifests_checked"], 3)
        self.assertEqual(audit["cross_report_consistency_status"], "passed")
        self.assertEqual(audit["opening_window_status"], "passed")
        self.assertEqual(audit["closing_window_status"], "passed")
        self.assertEqual(audit["intraday_cutoff_status"], "passed")
        self.assertEqual(audit["language_parity_status"], "passed")
        self.assertEqual(audit["us_session_status"], "passed")
        self.assertEqual(audit["us_holiday_status"], "passed")
        self.assertEqual(audit["us_market_data_provenance_status"], "passed")
        self.assertEqual(audit["account_export_status"], "passed", audit["account_export_findings"])
        self.assertEqual(audit["scorecard_status"], "passed")
        self.assertGreater(audit["overlapping_candles_checked"], 0)

        with (account_export_directory / "transaction-history.csv").open("a", encoding="utf-8") as stream:
            stream.write("private-user-123,2026-11-16T14:30:00Z,Spot,Deposit,USDT,1,changed after report\n")
        tamper_audit_job = self._approved_job("skills.audit")
        tamper_audit = JobRunner(self.manager).run(tamper_audit_job["job_id"])
        self.assertEqual(tamper_audit["status"], "completed", tamper_audit)
        self.assertEqual(tamper_audit["result"]["account_export_status"], "not_verified")

    def test_intraday_snapshot_cannot_run_before_explicit_approval(self):
        job = new_job("market.intraday_snapshot", {
            "cutoff_utc": "2026-11-13T03:00:00Z"
        })
        self.manager.submit(job)
        self.assertEqual(
            self.manager.validate_pending(job["job_id"]), "awaiting_approval"
        )
        with patch("local_engine.runtime.BinancePublicClient") as client_factory:
            with self.assertRaises(JobValidationError):
                JobRunner(self.manager).run(job["job_id"])
        client_factory.assert_not_called()
        self.assertEqual(self.manager.get(job["job_id"])["status"], "awaiting_approval")

    def test_intraday_snapshot_output_directory_is_fixed(self):
        job = new_job("market.intraday_snapshot", {
            "cutoff_utc": "2026-11-13T03:00:00Z"
        })
        job["output"]["directory"] = "reports/closing"
        with self.assertRaisesRegex(JobValidationError, "output is fixed to PDF in reports/intraday"):
            self.manager.submit(job)
        with patch("local_engine.runtime.BinancePublicClient") as client_factory:
            client_factory.assert_not_called()
        self.assertFalse(any(self.manager.workspace.directory("reports/closing").iterdir()))

    def test_intraday_snapshot_defaults_to_execution_time_in_dominican_timezone(self):
        job = self._approved_job("market.intraday_snapshot")
        with patch("local_engine.runtime.BinancePublicClient", return_value=FakeBinanceClient()), \
             patch("report_engine.acquisition.collect_market_context", return_value={
                 "macro_context": "No macro items.", "news": "No news items.",
                 "macro_sources": [], "news_sources": [], "context_status": "complete",
                 "context_limitations": "Fixture context only.",
             }), patch("report_engine.acquisition.collect_us_market_snapshot", side_effect=fake_us_market_snapshot):
            result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed", result)
        self.assertIn("snapshot-mercado_", result["result"]["filename"])
        self.assertEqual(result["result"]["report_date_local"], datetime.now(ZoneInfo("America/Santo_Domingo")).date().isoformat())

    def test_intraday_snapshot_job_rejects_non_pdf_output(self):
        job = new_job("market.intraday_snapshot", {
            "cutoff_utc": "2026-11-13T03:00:00Z"
        })
        job["output"]["format"] = "json"
        with self.assertRaisesRegex(JobValidationError, "output is fixed to PDF in reports/intraday"):
            self.manager.submit(job)


    def test_skills_audit_job_generates_pdf_and_reports_missing_evidence(self):
        job = self._approved_job("skills.audit")
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["result"]["format"], "pdf")
        self.assertEqual(result["result"]["artifacts_inspected"], 0)
        self.assertGreaterEqual(result["result"]["findings_count"], 1)
        artifact = self.manager.workspace.directory(result["result"]["artifact_path"])
        self.assertTrue(artifact.is_file())
        self.assertTrue(artifact.read_bytes().startswith(b"%PDF-"))

    def test_unsupported_handler_fails_explicitly(self):
        job = self._approved_job("engine.validate_data")
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("not implemented by this runtime", result["error"])

    def test_submitted_job_is_valid_json_with_real_newline(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        path = self.manager.workspace.job_path("inbox", job["job_id"])
        raw = path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(json.loads(raw.decode("utf-8"))["job_id"], job["job_id"])

    def test_duplicate_job_id_is_rejected(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        with self.assertRaises(JobValidationError):
            self.manager.submit(job)

    def test_workspace_rejects_symlink_escape_before_creating_children(self):
        root = Path(self.temp.name) / "symlink-workspace"
        outside = Path(self.temp.name) / "outside"
        root.mkdir()
        outside.mkdir()
        try:
            (root / "jobs").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Directory symlinks unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "escapes root"):
            Workspace(root).initialize()
        self.assertFalse((outside / "inbox").exists())

    def test_workspace_rejects_escape(self):
        with self.assertRaises(ValueError):
            self.manager.workspace.directory("../outside")

    def test_interrupted_transition_leaves_one_valid_state(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        source = self.manager.workspace.job_path("inbox", job["job_id"])
        target = self.manager.workspace.job_path("awaiting_approval", job["job_id"])
        with patch("local_engine.runtime.os.replace", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                self.manager.validate_pending(job["job_id"])
        self.assertTrue(source.is_file())
        self.assertFalse(target.exists())
        self.assertEqual(self.manager.get(job["job_id"])["status"], "inbox")

    def test_interruption_after_record_update_keeps_source_state_authoritative(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        source = self.manager.workspace.job_path("inbox", job["job_id"])
        target = self.manager.workspace.job_path("awaiting_approval", job["job_id"])
        real_replace = __import__("os").replace
        calls = 0

        def interrupt_before_rename(src, dst):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_replace(src, dst)
            raise OSError("simulated crash before state rename")

        with patch("local_engine.runtime.os.replace", side_effect=interrupt_before_rename):
            with self.assertRaises(OSError):
                self.manager.validate_pending(job["job_id"])
        self.assertTrue(source.is_file())
        self.assertFalse(target.exists())
        self.assertEqual(self.manager.get(job["job_id"])["status"], "inbox")

    def test_legacy_duplicate_states_are_reported_not_silently_selected(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        source = self.manager.workspace.job_path("inbox", job["job_id"])
        duplicate = self.manager.workspace.job_path("validated", job["job_id"])
        shutil.copyfile(source, duplicate)
        with self.assertRaisesRegex(JobValidationError, "multiple lifecycle states"):
            self.manager.get(job["job_id"])

    def test_concurrent_duplicate_submissions_allow_only_one(self):
        job = new_job("engine.health_check")
        barrier = threading.Barrier(2)
        outcomes = []

        def submit(manager):
            barrier.wait()
            try:
                manager.submit(job)
                outcomes.append("submitted")
            except JobValidationError:
                outcomes.append("duplicate")

        threads = [
            threading.Thread(target=submit, args=(self.manager,)),
            threading.Thread(target=submit, args=(self.second_manager,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertCountEqual(outcomes, ["submitted", "duplicate"])
        self.assertTrue(all(not thread.is_alive() for thread in threads))

    def test_multiprocess_duplicate_submissions_allow_only_one(self):
        job = new_job("engine.health_check")
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        processes = [
            context.Process(target=_process_submit, args=(str(self.manager.workspace.root), job, queue))
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        outcomes = [queue.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
        self.assertTrue(all(process.exitcode == 0 for process in processes))
        self.assertCountEqual(outcomes, ["submitted", "duplicate"])

    def test_multiprocess_claims_allow_only_one_worker(self):
        job = self._approved_job()
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        processes = [
            context.Process(target=_process_claim, args=(str(self.manager.workspace.root), job["job_id"], queue))
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        outcomes = [queue.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
        self.assertTrue(all(process.exitcode == 0 for process in processes))
        self.assertCountEqual(outcomes, ["claimed", "unavailable"])

    def test_concurrent_claims_allow_only_one_worker(self):
        job = self._approved_job()
        barrier = threading.Barrier(2)
        outcomes = []

        def claim(manager):
            barrier.wait()
            try:
                manager.claim(job["job_id"])
                outcomes.append("claimed")
            except JobValidationError:
                outcomes.append("unavailable")

        threads = [
            threading.Thread(target=claim, args=(self.manager,)),
            threading.Thread(target=claim, args=(self.second_manager,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertCountEqual(outcomes, ["claimed", "unavailable"])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(self.manager.get(job["job_id"])["status"], "running")


class OriginalSkillIntegrityTests(unittest.TestCase):
    REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

    def test_all_four_adaptations_match_recorded_original_skill_identities(self):
        result = verify_original_skill_packages(self.REPOSITORY_ROOT)
        self.assertEqual(result["status"], "not_verified", result["findings"])
        self.assertEqual(len(result["packages"]), 4)
        self.assertEqual(result["adaptation_status"], "passed")
        self.assertEqual(len(result["manifest_sha256"]), 64)
        self.assertTrue(all(item["status"] == "not_verified" for item in result["packages"]))
        self.assertTrue(any("los ZIP no están incluidos en este repositorio" in item for item in result["findings"]))

    def test_adaptation_identity_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(self.REPOSITORY_ROOT / "docs" / "original-skills-source",
                            root / "docs" / "original-skills-source")
            shutil.copytree(self.REPOSITORY_ROOT / "skills", root / "skills")
            adapted = root / "skills" / "binance-apertura-mercado" / "SKILL.md"
            original = adapted.read_text(encoding="utf-8")
            adapted.write_text(original.replace(
                "# binance-apertura-mercado\n", "# wrong-skill-name\n", 1
            ), encoding="utf-8")
            result = verify_original_skill_packages(root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("metadata/heading does not match" in item for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
