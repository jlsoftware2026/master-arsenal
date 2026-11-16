"""Offline tests for completed UTC-day Binance acquisition and PDF workflow."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from binance_data_engine.client import PaginationMetadata
from binance_data_engine.models import Candle
from report_engine.session_acquisition import (
    acquire_session_report_evidence, generate_closing_report_pdf, generate_opening_report_pdf,
)

START = datetime(2026, 11, 14, 4, tzinfo=timezone.utc)
END = START + timedelta(days=1)


class FakeClient:
    def __init__(self, incomplete=False, future_server=False):
        self.incomplete = incomplete
        self.future_server = future_server
        self.last_response_metadata = {"retrieved_at_utc": "2026-11-15T00:01:00Z"}

    def get_server_time(self, market):
        return END + timedelta(minutes=1) if not self.future_server else END - timedelta(minutes=1)

    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        duration_hours = int((end - start).total_seconds() // 3600)
        count = 250 if duration_hours >= 200 else duration_hours
        rows = []
        for index in range(count):
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
            requested_end=end.isoformat(), complete=not self.incomplete,
        )

    def get_24h_ticker(self, symbol, market):
        self.last_response_metadata = {"retrieved_at_utc": "2026-11-15T00:02:00Z"}
        return {"symbol": symbol, "priceChangePercent": "1"}


class SessionAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.context = patch("report_engine.session_acquisition.collect_market_context", return_value={
            "macro_context": "No macro items.", "news": "No news items.",
            "macro_sources": [], "news_sources": [], "context_status": "complete",
            "context_limitations": "Fixture context only.",
        })
        self.context.start()

    def tearDown(self):
        self.context.stop()

    def test_evidence_contains_exact_session_and_separate_warmup(self):
        report = acquire_session_report_evidence(FakeClient(), START.date())
        self.assertEqual(report["session_start_utc"], "2026-11-14T04:00:00Z")
        self.assertEqual(report["session_end_utc"], "2026-11-15T04:00:00Z")
        self.assertIn("2026-11-14", report["executive_summary"])
        self.assertIn("día calendario local completado", report["executive_summary"])
        opening = acquire_session_report_evidence(FakeClient(), START.date(), report_kind="opening")
        self.assertIn("2026-11-13", opening["executive_summary"])
        self.assertIn("día calendario local anterior", opening["executive_summary"])
        for symbol in ("BTCUSDT", "ETHUSDT"):
            item = report["symbols"][symbol]
            self.assertEqual(item["candle_count"], 24)
            self.assertEqual(item["indicator_history"]["candle_count"], 250)
            self.assertIsNotNone(item["indicators"]["ema_200"])
            self.assertEqual(item["performance"]["open"], "100")
            self.assertEqual(item["performance"]["close"], "123")

    def test_subminute_session_interval_is_rejected(self):
        from binance_data_engine.session import acquire_completed_market_day
        with self.assertRaisesRegex(ValueError, "minimum 1m"):
            acquire_completed_market_day(FakeClient(), START.date(), interval="1s")

    def test_future_or_incomplete_session_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "later than Binance server time"):
            acquire_session_report_evidence(FakeClient(future_server=True), START.date())
        with self.assertRaisesRegex(ValueError, "indicator-history pagination is incomplete or inconsistent"):
            acquire_session_report_evidence(FakeClient(incomplete=True), START.date())

    def test_closing_supports_partial_dominican_calendar_day(self):
        from report_engine.session_acquisition import acquire_session_report_evidence
        cutoff = datetime(2026, 11, 14, 18, 30)
        report = acquire_session_report_evidence(
            FakeClient(), START.date(), report_kind="closing", cutoff_local=cutoff
        )
        self.assertTrue(report["is_partial"])
        self.assertEqual(report["report_timezone"], "America/Santo_Domingo")
        self.assertEqual(report["report_date_local"], "2026-11-14")
        self.assertEqual(report["session_start_utc"], "2026-11-14T04:00:00Z")
        self.assertEqual(report["session_end_utc"], "2026-11-14T22:30:00Z")
        self.assertEqual(report["data_cutoff_utc"], "2026-11-14T22:00:00Z")
        self.assertEqual(report["symbols"]["BTCUSDT"]["candle_count"], 18)

    def test_partial_closing_workflow_writes_local_date_pdf_and_evidence_manifest(self):
        cutoff = datetime(2026, 11, 14, 18, 30)
        with TemporaryDirectory() as temp:
            artifact = generate_closing_report_pdf(
                FakeClient(), Path(temp) / "reports" / "closing", START.date(),
                manifest_directory=Path(temp) / "data" / "manifests", cutoff_local=cutoff,
            )
            self.assertEqual(artifact.name, "cierre-mercado_2026-11-14.pdf")
            manifests = list((Path(temp) / "data" / "manifests").glob("*.evidence.json"))
            self.assertEqual(len(manifests), 1)
            payload = json.loads(manifests[0].read_text(encoding="utf-8"))
            report = payload["report"]
            self.assertTrue(report["is_partial"])
            self.assertEqual(report["cutoff_local"], "2026-11-14T18:30:00-04:00")
            self.assertEqual(payload["report_window"]["report_timezone"], "America/Santo_Domingo")
            self.assertEqual(len(payload["raw_candle_evidence_sha256"]), 64)
            from report_engine.evidence import audit_evidence_manifest
            audit = audit_evidence_manifest(manifests[0], Path(temp))
            self.assertEqual(audit["status"], "passed", audit["findings"])

    def test_opening_and_closing_workflows_create_pdf(self):
        with TemporaryDirectory() as temp:
            opening = generate_opening_report_pdf(FakeClient(), temp, START.date())
            closing = generate_closing_report_pdf(FakeClient(), temp, START.date())
            self.assertEqual(opening.name, "apertura-mercado_2026-11-13.pdf")
            self.assertEqual(closing.name, "cierre-mercado_2026-11-14.pdf")
            self.assertTrue(opening.read_bytes().startswith(b"%PDF-"))
            self.assertTrue(closing.read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
