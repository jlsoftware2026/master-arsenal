"""Offline tests for attributed U.S. market snapshot acquisition."""
from datetime import datetime, timezone
import json
import unittest

from report_engine.us_market_data import collect_us_market_snapshot


AS_OF = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.payload[:limit]


def chart_payload(closes=(100.0, 102.0), previous=95.0):
    stamps = [
        int(datetime(2026, 11, 16, 14, 55, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 11, 16, 15, 5, tzinfo=timezone.utc).timestamp()),
    ]
    return json.dumps({
        "chart": {
            "result": [{
                "meta": {
                    "chartPreviousClose": previous,
                    "currency": "USD",
                    "fullExchangeName": "Test Exchange",
                },
                "timestamp": stamps,
                "indicators": {"quote": [{"close": list(closes)}]},
            }],
            "error": None,
        }
    }).encode("utf-8")


class USMarketDataTests(unittest.TestCase):
    def test_cutoff_excludes_future_quotes_and_retains_source_attribution(self):
        catalog = {"indices": (("S&P 500", "^GSPC", "index_points"),)}
        result = collect_us_market_snapshot(
            AS_OF, instruments=catalog,
            opener=lambda request, timeout: FakeResponse(chart_payload()),
        )
        item = result["groups"]["indices"][0]
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["instrument_snapshot_status"], "complete")
        self.assertEqual(item["last_price"], 100.0)
        self.assertEqual(item["observed_at_utc"], "2026-11-16T14:55:00Z")
        self.assertEqual(item["change"], 5.0)
        self.assertIn("finance.yahoo.com", item["source_url"])
        self.assertEqual(item["source"], result["provider"])

    def test_missing_symbol_is_explicitly_unavailable(self):
        catalog = {"indices": (("S&P 500", "^GSPC", "index_points"),)}
        def fail(request, timeout):
            raise TimeoutError("fixture timeout")
        result = collect_us_market_snapshot(AS_OF, instruments=catalog, opener=fail)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["unavailable_symbols"], ["^GSPC"])
        self.assertIsNone(result["groups"]["indices"][0]["last_price"])

    def test_sector_leaders_and_laggards_are_ranked_only_from_available_returns(self):
        catalog = {
            "sectors": (
                ("Technology", "XLK", "ETF_USD"),
                ("Energy", "XLE", "ETF_USD"),
            )
        }
        def opener(request, timeout):
            if "XLK" in request.full_url:
                return FakeResponse(chart_payload(closes=(110.0, 111.0), previous=100.0))
            return FakeResponse(chart_payload(closes=(90.0, 89.0), previous=100.0))
        result = collect_us_market_snapshot(AS_OF, instruments=catalog, opener=opener)
        self.assertEqual(result["sector_leaders"][0]["symbol"], "XLK")
        self.assertEqual(result["sector_laggards"][0]["symbol"], "XLE")

    def test_treasury_ten_year_yield_is_normalized_from_yahoo_tenths_scale(self):
        catalog = {"rates": (("U.S. Treasury 10Y yield", "^TNX", "yield_percent_x10"),)}
        result = collect_us_market_snapshot(
            AS_OF, instruments=catalog,
            opener=lambda request, timeout: FakeResponse(
                chart_payload(closes=(42.5, 43.0), previous=42.0)
            ),
        )
        item = result["groups"]["rates"][0]
        self.assertEqual(item["unit"], "yield_percent")
        self.assertEqual(item["last_price"], 4.25)
        self.assertAlmostEqual(item["change_basis_points"], 5.0)

    def test_invalid_naive_cutoff_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            collect_us_market_snapshot(datetime(2026, 11, 16, 15, 0))


if __name__ == "__main__":
    unittest.main()
