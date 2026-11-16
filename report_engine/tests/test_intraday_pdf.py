"""Offline tests for the intraday PDF reporting contract."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from report_engine import build_intraday_snapshot_pdf
from report_engine.intraday import _us_market_rows
from report_engine.audit import audit_market_report_artifact


def fixture():
    return {
        "window_start_utc": "2026-11-13T04:00:00Z",
        "report_timezone": "America/Santo_Domingo",
        "report_date_local": "2026-11-13",
        "requested_report_date_local": "2026-11-13",
        "cutoff_resolution": "explicit_utc_cutoff",
        "window_start_local": "2026-11-13T00:00:00-04:00",
        "cutoff_local": "2026-11-13T12:30:00-04:00",
        "is_partial": True,
        "window_semantics": "[start, cutoff)",
        "cutoff_utc": "2026-11-13T16:30:00Z",
        "generated_at_utc": "2026-11-13T16:31:00Z",
        "source": "Binance public REST API (fixture)",
        "market": "spot",
        "interval": "1h",
        "data_status": "fixture_only",
        "data_cutoff_utc": "2026-11-13T16:00:00Z",
        "binance_account_data_status": "unavailable",
        "us_equity_market_data_status": "not_integrated",
        "us_equity_session_state": "not_available",
        "comparison_basis": "Ventana del día local; el período móvil de 24 horas es distinto",
        "macro_context": "No hay contexto macroeconómico en este fixture.",
        "news_context": "No hay noticias en este fixture.",
        "provenance": [{"source": "Binance", "retrieved_at_utc": "2026-11-13T16:30:30Z", "note": "Fixture"}],
        "context_sources": [{
            "publisher": "Feed de prueba", "kind": "macro", "status": "ok",
            "retrieved_at_utc": "2026-11-13T16:30:30Z", "matching_items": 0,
            "feed_url": "https://example.com/feed.xml",
        }],
        "executive_summary": [
            "Punto uno de prueba.", "Punto dos de prueba.", "Punto tres de prueba.",
            "Punto cuatro de prueba.", "Punto cinco de prueba.", "Punto seis de prueba.",
            "Punto siete de prueba.",
        ],
        "symbols": {
            symbol: {
                "candle_count": 12,
                "first_open_time_utc": "2026-11-13T04:00:00Z",
                "last_close_time_utc": "2026-11-13T15:59:59Z",
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
    def test_market_snapshot_rows_format_sector_etfs_and_yield_bps(self):
        rows, unavailable = _us_market_rows({
            "groups": {
                "sectors": [{
                    "status": "ok", "name": "Technology", "symbol": "XLK",
                    "unit": "ETF_USD", "last_price": 250.5,
                    "change_percent": 1.25, "observed_at_et": "2026-11-16T10:00:00-05:00",
                }],
                "rates": [{
                    "status": "ok", "name": "U.S. Treasury 10Y yield", "symbol": "^TNX",
                    "unit": "yield_percent", "last_price": 4.25,
                    "change_basis_points": -2.0, "observed_at_et": "2026-11-16T10:00:00-05:00",
                }],
            }
        })
        self.assertEqual(rows[0][3], "$250.50")
        self.assertEqual(rows[1][4], "-2.0 pb")
        self.assertEqual(unavailable, [])



    def test_creates_named_readable_pdf(self):
        with TemporaryDirectory() as temp:
            result = build_intraday_snapshot_pdf(fixture(), temp)
            self.assertEqual(result.name, "snapshot-mercado_2026-11-13_12-30.pdf")
            payload = result.read_bytes()
            self.assertTrue(payload.startswith(b"%PDF-"))
            self.assertIn(b"%%EOF", payload[-2048:])
            self.assertGreater(len(payload), 1000)

    def test_intraday_pdf_passes_independent_content_and_localization_audit(self):
        with TemporaryDirectory() as temp:
            artifact = build_intraday_snapshot_pdf(fixture(), temp)
            audit = audit_market_report_artifact(artifact, "intraday")
            self.assertEqual(audit["status"], "passed", audit["missing_markers"])
            import pymupdf as fitz
            with fitz.open(artifact) as document:
                extracted = " ".join(page.get_text("text") for page in document)
            for point in ("Punto uno de prueba.", "Punto siete de prueba."):
                self.assertIn(point, extracted)

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

    def test_rejects_local_timestamp_that_violates_iana_timezone_rules(self):
        data = fixture()
        data["window_start_local"] = "2026-11-13T01:00:00-03:00"
        data["cutoff_local"] = "2026-11-13T13:30:00-03:00"
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "IANA America/Santo_Domingo"):
                build_intraday_snapshot_pdf(data, temp)

    def test_rejects_wrong_window_start(self):
        data = fixture()
        data["window_start_utc"] = "2026-11-13T05:00:00Z"
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Local and UTC"):
                build_intraday_snapshot_pdf(data, temp)

    def test_rejects_candle_closing_after_exclusive_cutoff(self):
        data = fixture()
        data["symbols"]["BTCUSDT"]["last_close_time_utc"] = "2026-11-13T16:59:59Z"
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "exclusive cutoff"):
                build_intraday_snapshot_pdf(data, temp)

    def test_rejects_cutoff_before_start(self):
        data = fixture()
        data["cutoff_utc"] = "2026-11-13T00:00:00Z"
        with TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                build_intraday_snapshot_pdf(data, temp)


if __name__ == "__main__":
    unittest.main()
