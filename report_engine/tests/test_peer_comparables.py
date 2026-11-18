"""Tests for explicit-criteria peer valuation and median calculations."""
import unittest

from report_engine.peer_comparables import calculate_peer_comparables


def entity(key, name, *, market_cap, earnings, revenue, equity, asset_class="listed_equity"):
    return {
        "instrument_key": key,
        "asset_class": asset_class,
        "name": name,
        "facts": [
            {"fact_id": f"{key}-ni", "instrument_key": key, "dimension": "net_income",
             "value": str(earnings), "unit": "USD", "as_of_utc": "2025-12-31T23:59:59Z",
             "source_url": "https://example.org/filing", "evidence_quality": "verified_source"},
            {"fact_id": f"{key}-rev", "instrument_key": key, "dimension": "revenue",
             "value": str(revenue), "unit": "USD", "as_of_utc": "2025-12-31T23:59:59Z",
             "source_url": "https://example.org/filing", "evidence_quality": "verified_source"},
            {"fact_id": f"{key}-eq", "instrument_key": key, "dimension": "stockholders_equity",
             "value": str(equity), "unit": "USD", "as_of_utc": "2025-12-31T23:59:59Z",
             "source_url": "https://example.org/filing", "evidence_quality": "verified_source"},
        ],
        "market_cap": {
            "value": str(market_cap), "unit": "USD", "as_of_utc": "2026-11-17T16:00:00Z",
            "source_id": f"{key}-market-cap", "source_url": "https://example.org/market-cap",
        },
        "earnings_period_basis": "annual",
    }


def peer(entity_record):
    entity_record["selection_criteria"] = {
        "sector": "Healthcare",
        "business_model": "Branded therapeutics",
        "geography": "United States",
        "market_cap_band": "Large cap",
        "revenue_model": "Product sales",
        "accounting_basis": "US GAAP",
        "rationale": "Comparable commercial-stage product mix and operating model.",
    }
    return entity_record


class PeerComparablesTests(unittest.TestCase):
    def setUp(self):
        self.candidate = entity("listed_equity|cand", "Candidate", market_cap=5000,
                                earnings=100, revenue=1000, equity=2000)
        self.peers = [
            peer(entity("listed_equity|p1", "Peer One", market_cap=2000,
                        earnings=100, revenue=500, equity=1000)),
            peer(entity("listed_equity|p2", "Peer Two", market_cap=3000,
                        earnings=100, revenue=600, equity=1200)),
            peer(entity("listed_equity|p3", "Peer Three", market_cap=6000,
                        earnings=100, revenue=1000, equity=2000)),
        ]

    def test_calculates_medians_and_candidate_premium_discount(self):
        result = calculate_peer_comparables(self.candidate, self.peers)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["peer_count"], 3)
        self.assertEqual(result["metrics"]["price_to_earnings"]["median"], "30.0000")
        self.assertEqual(result["metrics"]["price_to_sales"]["median"], "5.0000")
        self.assertEqual(result["metrics"]["price_to_book"]["median"], "2.5000")
        self.assertEqual(
            result["metrics"]["price_to_earnings"]["candidate_premium_discount_pct_vs_median"],
            "66.6667",
        )

    def test_fewer_than_minimum_peers_does_not_publish_medians(self):
        result = calculate_peer_comparables(self.candidate, self.peers[:2])
        self.assertEqual(result["status"], "insufficient_peer_coverage")
        self.assertEqual(result["metrics"], {})

    def test_negative_earnings_peer_is_excluded_only_from_pe_median(self):
        peers = list(self.peers)
        peers[0] = peer(entity("listed_equity|p1", "Peer One", market_cap=2000,
                               earnings=-100, revenue=500, equity=1000))
        result = calculate_peer_comparables(self.candidate, peers)
        self.assertNotIn("price_to_earnings", result["metrics"])
        self.assertIn("price_to_earnings", result["missing_metrics"])
        self.assertIn("price_to_sales", result["metrics"])
        self.assertEqual(result["status"], "partial")

    def test_peer_criteria_are_mandatory(self):
        peers = list(self.peers)
        peers[0] = dict(peers[0])
        peers[0]["selection_criteria"] = {"sector": "Healthcare"}
        with self.assertRaisesRegex(ValueError, "selection_criteria.business_model"):
            calculate_peer_comparables(self.candidate, peers)

    def test_duplicate_or_candidate_peer_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            calculate_peer_comparables(self.candidate, [self.peers[0], self.peers[0]])
        with self.assertRaisesRegex(ValueError, "exclude the candidate"):
            calculate_peer_comparables(self.candidate, [peer(self.candidate)])

    def test_mixed_equity_asset_classes_are_rejected(self):
        peers = list(self.peers)
        peers[0] = peer(entity("tokenized_equity|p1", "Tokenized Peer", market_cap=2000,
                               earnings=100, revenue=500, equity=1000,
                               asset_class="tokenized_equity"))
        with self.assertRaisesRegex(ValueError, "same equity asset class"):
            calculate_peer_comparables(self.candidate, peers)

    def test_minimum_peer_count_must_be_at_least_two(self):
        with self.assertRaisesRegex(ValueError, "at least 2"):
            calculate_peer_comparables(self.candidate, self.peers, minimum_peer_count=1)


if __name__ == "__main__":
    unittest.main()
