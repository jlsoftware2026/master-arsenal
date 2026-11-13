"""Offline tests for the intraday PDF reporting contract."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from report_engine import build_intraday_snapshot_pdf


def fixture():
    return {
        "window_start_utc": "2026-11-13T00:00:00Z",
        "cutoff_utc": "2026-11-13T16:30:00Z",
        "generated_at_utc": "2026-11-13T16:31:00Z",
        "source": "Binance public REST API (fixture)",
        "market": "spot",
        "interval": "1h",
        "data_status": "fixture_only",
        "executive_summary": "Fixture report; no live market claim.",
        "symbols": {
            symbol: {
                "candle_count": 16,
                "first_open_time_utc": "2026-11-13T00:00:00Z",
                "last_close_time_utc": "2026-11-13T16:59:59Z",
                "ticker_24h": {"priceChangePercent": "1.2"},
                "response_metadata": {"retrieved_at_utc": "2026-11-13T16:30:30Z"},
                "indicators": {"ema_20": 100, "rsi_14": 55.2, "macd": {"line": 1.1}},
                "validation": [],
            } for symbol in ("BTCUSDT", "ETHUSDT")
        },
        "bullish_scenario": "Conditional upside scenario; fixture text only.",
        "bearish_scenario": "Conditional downside scenario; fixture text only.",
    }


class IntradayPdfTests(unittest.TestCase):
    def test_creates_named_readable_pdf(self):
        with TemporaryDirectory() as temp:
            result = build_intraday_snapshot_pdf(fixture(), temp)
            self.assertEqual(result.name, "snapshot-mercado-2026-11-13_16-30.pdf")
            payload = result.read_bytes()
            self.assertTrue(payload.startswith(b"%PDF-"))
            self.assertIn(b"%%EOF", payload[-2048:])
            self.assertGreater(len(payload), 1000)

    def test_requires_btc_and_eth(self):
        data = fixture()
        del data["symbols"]["ETHUSDT"]
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "ETHUSDT"):
                build_intraday_snapshot_pdf(data, temp)

    def test_rejects_non_utc_timestamps(self):
        data = fixture()
        data["cutoff_utc"] = "2026-11-13T16:30:00-04:00"
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "UTC"):
                build_intraday_snapshot_pdf(data, temp)

    def test_rejects_wrong_window_start(self):
        data = fixture()
        data["window_start_utc"] = "2026-11-13T01:00:00Z"
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "00:00 UTC"):
                build_intraday_snapshot_pdf(data, temp)

    def test_rejects_cutoff_before_start(self):
        data = fixture()
        data["cutoff_utc"] = "2026-11-13T00:00:00Z"
        with TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                build_intraday_snapshot_pdf(data, temp)


if __name__ == "__main__":
    unittest.main()
