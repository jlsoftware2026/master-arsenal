"""Cash-only hypothetical position sizing from explicit risk and allocation inputs.

This module does not select an entry, stop, capital amount, or risk budget and
never places orders. All outputs are planning estimates, not execution guarantees.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


def _decimal(value: Any, field: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be a finite {'non-negative' if allow_zero else 'positive'} number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be a finite {'non-negative' if allow_zero else 'positive'} number") from exc
    if not result.is_finite() or (result < 0 if allow_zero else result <= 0):
        raise ValueError(f"{field} must be a finite {'non-negative' if allow_zero else 'positive'} number")
    return result


def _fmt(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


def calculate_cash_position_size(
    *,
    available_capital: Any,
    quote_currency: str,
    entry_price: Any,
    invalidation_price: Any,
    risk_budget_pct: Any,
    max_allocation_pct: Any,
    entry_fee_bps: Any = 0,
    exit_fee_bps: Any = 0,
    entry_slippage_bps: Any = 0,
    exit_slippage_bps: Any = 0,
) -> dict[str, Any]:
    """Calculate a cash-only maximum hypothetical size under risk and allocation caps."""
    if not isinstance(quote_currency, str) or not quote_currency.strip():
        raise ValueError("quote_currency is required")
    capital = _decimal(available_capital, "available_capital")
    entry = _decimal(entry_price, "entry_price")
    invalidation = _decimal(invalidation_price, "invalidation_price")
    if invalidation >= entry:
        raise ValueError("invalidation_price must be below entry_price for a long position")
    risk_pct = _decimal(risk_budget_pct, "risk_budget_pct")
    allocation_pct = _decimal(max_allocation_pct, "max_allocation_pct")
    if risk_pct > 100:
        raise ValueError("risk_budget_pct must not exceed 100")
    if allocation_pct > 100:
        raise ValueError("max_allocation_pct must not exceed 100")

    entry_fee = _decimal(entry_fee_bps, "entry_fee_bps", allow_zero=True)
    exit_fee = _decimal(exit_fee_bps, "exit_fee_bps", allow_zero=True)
    entry_slippage = _decimal(entry_slippage_bps, "entry_slippage_bps", allow_zero=True)
    exit_slippage = _decimal(exit_slippage_bps, "exit_slippage_bps", allow_zero=True)
    bps = Decimal("10000")
    entry_cost_rate = (entry_fee + entry_slippage) / bps
    exit_cost_rate = (exit_fee + exit_slippage) / bps

    risk_per_unit = (
        entry - invalidation
        + entry * entry_cost_rate
        + invalidation * exit_cost_rate
    )
    if risk_per_unit <= 0:
        raise ValueError("calculated risk_per_unit must be positive")

    risk_budget = capital * risk_pct / Decimal("100")
    allocation_capital = capital * allocation_pct / Decimal("100")
    units_by_risk = risk_budget / risk_per_unit
    units_by_allocation = allocation_capital / entry
    units = min(units_by_risk, units_by_allocation)
    notional = units * entry
    planned_risk = units * risk_per_unit
    allocation_used_pct = notional / capital * Decimal("100")
    risk_used_pct = planned_risk / capital * Decimal("100")

    if units_by_risk < units_by_allocation:
        constraint = "risk_budget"
    elif units_by_allocation < units_by_risk:
        constraint = "capital_allocation"
    else:
        constraint = "both"

    return {
        "schema": "ma.cash-position-size/v1",
        "analysis_type": "hypothetical_cash_only",
        "quote_currency": quote_currency.strip().upper(),
        "available_capital": str(capital),
        "entry_price": str(entry),
        "invalidation_price": str(invalidation),
        "risk_budget_pct": str(risk_pct),
        "risk_budget_amount": _fmt(risk_budget),
        "max_allocation_pct": str(allocation_pct),
        "max_allocation_amount": _fmt(allocation_capital),
        "entry_fee_bps": str(entry_fee),
        "exit_fee_bps": str(exit_fee),
        "entry_slippage_bps": str(entry_slippage),
        "exit_slippage_bps": str(exit_slippage),
        "estimated_units": _fmt(units),
        "estimated_notional": _fmt(notional),
        "planned_loss_at_invalidation": _fmt(planned_risk),
        "capital_allocation_used_pct": _fmt(allocation_used_pct),
        "capital_risk_used_pct": _fmt(risk_used_pct),
        "limiting_constraint": constraint,
        "limitations": [
            "All inputs are explicit user-supplied planning assumptions; no entry, stop, capital, or risk budget is selected by the engine.",
            "Cash-only sizing; no leverage, borrowing, margin, derivatives, or short exposure.",
            "Excludes taxes, spread variation, market impact, funding, custody costs, lot-size rules, and gaps beyond the invalidation price.",
            "A stop/invalidation level is not a guaranteed execution price; realized loss can exceed this estimate.",
            "This is a calculator, not a recommendation or order instruction. No order is submitted.",
        ],
    }
