"""Tests for transparent long-only price scenario calculations."""
import unittest

from report_engine.scenarios import calculate_long_scenarios

BASE = {
    "instrument_key": "listed_equity|exm|usd|example corp|nasdaq",
    "quote_currency": "USD",
    "reference_entry_price": "100",
    "invalidation_price": "80",
    "bull_case": {"price": "150", "assumptions": "Successful launch and margin expansion."},
    "base_case": {"price": "115", "assumptions": "Moderate adoption and stable margins."},
    "bear_case": {"price": "65", "assumptions": "Launch delay and competitive pressure."},
    "invalidation_basis": "Thesis invalidated below the prior structural support assumption.",
    "horizon": "12 months",
    "as_of_utc": "2026-11-17T16:00:00Z",
}


class ScenarioCalculationTests(unittest.TestCase):
    def calculate(self, **changes):
        args = dict(BASE)
        args.update(changes)
        return calculate_long_scenarios(**args)

    def test_calculates_returns_and_reward_risk(self):
        result = self.calculate()
        self.assertEqual(result["scenarios"]["bull"]["return_pct"], "50.0000")
        self.assertEqual(result["scenarios"]["base"]["return_pct"], "15.0000")
        self.assertEqual(result["scenarios"]["bear"]["return_pct"], "-35.0000")
        self.assertEqual(result["downside_to_invalidation_pct"], "20.0000")
        self.assertEqual(result["bull_reward_to_risk"], "2.5000")
        self.assertEqual(result["base_reward_to_risk"], "0.7500")

    def test_scenarios_are_explicitly_hypothetical(self):
        result = self.calculate()
        self.assertEqual(result["analysis_type"], "hypothetical_long_only")
        self.assertIn("not an order", result["hypothetical_inputs"]["entry_price_basis"])

    def test_does_not_generate_probabilities_or_expected_return(self):
        result = self.calculate()
        self.assertIsNone(result["probabilities"])
        self.assertIsNone(result["expected_return"])

    def test_requires_bull_base_bear_order(self):
        with self.assertRaisesRegex(ValueError, "ordered bull"):
            self.calculate(
                bull_case={"price": 110, "assumptions": "Bull"},
                base_case={"price": 120, "assumptions": "Base"},
            )

    def test_invalidation_must_be_below_entry(self):
        with self.assertRaisesRegex(ValueError, "below reference_entry_price"):
            self.calculate(invalidation_price=100)

    def test_rejects_zero_negative_and_non_finite_prices(self):
        for value in (0, -1, "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.calculate(reference_entry_price=value)

    def test_rejects_missing_assumption_rationale(self):
        with self.assertRaisesRegex(ValueError, "assumptions"):
            self.calculate(bull_case={"price": 150, "assumptions": ""})

    def test_rejects_naive_as_of_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.calculate(as_of_utc="2026-11-17T16:00:00")

    def test_rejects_invalid_quote_currency(self):
        with self.assertRaisesRegex(ValueError, "quote_currency"):
            self.calculate(quote_currency="")

    def test_supports_high_precision_decimal_inputs(self):
        result = self.calculate(
            reference_entry_price="0.12345678",
            invalidation_price="0.10000000",
            bull_case={"price": "0.20000000", "assumptions": "Adoption scenario."},
            base_case={"price": "0.15000000", "assumptions": "Base scenario."},
            bear_case={"price": "0.08000000", "assumptions": "Downside scenario."},
        )
        self.assertEqual(result["hypothetical_inputs"]["reference_entry_price"], "0.12345678")
        self.assertIsInstance(result["bull_reward_to_risk"], str)


if __name__ == "__main__":
    unittest.main()
