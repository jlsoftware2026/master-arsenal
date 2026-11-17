"""Tests for hypothetical cash-only position sizing."""
import unittest
from decimal import Decimal

from report_engine.position_sizing import calculate_cash_position_size

BASE = {
    "available_capital": "10000",
    "quote_currency": "USD",
    "entry_price": "100",
    "invalidation_price": "90",
    "risk_budget_pct": "1",
    "max_allocation_pct": "50",
}


class PositionSizingTests(unittest.TestCase):
    def calculate(self, **changes):
        args = dict(BASE)
        args.update(changes)
        return calculate_cash_position_size(**args)

    def test_risk_budget_limits_position(self):
        result = self.calculate()
        self.assertEqual(result["risk_budget_amount"], "100.00000000")
        self.assertEqual(result["estimated_units"], "10.00000000")
        self.assertEqual(result["estimated_notional"], "1000.00000000")
        self.assertEqual(result["planned_loss_at_invalidation"], "100.00000000")
        self.assertEqual(result["limiting_constraint"], "risk_budget")

    def test_allocation_cap_limits_position(self):
        result = self.calculate(risk_budget_pct=10, max_allocation_pct=5)
        self.assertEqual(result["estimated_notional"], "500.00000000")
        self.assertEqual(result["planned_loss_at_invalidation"], "50.00000000")
        self.assertEqual(result["limiting_constraint"], "capital_allocation")

    def test_fees_and_slippage_increase_risk_per_unit(self):
        no_cost = self.calculate()
        with_cost = self.calculate(entry_fee_bps=10, exit_fee_bps=10,
                                   entry_slippage_bps=5, exit_slippage_bps=5)
        self.assertLess(Decimal(with_cost["estimated_units"]), Decimal(no_cost["estimated_units"]))

    def test_never_exceeds_available_capital_allocation(self):
        result = self.calculate(risk_budget_pct=100, max_allocation_pct=25)
        self.assertLessEqual(Decimal(result["estimated_notional"]), Decimal("2500"))

    def test_requires_invalidation_below_entry(self):
        with self.assertRaisesRegex(ValueError, "below entry_price"):
            self.calculate(invalidation_price=100)

    def test_rejects_invalid_risk_and_allocation_percentages(self):
        for field, value in (("risk_budget_pct", 0), ("risk_budget_pct", 101),
                             ("max_allocation_pct", 0), ("max_allocation_pct", 101)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.calculate(**{field: value})

    def test_rejects_negative_fees_and_slippage(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.calculate(entry_fee_bps=-1)

    def test_rejects_non_finite_inputs(self):
        with self.assertRaisesRegex(ValueError, "finite positive"):
            self.calculate(available_capital="NaN")

    def test_output_is_explicitly_hypothetical_and_cash_only(self):
        result = self.calculate()
        self.assertEqual(result["analysis_type"], "hypothetical_cash_only")
        self.assertTrue(any("No order is submitted" in item for item in result["limitations"]))


if __name__ == "__main__":
    unittest.main()
