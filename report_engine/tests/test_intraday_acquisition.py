"""Offline tests for completed-candle UTC acquisition."""
from datetime import datetime, timedelta, timezone
import unittest
from tempfile import TemporaryDirectory


from binance_data_engine.client import PaginationMetadata
from binance_data_engine.models import Candle
from report_engine.acquisition import acquire_intraday_evidence, generate_intraday_snapshot_pdf


START = datetime(2026, 11, 13, tzinfo=timezone.utc)
CUTOFF = START + timedelta(hours=3)


class FakeClient:
    def __init__(self, missing=False):
        self.missing = missing
        self.last_response_metadata = {"retrieved_at_utc": "2026-11-13T03:01:00Z"}

    def get_server_time(self, market):
        return CUTOFF + timedelta(minutes=1)

    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        rows = []
        for hour in range(3):
            if self.missing and hour == 1:
                continue
            opened = START + timedelta(hours=hour)
            rows.append(Candle(
                symbol=symbol, interval=interval, open_time=opened,
                close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
                open=100, high=102, low=99, close=101, volume=10,
            ))
        return rows, PaginationMetadata(
            pages=1, returned=len(rows),
            requested_start=START.isoformat().replace("+00:00", "Z"),
            requested_end=CUTOFF.isoformat().replace("+00:00", "Z"),
            complete=True,
        )

    def get_24h_ticker(self, symbol, market):
        return {"symbol": symbol, "priceChangePercent": "1.0"}


class IntradayAcquisitionTests(unittest.TestCase):
    def test_acquires_completed_utc_day_candles_for_core_symbols(self):
        report = acquire_intraday_evidence(FakeClient(), CUTOFF, "1h")
        self.assertEqual(report["data_status"], "complete")
        for symbol in ("BTCUSDT", "ETHUSDT"):
            item = report["symbols"][symbol]
            self.assertEqual(item["candle_count"], 3)
            self.assertEqual(item["expected_candle_count"], 3)
            self.assertEqual(item["last_close_time_utc"], "2026-11-13T02:59:59.999000Z")

    def test_missing_candle_is_never_reported_as_complete(self):
        report = acquire_intraday_evidence(FakeClient(missing=True), CUTOFF, "1h")
        self.assertEqual(report["data_status"], "incomplete")
        issue_codes = {
            issue["code"] for issue in report["symbols"]["BTCUSDT"]["validation"]
        }
        self.assertIn("missing_candles", issue_codes)

    def test_end_to_end_workflow_writes_pdf_from_acquired_evidence(self):
        with TemporaryDirectory() as temp:
            result = generate_intraday_snapshot_pdf(FakeClient(), CUTOFF, temp, "1h")
            self.assertTrue(result.is_file())
            self.assertEqual(result.name, "snapshot-mercado-2026-11-13_03-00.pdf")
            self.assertTrue(result.read_bytes().startswith(b"%PDF-"))

    def test_rejects_unsupported_interval(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            acquire_intraday_evidence(FakeClient(), CUTOFF, "1M")


if __name__ == "__main__":
    unittest.main()
