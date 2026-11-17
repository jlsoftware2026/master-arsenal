"""Tests for standalone pre-investment opportunity PDF composition."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from report_engine.instruments import build_instrument_record
from report_engine.opportunity import build_opportunity_report_pdf
from report_engine.research import build_research_packet
from report_engine.scenarios import calculate_long_scenarios
from report_engine.position_sizing import calculate_cash_position_size

NOW = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)
KEY = "listed_equity|exm|usd|example corp|nasdaq"


def report_fixture():
    instrument = build_instrument_record({
        "asset_class": "listed_equity", "name": "Example Corp",
        "symbol": "EXM", "quote_currency": "USD",
        "issuer": "Example Corp", "exchange": "NASDAQ",
    })
    facts = [{
        "fact_id": "fact-1", "instrument_key": KEY,
        "dimension": "revenue", "label": "FY revenue", "value": "1000000",
        "unit": "USD", "source_kind": "issuer_disclosure",
        "evidence_quality": "verified_source", "source_name": "Issuer filing",
        "source_url": "https://example.com/filing",
        "source_reference": "FY2025 revenue note",
        "as_of_utc": "2026-11-17T15:00:00Z",
        "retrieved_at_utc": "2026-11-17T15:30:00Z",
    }]
    packet = build_research_packet(KEY, facts, now=NOW,
                                   freshness_limits_hours={"revenue": 24})
    scenarios = calculate_long_scenarios(
        instrument_key=KEY, quote_currency="USD",
        reference_entry_price=100, invalidation_price=80,
        bull_case={"price": 150, "assumptions": "Launch succeeds."},
        base_case={"price": 115, "assumptions": "Adoption is moderate."},
        bear_case={"price": 65, "assumptions": "Launch is delayed."},
        invalidation_basis="Thesis fails below 80.", horizon="12 months",
        as_of_utc="2026-11-17T16:00:00Z",
    )
    sizing = calculate_cash_position_size(
        instrument_key=KEY, as_of_utc="2026-11-17T16:00:00Z",
        entry_price_basis="Hypothetical reference price.",
        invalidation_basis="Thesis invalidation assumption.",
        available_capital=10000, quote_currency="USD",
        entry_price=100, invalidation_price=80,
        risk_budget_pct=1, max_allocation_pct=50,
    )
    return {
        "generated_at_utc": "2026-11-17T16:00:00Z",
        "instrument": instrument, "research_packet": packet,
        "conclusion": "potential_candidate_for_further_diligence",
        "executive_summary": ["Evidence is preliminary.", "Further diligence is required."],
        "scenarios": scenarios, "position_sizing": sizing,
        "risks": ["Competition may pressure margins."],
        "thesis_invalidation": ["Clinical or commercial milestones fail."],
        "provider_status": {"sec": "fixture evidence only"},
    }


class OpportunityPdfTests(unittest.TestCase):
    def test_builds_valid_opportunity_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = build_opportunity_report_pdf(report_fixture(), directory)
            self.assertTrue(path.is_file())
            self.assertEqual(path.suffix, ".pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
            self.assertIn("oportunidad-listed_equity-EXM", path.name)

    def test_rejects_mismatched_research_packet_instrument(self):
        report = report_fixture()
        report["research_packet"]["instrument_key"] = "different"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "does not match instrument"):
                build_opportunity_report_pdf(report, directory)

    def test_insufficient_evidence_cannot_support_potential_candidate(self):
        report = report_fixture()
        report["research_packet"] = build_research_packet(KEY, [], now=NOW)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "insufficient evidence"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_unknown_conclusion(self):
        report = report_fixture()
        report["conclusion"] = "strong_buy"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "conclusion"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_scenario_for_different_instrument(self):
        report = report_fixture()
        report["scenarios"]["instrument_key"] = "different"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "scenario instrument_key"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_probability_or_expected_return_fields(self):
        report = report_fixture()
        report["scenarios"]["probabilities"] = {"bull": 0.5}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "must not contain"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_position_sizing_for_different_instrument(self):
        report = report_fixture()
        report["position_sizing"]["instrument_key"] = "different"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "position sizing instrument_key"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_invalid_fact_in_packet(self):
        report = report_fixture()
        report["research_packet"]["facts"][0]["instrument_key"] = "different"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "research fact"):
                build_opportunity_report_pdf(report, directory)


if __name__ == "__main__":
    unittest.main()
