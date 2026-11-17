"""Tests for transparent same-period financial ratio calculations."""
import unittest

from report_engine.fundamentals import calculate_financial_ratios

KEY = "listed_equity|exm|usd|example corp|nasdaq"
PERIOD = "2025-12-31T23:59:59Z"


def fact(dimension, value, *, fact_id=None, period=PERIOD, unit="USD"):
    return {
        "fact_id": fact_id or dimension,
        "instrument_key": KEY,
        "dimension": dimension,
        "value": str(value),
        "unit": unit,
        "as_of_utc": period,
    }


class FinancialRatioTests(unittest.TestCase):
    def test_calculates_margins_fcf_liquidity_and_returns(self):
        facts = [
            fact("revenue", 1000), fact("gross_profit", 600),
            fact("operating_income", 200), fact("net_income", 100),
            fact("operating_cash_flow", 150), fact("capital_expenditures", -50),
            fact("current_assets", 500), fact("current_liabilities", 250),
            fact("cash_and_equivalents", 100), fact("total_assets", 2000),
            fact("stockholders_equity", 1000),
        ]
        result = calculate_financial_ratios(facts, instrument_key=KEY)
        self.assertEqual(result["metrics"]["gross_margin_pct"]["value"], "60.0000")
        self.assertEqual(result["metrics"]["operating_margin_pct"]["value"], "20.0000")
        self.assertEqual(result["metrics"]["net_margin_pct"]["value"], "10.0000")
        self.assertEqual(result["metrics"]["free_cash_flow"]["value"], "100.00")
        self.assertEqual(result["metrics"]["free_cash_flow_margin_pct"]["value"], "10.0000")
        self.assertEqual(result["metrics"]["current_ratio"]["value"], "2.0000")
        self.assertEqual(result["metrics"]["cash_to_current_liabilities"]["value"], "0.4000")
        self.assertEqual(result["metrics"]["period_end_roa_pct"]["value"], "5.0000")
        self.assertEqual(result["metrics"]["period_end_roe_pct"]["value"], "10.0000")
        self.assertEqual(result["status"], "complete")

    def test_missing_inputs_are_not_zero_filled(self):
        result = calculate_financial_ratios([fact("revenue", 1000)], instrument_key=KEY)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertNotIn("operating_margin_pct", result["metrics"])
        self.assertIn("operating_margin_pct", result["missing_metrics"])

    def test_mismatched_periods_are_not_combined(self):
        facts = [fact("revenue", 1000), fact("operating_income", 200, period="2024-12-31T23:59:59Z")]
        result = calculate_financial_ratios(facts, instrument_key=KEY)
        self.assertNotIn("operating_margin_pct", result["metrics"])
        self.assertIn("same reporting period", result["missing_metrics"]["operating_margin_pct"])

    def test_mismatched_currency_units_are_not_combined(self):
        facts = [fact("revenue", 1000, unit="USD"), fact("operating_income", 200, unit="EUR")]
        result = calculate_financial_ratios(facts, instrument_key=KEY)
        self.assertIn("different units", result["missing_metrics"]["operating_margin_pct"])

    def test_zero_denominator_is_not_calculated(self):
        facts = [fact("revenue", 0), fact("operating_income", 20)]
        result = calculate_financial_ratios(facts, instrument_key=KEY)
        self.assertNotIn("operating_margin_pct", result["metrics"])
        self.assertIn("zero", result["missing_metrics"]["operating_margin_pct"])

    def test_ambiguous_latest_dimension_is_not_selected(self):
        facts = [fact("revenue", 1000, fact_id="r1"), fact("revenue", 1100, fact_id="r2"),
                 fact("operating_income", 200)]
        result = calculate_financial_ratios(facts, instrument_key=KEY)
        self.assertIn("Ambiguous", result["missing_metrics"]["operating_margin_pct"])

    def test_rejects_fact_for_different_instrument(self):
        with self.assertRaisesRegex(ValueError, "instrument_key"):
            calculate_financial_ratios([fact("revenue", 1000) | {"instrument_key": "other"}],
                                       instrument_key=KEY)

    def test_capex_sign_is_normalized_for_fcf(self):
        facts = [fact("operating_cash_flow", 150), fact("capital_expenditures", 50)]
        result = calculate_financial_ratios(facts, instrument_key=KEY)
        self.assertEqual(result["metrics"]["free_cash_flow"]["value"], "100.00")


if __name__ == "__main__":
    unittest.main()
