"""Offline tests for completed-candle UTC acquisition."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory


from binance_data_engine.client import PaginationMetadata
from binance_data_engine.models import Candle
from report_engine.acquisition import acquire_intraday_evidence, generate_intraday_snapshot_pdf


START = datetime(2026, 11, 12, 4, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 11, 13, 3, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, missing=False, incomplete=False):
        self.missing = missing
        self.incomplete = incomplete
        self.last_response_metadata = {"retrieved_at_utc": "2026-11-13T03:01:00Z"}

    def get_server_time(self, market):
        return CUTOFF + timedelta(hours=1)

    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        rows = []
        if end <= START:
            for index in range(250):
                opened = start + timedelta(hours=index)
                rows.append(Candle(
                    symbol=symbol, interval=interval, open_time=opened,
                    close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
                    open=100 + index, high=102 + index, low=99 + index,
                    close=101 + index, volume=10,
                ))
        else:
            count = int((end - start).total_seconds() // 3600)
            for hour in range(count):
                if self.missing and hour == 1:
                    continue
                opened = start + timedelta(hours=hour)
                rows.append(Candle(
                    symbol=symbol, interval=interval, open_time=opened,
                    close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
                    open=100, high=102, low=99, close=101, volume=10,
                ))
        return rows, PaginationMetadata(
            pages=1, returned=len(rows),
            requested_start=start.isoformat().replace("+00:00", "Z"),
            requested_end=end.isoformat().replace("+00:00", "Z"),
            complete=not self.incomplete,
        )

    def get_24h_ticker(self, symbol, market):
        return {"symbol": symbol, "priceChangePercent": "1.0"}


class IntradayAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.context = patch("report_engine.acquisition.collect_market_context", return_value={
            "macro_context": "No macro items.", "news": "No news items.",
            "macro_sources": [], "news_sources": [], "context_status": "complete",
                   "context_limitations": "Fixture context only.",
        })
        self.context.start()

    def tearDown(self):
        self.context.stop()

    def test_acquires_completed_utc_day_candles_for_core_symbols(self):
        report = acquire_intraday_evidence(FakeClient(), CUTOFF, "1h")
        self.assertEqual(report["data_status"], "complete")
        for symbol in ("BTCUSDT", "ETHUSDT"):
            item = report["symbols"][symbol]
            self.assertEqual(item["candle_count"], 23)
            self.assertEqual(item["expected_candle_count"], 23)
            self.assertEqual(item["last_close_time_utc"], "2026-11-13T02:59:59.999000Z")
            self.assertEqual(item["indicator_history"]["candle_count"], 250)
            self.assertIsNotNone(item["indicators"]["ema_200"])

    def test_missing_candle_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "expected 23 candles, received 22"):
            acquire_intraday_evidence(FakeClient(missing=True), CUTOFF, "1h")

    def test_incomplete_pagination_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pagination is incomplete or inconsistent"):
            acquire_intraday_evidence(FakeClient(incomplete=True), CUTOFF, "1h")

    def test_unaligned_cutoff_is_preserved_and_incomplete_final_candle_excluded(self):
        requested = CUTOFF + timedelta(minutes=30)
        report = acquire_intraday_evidence(FakeClient(), requested, "1h")
        self.assertEqual(report["cutoff_utc"], requested.isoformat().replace("+00:00", "Z"))
        self.assertEqual(report["data_cutoff_utc"], CUTOFF.isoformat().replace("+00:00", "Z"))
        self.assertEqual(report["symbols"]["BTCUSDT"]["candle_count"], 23)

    def test_end_to_end_workflow_writes_pdf_from_acquired_evidence(self):
        with TemporaryDirectory() as temp:
            result = generate_intraday_snapshot_pdf(FakeClient(), CUTOFF, temp, "1h")
            self.assertTrue(result.is_file())
            self.assertEqual(result.name, "snapshot-mercado-2026-11-12_23-00.pdf")
            self.assertTrue(result.read_bytes().startswith(b"%PDF-"))

    def test_rejects_unsupported_interval(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            acquire_intraday_evidence(FakeClient(), CUTOFF, "1M")


if __name__ == "__main__":
    unittest.main()
