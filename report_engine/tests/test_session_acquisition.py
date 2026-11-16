"""Offline tests for completed UTC-day Binance acquisition and PDF workflow."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from tempfile import TemporaryDirectory
import unittest

from binance_data_engine.client import PaginationMetadata
from binance_data_engine.models import Candle
from report_engine.session_acquisition import (
    acquire_session_report_evidence, generate_closing_report_pdf, generate_opening_report_pdf,
)

START = datetime(2026, 11, 14, tzinfo=timezone.utc)
END = START + timedelta(days=1)


class FakeClient:
    def __init__(self, incomplete=False, future_server=False):
        self.incomplete = incomplete
        self.future_server = future_server
        self.last_response_metadata = {"retrieved_at_utc": "2026-11-15T00:01:00Z"}

    def get_server_time(self, market):
        return END + timedelta(minutes=1) if not self.future_server else END - timedelta(minutes=1)

    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        count = 250 if end <= START else 24
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
        self.assertEqual(report["session_start_utc"], "2026-11-14T00:00:00Z")
        self.assertEqual(report["session_end_utc"], "2026-11-15T00:00:00Z")
        for symbol in ("BTCUSDT", "ETHUSDT"):
            item = report["symbols"][symbol]
            self.assertEqual(item["candle_count"], 24)
            self.assertEqual(item["indicator_history"]["candle_count"], 250)
            self.assertIsNotNone(item["indicators"]["ema_200"])
            self.assertEqual(item["performance"]["open"], "100")
            self.assertEqual(item["performance"]["close"], "123")

    def test_future_or_incomplete_session_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not yet complete"):
            acquire_session_report_evidence(FakeClient(future_server=True), START.date())
        with self.assertRaisesRegex(ValueError, "indicator-history pagination did not complete"):
            acquire_session_report_evidence(FakeClient(incomplete=True), START.date())

    def test_opening_and_closing_workflows_create_pdf(self):
        with TemporaryDirectory() as temp:
            opening = generate_opening_report_pdf(FakeClient(), temp, START.date())
            closing = generate_closing_report_pdf(FakeClient(), temp, START.date())
            self.assertEqual(opening.name, "apertura-mercado_2026-11-14.pdf")
            self.assertEqual(closing.name, "cierre-mercado_2026-11-14.pdf")
            self.assertTrue(opening.read_bytes().startswith(b"%PDF-"))
            self.assertTrue(closing.read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
