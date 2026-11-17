"""Tests for source-attributed investment research evidence."""
from datetime import datetime, timedelta, timezone
import unittest

from report_engine.research import (
    assess_freshness,
    build_research_packet,
    normalize_research_fact,
)

NOW = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)
KEY = "listed_equity|exm|usd|example corp|nasdaq"


def sourced_fact(**overrides):
    fact = {
        "fact_id": "fact-001", "instrument_key": KEY,
        "dimension": "revenue", "label": "FY revenue",
        "value": "125000000", "unit": "USD",
        "source_kind": "issuer_disclosure", "evidence_quality": "verified_source",
        "source_name": "Example Corp annual report",
        "source_url": "https://example.com/investors/annual-report",
        "source_reference": "FY2025 consolidated statements, revenue line",
        "as_of_utc": "2026-10-31T00:00:00Z",
        "retrieved_at_utc": "2026-11-17T15:00:00Z",
    }
    fact.update(overrides)
    return fact


class ResearchEvidenceTests(unittest.TestCase):
    def test_normalizes_valid_sourced_fact(self):
        result = normalize_research_fact(sourced_fact())
        self.assertEqual(result["dimension"], "revenue")
        self.assertEqual(result["source_kind"], "issuer_disclosure")
        self.assertEqual(result["source_reference"], "FY2025 consolidated statements, revenue line")

    def test_rejects_unknown_dimension(self):
        with self.assertRaisesRegex(ValueError, "dimension"):
            normalize_research_fact(sourced_fact(dimension="guaranteed_return"))

    def test_rejects_unknown_source_kind(self):
        with self.assertRaisesRegex(ValueError, "source_kind"):
            normalize_research_fact(sourced_fact(source_kind="social_media_rumor"))

    def test_external_source_requires_https(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            normalize_research_fact(sourced_fact(source_url="http://example.com/report"))

    def test_verified_fact_requires_source_reference(self):
        fact = sourced_fact()
        fact.pop("source_reference")
        with self.assertRaisesRegex(ValueError, "source_reference"):
            normalize_research_fact(fact)

    def test_assumption_requires_note_and_is_not_external_fact(self):
        fact = {
            "fact_id": "assumption-1", "instrument_key": KEY,
            "dimension": "valuation", "label": "Illustrative exit multiple",
            "value": 18, "unit": "x",
            "source_kind": "analyst_assumption", "evidence_quality": "estimated",
            "assumption_note": "Scenario input for sensitivity analysis.",
            "as_of_utc": "2026-11-17T15:00:00Z",
            "retrieved_at_utc": "2026-11-17T15:00:00Z",
        }
        result = normalize_research_fact(fact)
        self.assertIn("assumption_note", result)
        self.assertNotIn("source_url", result)

    def test_assumption_cannot_claim_external_source_url(self):
        fact = {
            "fact_id": "assumption-1", "instrument_key": KEY,
            "dimension": "valuation", "label": "Illustrative multiple",
            "value": 18, "unit": "x", "source_kind": "analyst_assumption",
            "evidence_quality": "estimated", "assumption_note": "Scenario input.",
            "source_url": "https://example.com",
            "as_of_utc": "2026-11-17T15:00:00Z",
            "retrieved_at_utc": "2026-11-17T15:00:00Z",
        }
        with self.assertRaisesRegex(ValueError, "must not be represented"):
            normalize_research_fact(fact)

    def test_rejects_naive_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            normalize_research_fact(sourced_fact(as_of_utc="2026-11-17T15:00:00"))

    def test_rejects_non_finite_numeric_value(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            normalize_research_fact(sourced_fact(value=float("nan")))

    def test_freshness_is_not_claimed_without_policy(self):
        fact = normalize_research_fact(sourced_fact())
        result = assess_freshness(fact, now=NOW, max_age=None)
        self.assertEqual(result["status"], "not_assessed")

    def test_stale_fact_is_flagged_by_explicit_policy(self):
        packet = build_research_packet(KEY, [sourced_fact()], now=NOW,
                                       freshness_limits_hours={"revenue": 24})
        self.assertEqual(packet["data_quality"]["status"], "insufficient_evidence")
        self.assertEqual(packet["data_quality"]["stale_fact_ids"], ["fact-001"])

    def test_fresh_fact_is_recorded(self):
        fact = sourced_fact(as_of_utc="2026-11-17T15:30:00Z")
        packet = build_research_packet(KEY, [fact], now=NOW,
                                       freshness_limits_hours={"revenue": 24})
        self.assertEqual(packet["facts"][0]["freshness"]["status"], "fresh")
        self.assertEqual(packet["data_quality"]["status"], "evidence_recorded")

    def test_future_dated_fact_is_not_accepted_as_fresh(self):
        fact = sourced_fact(as_of_utc="2026-11-17T16:01:00Z")
        packet = build_research_packet(KEY, [fact], now=NOW,
                                       freshness_limits_hours={"revenue": 24})
        self.assertEqual(packet["data_quality"]["future_dated_fact_ids"], ["fact-001"])
        self.assertEqual(packet["data_quality"]["status"], "insufficient_evidence")

    def test_rejects_fact_for_different_instrument(self):
        with self.assertRaisesRegex(ValueError, "instrument_key"):
            build_research_packet("different-key", [sourced_fact()], now=NOW)

    def test_rejects_duplicate_fact_ids(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            build_research_packet(KEY, [sourced_fact(), sourced_fact()], now=NOW)

    def test_missing_facts_is_insufficient_evidence(self):
        packet = build_research_packet(KEY, [], now=NOW)
        self.assertEqual(packet["fact_count"], 0)
        self.assertEqual(packet["data_quality"]["status"], "insufficient_evidence")

    def test_unassessed_freshness_is_explicit(self):
        packet = build_research_packet(KEY, [sourced_fact()], now=NOW)
        self.assertEqual(packet["data_quality"]["status"], "freshness_not_assessed")
        self.assertEqual(packet["data_quality"]["freshness_not_assessed_fact_ids"], ["fact-001"])


if __name__ == "__main__":
    unittest.main()
