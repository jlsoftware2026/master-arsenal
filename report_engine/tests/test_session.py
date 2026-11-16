"""Offline tests for completed-session opening and closing PDF composers."""
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
import unittest

from report_engine.session import build_closing_report_pdf, build_opening_report_pdf

START = datetime(2026, 11, 14, tzinfo=timezone.utc)
END = START + timedelta(days=1)


def _candles(symbol):
    rows = []
    for hour in range(24):
        opened = START + timedelta(hours=hour)
        rows.append({
            "open_time": opened.isoformat().replace("+00:00", "Z"),
            "close_time": (opened + timedelta(hours=1) - timedelta(milliseconds=1)).isoformat().replace("+00:00", "Z"),
            "open": str(100 + hour), "high": str(102 + hour),
            "low": str(99 + hour), "close": str(101 + hour), "volume": "10",
        })
    return rows


def _report():
    return {
        "session_start_utc": START.isoformat().replace("+00:00", "Z"),
        "session_end_utc": END.isoformat().replace("+00:00", "Z"),
        "generated_at_utc": (END + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        "source": "Binance public REST API",
        "market": "spot",
        "interval": "1h",
        "data_status": "complete",
        "executive_summary": "BTC and ETH completed the UTC session.",
        "symbols": {
            "BTCUSDT": {"candles": _candles("BTCUSDT"), "candle_count": 24,
                        "indicators": {"ema_200": 123.4}, "performance": "+2.1%"},
            "ETHUSDT": {"candles": _candles("ETHUSDT"), "candle_count": 24,
                        "indicators": {"ema_200": 234.5}, "performance": "+1.4%"},
        },
        "bullish_scenario": "Continuation above the session high, conditional on volume.",
        "bearish_scenario": "Failure at resistance and loss of support invalidates the bullish case.",
        "macro_context": "No macro evidence supplied.",
        "news": "No news evidence supplied.",
    }


class SessionReportTests(unittest.TestCase):
    def test_opening_pdf_is_created_and_independently_readable(self):
        with TemporaryDirectory() as temp:
            path = build_opening_report_pdf(_report(), temp)
            self.assertEqual(path.name, "apertura-mercado_2026-11-14.pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

    def test_closing_pdf_is_created_and_independently_readable(self):
        with TemporaryDirectory() as temp:
            path = build_closing_report_pdf(_report(), temp)
            self.assertEqual(path.name, "cierre-mercado_2026-11-14.pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

    def test_both_core_symbols_are_mandatory(self):
        report = _report()
        del report["symbols"]["ETHUSDT"]
        with self.assertRaisesRegex(ValueError, "ETHUSDT"):
            build_opening_report_pdf(report, ".")

    def test_session_must_be_exactly_one_completed_utc_day(self):
        report = _report()
        report["session_end_utc"] = (END - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(ValueError, "exactly one UTC day"):
            build_closing_report_pdf(report, ".")

    def test_generation_cannot_precede_session_end(self):
        report = _report()
        report["generated_at_utc"] = START.isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            build_closing_report_pdf(report, ".")

    def test_out_of_window_candle_is_rejected(self):
        report = _report()
        report["symbols"]["BTCUSDT"]["candles"][0]["open_time"] = (
            START - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(ValueError, "outside the completed session"):
            build_opening_report_pdf(report, ".")


if __name__ == "__main__":
    unittest.main()
