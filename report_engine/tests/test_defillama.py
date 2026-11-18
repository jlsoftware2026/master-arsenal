"""Offline tests for DeFiLlama protocol research adapter."""
from datetime import datetime, timezone
import unittest

from report_engine.defillama import DeFiLlamaProtocolResearch, _latest_chart, _latest_tvl, _slug

NOW = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)
KEY = "crypto|aave|usdt"


def protocol_fixture():
    return {
        "slug": "aave",
        "name": "Aave",
        "symbol": "AAVE",
        "category": "Lending",
        "chains": ["Ethereum", "Polygon"],
        "gecko_id": "aave",
        "tvl": [
            {"date": 1794873600, "totalLiquidityUSD": 1_000_000_000},
            {"date": 1794902400, "totalLiquidityUSD": 1_100_000_000},
        ],
    }


def fee_fixture(value):
    return {
        "totalDataChart": [
            [1794873600, value - 100],
            [1794902400, value],
        ],
        "total24h": value,
    }


class DeFiLlamaTests(unittest.TestCase):
    def test_slug_validation(self):
        self.assertEqual(_slug("AAVE"), "aave")
        for value in ("", "../aave", "aave?x=1", "aave/v2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _slug(value)

    def test_latest_tvl_uses_latest_valid_point(self):
        self.assertEqual(_latest_tvl(protocol_fixture()["tvl"]), (1_100_000_000.0, 1794902400))

    def test_latest_chart_uses_latest_valid_point(self):
        self.assertEqual(_latest_chart([[1794873600, 4], [1794902400, 5]]), (5.0, 1794902400))

    def test_latest_chart_rejects_invalid_values(self):
        self.assertIsNone(_latest_chart([["bad", 4], [1794873600, float("nan")]]))

    def test_requires_explicit_protocol_instrument_attribution(self):
        adapter = DeFiLlamaProtocolResearch(fetch_json=lambda *args: protocol_fixture())
        with self.assertRaisesRegex(ValueError, "attribution_basis"):
            adapter.fetch_protocol_research(protocol_slug="aave", instrument_key=KEY,
                                            attribution_basis="", retrieved_at=NOW)

    def test_fetches_exact_protocol_and_fee_metric_types(self):
        urls = []
        def fake(url, headers, timeout):
            urls.append(url)
            if "/protocol/" in url:
                return protocol_fixture()
            if "dailyFees" in url:
                return fee_fixture(300)
            if "dailyRevenue" in url:
                return fee_fixture(200)
            return fee_fixture(50)
        adapter = DeFiLlamaProtocolResearch(fetch_json=fake)
        result = adapter.fetch_protocol_research(
            protocol_slug="AAVE", instrument_key=KEY,
            attribution_basis="Issuer protocol documentation maps this token to the protocol governance system.",
            retrieved_at=NOW,
        )
        self.assertIn("https://api.llama.fi/protocol/aave", urls[0])
        self.assertEqual(len(result["facts"]), 4)
        self.assertEqual(result["data_quality_status"], "evidence_recorded")
        self.assertEqual(result["protocol_instrument_attribution"]["status"],
                         "caller_supplied_not_independently_verified")

    def test_fees_revenue_and_holders_revenue_are_separate(self):
        def fake(url, headers, timeout):
            if "/protocol/" in url:
                return protocol_fixture()
            if "dailyFees" in url:
                return fee_fixture(300)
            if "dailyRevenue" in url:
                return fee_fixture(200)
            return fee_fixture(50)
        result = DeFiLlamaProtocolResearch(fetch_json=fake).fetch_protocol_research(
            protocol_slug="aave", instrument_key=KEY,
            attribution_basis="Explicitly documented protocol mapping.", retrieved_at=NOW,
        )
        dims = {fact["label"].split()[-1]: fact["dimension"] for fact in result["facts"]}
        self.assertEqual(dims["fees"], "protocol_fees")
        self.assertEqual(dims["revenue"], "protocol_revenue")

    def test_missing_metric_is_not_zero_filled(self):
        def fake(url, headers, timeout):
            if "/protocol/" in url:
                return protocol_fixture()
            if "dailyFees" in url:
                return fee_fixture(300)
            raise RuntimeError("not covered")
        result = DeFiLlamaProtocolResearch(fetch_json=fake).fetch_protocol_research(
            protocol_slug="aave", instrument_key=KEY,
            attribution_basis="Explicitly documented protocol mapping.", retrieved_at=NOW,
        )
        self.assertIn("dailyRevenue", result["missing_metrics"])
        self.assertNotIn("protocol revenue", [f["label"] for f in result["facts"]])

    def test_rejects_mismatched_protocol_slug(self):
        fixture = protocol_fixture()
        fixture["slug"] = "other-protocol"
        adapter = DeFiLlamaProtocolResearch(fetch_json=lambda *args: fixture)
        with self.assertRaisesRegex(ValueError, "different protocol slug"):
            adapter.fetch_protocol_research(protocol_slug="aave", instrument_key=KEY,
                                            attribution_basis="Documented mapping.",
                                            retrieved_at=NOW)

    def test_tvl_missing_is_explicit(self):
        fixture = protocol_fixture()
        fixture["tvl"] = []
        def fake(url, headers, timeout):
            if "/protocol/" in url:
                return fixture
            return {}
        result = DeFiLlamaProtocolResearch(fetch_json=fake).fetch_protocol_research(
            protocol_slug="aave", instrument_key=KEY,
            attribution_basis="Documented mapping.", retrieved_at=NOW,
        )
        self.assertIn("protocol_tvl", result["missing_metrics"])
        self.assertFalse(any(f["dimension"] == "protocol_usage" for f in result["facts"]))

    def test_rejects_invalid_protocol_response(self):
        adapter = DeFiLlamaProtocolResearch(fetch_json=lambda *args: [])
        with self.assertRaisesRegex(ValueError, "JSON object"):
            adapter.fetch_protocol_research(protocol_slug="aave", instrument_key=KEY,
                                            attribution_basis="Documented mapping.",
                                            retrieved_at=NOW)


if __name__ == "__main__":
    unittest.main()
