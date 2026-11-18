"""Deterministic, assumption-transparent long-horizon price scenario calculations.

No probabilities, expected returns, target prices, or trading instructions are
invented. All price inputs are caller-supplied hypothetical assumptions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be a finite positive number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be a finite positive number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return parsed


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("as_of_utc must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("as_of_utc must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("as_of_utc must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def _fmt(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _return_pct(entry: Decimal, scenario: Decimal) -> Decimal:
    return (scenario - entry) / entry * Decimal("100")


def calculate_long_scenarios(
    *,
    instrument_key: str,
    quote_currency: str,
    reference_entry_price: Any,
    invalidation_price: Any,
    bull_case: Mapping[str, Any],
    base_case: Mapping[str, Any],
    bear_case: Mapping[str, Any],
    invalidation_basis: str,
    horizon: str,
    as_of_utc: str,
) -> dict[str, Any]:
    """Calculate scenario returns and reward/risk from explicit long-only assumptions."""
    key = _text(instrument_key, "instrument_key")
    currency = _text(quote_currency, "quote_currency").upper()
    period = _text(horizon, "horizon")
    generated_at = _timestamp(as_of_utc)
    entry = _decimal(reference_entry_price, "reference_entry_price")
    invalidation = _decimal(invalidation_price, "invalidation_price")
    if invalidation >= entry:
        raise ValueError("invalidation_price must be below reference_entry_price for a long scenario")
    risk_per_unit = entry - invalidation
    risk_pct = risk_per_unit / entry * Decimal("100")
    invalidation_note = _text(invalidation_basis, "invalidation_basis")

    cases = {"bull": bull_case, "base": base_case, "bear": bear_case}
    prices: dict[str, Decimal] = {}
    normalized_cases: dict[str, dict[str, str]] = {}
    for name, case in cases.items():
        if not isinstance(case, Mapping):
            raise ValueError(f"{name}_case must be a mapping")
        price = _decimal(case.get("price"), f"{name}_case.price")
        rationale = _text(case.get("assumptions"), f"{name}_case.assumptions")
        prices[name] = price
        normalized_cases[name] = {
            "price": str(price),
            "assumptions": rationale,
            "return_pct": _fmt(_return_pct(entry, price)),
        }

    if not (prices["bull"] >= prices["base"] >= prices["bear"]):
        raise ValueError("scenario prices must be ordered bull >= base >= bear")

    def reward_to_risk(target: Decimal) -> str:
        return _fmt((target - entry) / risk_per_unit)

    return {
        "schema": "ma.price-scenarios/v1",
        "instrument_key": key,
        "quote_currency": currency,
        "analysis_type": "hypothetical_long_only",
        "as_of_utc": generated_at.isoformat().replace("+00:00", "Z"),
        "horizon": period,
        "hypothetical_inputs": {
            "reference_entry_price": str(entry),
            "entry_price_basis": "Caller-supplied hypothetical reference price; not an order or executed position.",
            "invalidation_price": str(invalidation),
            "invalidation_basis": invalidation_note,
        },
        "scenarios": normalized_cases,
        "downside_to_invalidation_pct": _fmt(risk_pct),
        "bull_reward_to_risk": reward_to_risk(prices["bull"]),
        "base_reward_to_risk": reward_to_risk(prices["base"]),
        "probabilities": None,
        "expected_return": None,
        "interpretation_limits": [
            "All prices and rationales are caller-supplied assumptions, not model-generated forecasts.",
            "No scenario probabilities or probability-weighted expected return are calculated.",
            "Reward-to-risk is a simple price-distance ratio and excludes fees, slippage, taxes, liquidity, gap risk, and execution constraints.",
            "The invalidation price is a hypothetical thesis-risk reference, not a guaranteed stop execution price.",
            "This is a scenario calculator, not a recommendation or order instruction.",
        ],
    }
