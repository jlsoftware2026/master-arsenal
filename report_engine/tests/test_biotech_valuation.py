"""Offline tests for stage-aware biotech valuation and runway calculations."""
import unittest
from report_engine.biotech_valuation import assess_biotech_valuation

KEY = "listed_equity|exm|usd|example biotech|nasdaq"
CUTOFF = "2026-11-17T16:00:00Z"

def obs(value, source_id, currency="USD", as_of=CUTOFF, quality="verified_source"):
    return {"instrument_key": KEY, "value": str(value), "currency": currency, "as_of_utc": as_of,
            "source_id": source_id, "source_url": "https://example.org/source",
            "evidence_quality": quality}

class BiotechValuationTests(unittest.TestCase):
    def test_clinical_company_runway(self):
        result = assess_biotech_valuation(instrument_key=KEY, development_stage="clinical",
            analysis_cutoff_utc=CUTOFF, cash=obs(120, "cash-1"),
            quarterly_net_cash_burn=obs(30, "burn-1"))
        self.assertEqual(result["metrics"]["cash_runway_months"]["value"], "12.00")
        self.assertNotIn("price_to_sales", result["metrics"])

    def test_pre_revenue_no_sales_multiple(self):
        result = assess_biotech_valuation(instrument_key=KEY, development_stage="preclinical",
            analysis_cutoff_utc=CUTOFF, market_cap=obs(500, "cap"), annual_revenue=obs(0, "revenue"))
        self.assertNotIn("price_to_sales", result["metrics"])

    def test_commercial_sales_multiple(self):
        result = assess_biotech_valuation(instrument_key=KEY, development_stage="commercial",
            analysis_cutoff_utc=CUTOFF, market_cap=obs(1000, "cap"),
            annual_revenue=obs(200, "revenue"))
        self.assertEqual(result["metrics"]["price_to_sales"]["value"], "5.00")

    def test_zero_burn_blocks_runway(self):
        result = assess_biotech_valuation(instrument_key=KEY, development_stage="clinical",
            analysis_cutoff_utc=CUTOFF, cash=obs(100, "cash"),
            quarterly_net_cash_burn=obs(0, "burn"))
        self.assertNotIn("cash_runway_months", result["metrics"])

    def test_currency_mismatch_blocks_runway(self):
        result = assess_biotech_valuation(instrument_key=KEY, development_stage="clinical",
            analysis_cutoff_utc=CUTOFF, cash=obs(100, "cash", "USD"),
            quarterly_net_cash_burn=obs(20, "burn", "EUR"))
        self.assertNotIn("cash_runway_months", result["metrics"])

    def test_future_dated_market_cap_rejected(self):
        result = assess_biotech_valuation(instrument_key=KEY, development_stage="commercial",
            analysis_cutoff_utc=CUTOFF,
            market_cap=obs(1000, "cap", as_of="2026-11-18T00:00:00Z"),
            annual_revenue=obs(200, "revenue"))
        self.assertNotIn("price_to_sales", result["metrics"])

    def test_catalyst_has_no_success_probability(self):
        result = assess_biotech_valuation(instrument_key=KEY, development_stage="clinical",
            analysis_cutoff_utc=CUTOFF, clinical_catalysts=[{
                "nct_id": "NCT01234567", "phase": ["PHASE3"], "status": "RECRUITING",
                "primary_completion_date": "2027-06-30",
                "source_url": "https://clinicaltrials.gov/study/NCT01234567",
                "attribution_basis": "Issuer filing reference."}])
        self.assertIn("not an efficacy", result["clinical_catalysts"][0]["warning"])

    def test_missing_provenance_rejected(self):
        bad = obs(100, "cash"); bad.pop("source_url")
        with self.assertRaisesRegex(ValueError, "source_url"):
            assess_biotech_valuation(instrument_key=KEY, development_stage="clinical",
                analysis_cutoff_utc=CUTOFF, cash=bad, quarterly_net_cash_burn=obs(20, "burn"))

    def test_invalid_stage_rejected(self):
        with self.assertRaisesRegex(ValueError, "development_stage"):
            assess_biotech_valuation(instrument_key=KEY, development_stage="device",
                analysis_cutoff_utc=CUTOFF)

if __name__ == "__main__":
    unittest.main()
