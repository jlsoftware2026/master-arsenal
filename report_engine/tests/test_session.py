"""Offline tests for Dominican local-calendar opening and closing PDF composers."""
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
import unittest

from report_engine.session import build_closing_report_pdf, build_opening_report_pdf

START = datetime(2026, 11, 14, 4, tzinfo=timezone.utc)
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


def _report(kind="opening"):
    return {
        "session_start_utc": START.isoformat().replace("+00:00", "Z"),
        "session_end_utc": END.isoformat().replace("+00:00", "Z"),
        "window_start_local": "2026-11-14T00:00:00-04:00",
        "cutoff_local": "2026-11-15T00:00:00-04:00",
        "report_timezone": "America/Santo_Domingo",
        "report_date_local": "2026-11-14",
        "requested_report_date_local": "2026-11-15" if kind == "opening" else "2026-11-14",
        "cutoff_resolution": "previous_local_calendar_day" if kind == "opening" else "completed_historical_local_day",
        "window_semantics": "[start, cutoff)",
        "is_partial": False,
        "data_cutoff_utc": END.isoformat().replace("+00:00", "Z"),
        "generated_at_utc": (END + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        "source": "Binance public REST API",
        "market": "spot",
        "interval": "1h",
        "data_status": "complete",
        "indicator_methodology": {
            "lookback_candles": 250,
            "report_window_excludes_lookback": True,
            "partial_final_interval_excluded": False,
        },
        "binance_account_data_status": "unavailable",
        "us_equity_market_data_status": "not_integrated",
        "opening_forecast_scorecard_status": "not_implemented" if kind == "closing" else "not_applicable",
        "activation_timing_status": "not_automated",
        "executive_summary": "BTC and ETH completed the Dominican local calendar day.",
        "technical_analysis": "Indicator calculations use a separate warm-up series.",
        "symbols": {
            "BTCUSDT": {"candles": _candles("BTCUSDT"), "candle_count": 24,
                        "indicators": {"ema_200": 123.4}, "performance": "+2.1%"},
            "ETHUSDT": {"candles": _candles("ETHUSDT"), "candle_count": 24,
                        "indicators": {"ema_200": 234.5}, "performance": "+1.4%"},
        },
        "bullish_scenario": "Continuation above the session high, conditional on volume.",
        "bearish_scenario": "Failure at resistance and loss of support invalidates the bullish case.",
        "assumptions_and_invalidation": "The opposite range extreme invalidates the scenario.",
        "risks": "Volatility and liquidity risk.",
        "macro_context": "No macro evidence supplied.",
        "news": "No news evidence supplied.",
        "limitations": "Private account and full U.S. equity-market coverage are unavailable.",
        "provenance": [],
        "context_sources": [],
    }


class SessionReportTests(unittest.TestCase):
    def test_opening_pdf_uses_previous_local_day_and_is_readable(self):
        with TemporaryDirectory() as temp:
            path = build_opening_report_pdf(_report("opening"), temp)
            self.assertEqual(path.name, "apertura-mercado_2026-11-15.pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

    def test_closing_pdf_uses_local_date_and_is_readable(self):
        with TemporaryDirectory() as temp:
            path = build_closing_report_pdf(_report("closing"), temp)
            self.assertEqual(path.name, "cierre-mercado_2026-11-14.pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

    def test_both_core_symbols_are_mandatory(self):
        report = _report()
        del report["symbols"]["ETHUSDT"]
        with self.assertRaisesRegex(ValueError, "ETHUSDT"):
            build_opening_report_pdf(report, ".")

    def test_completed_report_must_end_at_next_local_midnight(self):
        report = _report("closing")
        report["session_end_utc"] = "2026-11-15T03:00:00Z"
        report["cutoff_local"] = "2026-11-14T23:00:00-04:00"
        with self.assertRaisesRegex(ValueError, "next local midnight"):
            build_closing_report_pdf(report, ".")

    def test_generation_cannot_precede_session_end(self):
        report = _report("closing")
        report["generated_at_utc"] = START.isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            build_closing_report_pdf(report, ".")

    def test_out_of_window_candle_is_rejected(self):
        report = _report()
        report["symbols"]["BTCUSDT"]["candles"][0]["open_time"] = (
            START - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(ValueError, "outside the report window"):
            build_opening_report_pdf(report, ".")


if __name__ == "__main__":
    unittest.main()
