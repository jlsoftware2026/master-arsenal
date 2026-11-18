"""Transparent financial ratio calculations from same-period SEC/issuer facts."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

DOLLAR_METRICS = {
    "revenue", "gross_profit", "operating_income", "net_income",
    "operating_cash_flow", "capital_expenditures", "current_assets",
    "current_liabilities", "stockholders_equity", "total_assets",
    "cash_and_equivalents",
}


def _number(fact: Mapping[str, Any]) -> Decimal | None:
    try:
        value = Decimal(str(fact.get("value")))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return value if value.is_finite() else None


def _fmt(value: Decimal, places: str = "0.0001") -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def calculate_financial_ratios(
    facts: list[Mapping[str, Any]],
    *,
    instrument_key: str,
) -> dict[str, Any]:
    """Calculate only ratios supported by unambiguous same-period source facts."""
    if not isinstance(instrument_key, str) or not instrument_key.strip():
        raise ValueError("instrument_key is required")
    if not isinstance(facts, list):
        raise ValueError("facts must be a list")

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for fact in facts:
        if not isinstance(fact, Mapping):
            raise ValueError("each fact must be a mapping")
        if fact.get("instrument_key") != instrument_key:
            raise ValueError("all financial facts must match the requested instrument_key")
        dimension = fact.get("dimension")
        if isinstance(dimension, str):
            grouped.setdefault(dimension, []).append(fact)

    selected: dict[str, Mapping[str, Any]] = {}
    ambiguous: set[str] = set()
    for dimension, candidates in grouped.items():
        dated = [item for item in candidates if isinstance(item.get("as_of_utc"), str)]
        if not dated:
            continue
        latest = max(item["as_of_utc"] for item in dated)
        same_period = [item for item in dated if item["as_of_utc"] == latest]
        if len(same_period) != 1:
            ambiguous.add(dimension)
        else:
            selected[dimension] = same_period[0]

    metrics: dict[str, dict[str, Any]] = {}
    missing: dict[str, str] = {}

    def pair(name: str, numerator_dimension: str, denominator_dimension: str,
             *, multiplier: Decimal = Decimal("1"), unit: str = "ratio",
             formula: str) -> None:
        numerator_fact = selected.get(numerator_dimension)
        denominator_fact = selected.get(denominator_dimension)
        if numerator_dimension in ambiguous or denominator_dimension in ambiguous:
            missing[name] = "Ambiguous multiple observations for the same latest period."
            return
        if numerator_fact is None or denominator_fact is None:
            missing[name] = f"Requires {numerator_dimension} and {denominator_dimension} for the same period."
            return
        if numerator_fact.get("as_of_utc") != denominator_fact.get("as_of_utc"):
            missing[name] = "Required facts do not share the same reporting period end."
            return
        if numerator_fact.get("unit") != denominator_fact.get("unit"):
            missing[name] = "Required facts use different units/currencies."
            return
        numerator = _number(numerator_fact)
        denominator = _number(denominator_fact)
        if numerator is None or denominator is None:
            missing[name] = "Required source values are not finite numeric values."
            return
        if denominator == 0:
            missing[name] = "Denominator is zero; ratio not calculated."
            return
        value = numerator / denominator * multiplier
        metrics[name] = {
            "value": _fmt(value),
            "unit": unit,
            "formula": formula,
            "as_of_utc": numerator_fact["as_of_utc"],
            "source_fact_ids": [numerator_fact.get("fact_id"), denominator_fact.get("fact_id")],
            "status": "calculated",
        }

    percent = Decimal("100")
    pair("gross_margin_pct", "gross_profit", "revenue", multiplier=percent,
         unit="percent", formula="gross_profit / revenue × 100")
    pair("operating_margin_pct", "operating_income", "revenue", multiplier=percent,
         unit="percent", formula="operating_income / revenue × 100")
    pair("net_margin_pct", "net_income", "revenue", multiplier=percent,
         unit="percent", formula="net_income / revenue × 100")
    pair("operating_cash_flow_margin_pct", "operating_cash_flow", "revenue",
         multiplier=percent, unit="percent",
         formula="operating_cash_flow / revenue × 100")
    pair("current_ratio", "current_assets", "current_liabilities",
         unit="x", formula="current_assets / current_liabilities")
    pair("cash_to_current_liabilities", "cash_and_equivalents", "current_liabilities",
         unit="x", formula="cash_and_equivalents / current_liabilities")
    pair("period_end_roa_pct", "net_income", "total_assets", multiplier=percent,
         unit="percent", formula="net_income / period_end_total_assets × 100")
    pair("period_end_roe_pct", "net_income", "stockholders_equity", multiplier=percent,
         unit="percent", formula="net_income / period_end_stockholders_equity × 100")

    cfo = selected.get("operating_cash_flow")
    capex = selected.get("capital_expenditures")
    revenue = selected.get("revenue")
    if "operating_cash_flow" in ambiguous or "capital_expenditures" in ambiguous:
        missing["free_cash_flow"] = "Ambiguous multiple observations for the same latest period."
    elif cfo is None or capex is None:
        missing["free_cash_flow"] = "Requires operating_cash_flow and capital_expenditures for the same period."
    elif cfo.get("as_of_utc") != capex.get("as_of_utc") or cfo.get("unit") != capex.get("unit"):
        missing["free_cash_flow"] = "Cash flow and capital expenditures do not share period end and currency."
    else:
        cfo_value, capex_value = _number(cfo), _number(capex)
        if cfo_value is None or capex_value is None:
            missing["free_cash_flow"] = "Required source values are not finite numeric values."
        else:
            fcf = cfo_value - abs(capex_value)
            metrics["free_cash_flow"] = {
                "value": _fmt(fcf, "0.01"),
                "unit": cfo.get("unit", "currency"),
                "formula": "operating_cash_flow - absolute(capital_expenditures)",
                "as_of_utc": cfo["as_of_utc"],
                "source_fact_ids": [cfo.get("fact_id"), capex.get("fact_id")],
                "status": "calculated",
            }
            if revenue is None or revenue.get("as_of_utc") != cfo.get("as_of_utc") or revenue.get("unit") != cfo.get("unit"):
                missing["free_cash_flow_margin_pct"] = "Requires revenue with the same reporting period end and currency."
            else:
                revenue_value = _number(revenue)
                if revenue_value is None or revenue_value == 0:
                    missing["free_cash_flow_margin_pct"] = "Revenue is unavailable or zero."
                else:
                    metrics["free_cash_flow_margin_pct"] = {
                        "value": _fmt(fcf / revenue_value * percent),
                        "unit": "percent",
                        "formula": "free_cash_flow / revenue × 100",
                        "as_of_utc": cfo["as_of_utc"],
                        "source_fact_ids": [cfo.get("fact_id"), capex.get("fact_id"), revenue.get("fact_id")],
                        "status": "calculated",
                    }

    return {
        "schema": "ma.financial-ratios/v1",
        "instrument_key": instrument_key,
        "metrics": metrics,
        "missing_metrics": missing,
        "status": "insufficient_evidence" if not metrics else (
            "complete" if not missing else "partial"
        ),
        "limitations": [
            "Ratios are calculated only from unambiguous source facts with matching reporting-period end and currency.",
            "Period-end ROA/ROE use period-end balances, not average assets/equity; they are proxies, not textbook average-balance ratios.",
            "Free cash flow is operating cash flow less absolute reported capital expenditures; classification and sign conventions require filing review.",
            "No growth rates, valuation multiples, total-debt aggregation, peer comparisons, or investment score are calculated.",
            "Missing, mismatched, ambiguous, or zero-denominator inputs are not filled or guessed.",
        ],
    }


def calculate_valuation_multiples(
    facts: list[Mapping[str, Any]],
    *,
    instrument_key: str,
    market_cap: Mapping[str, Any],
    earnings_period_basis: str,
) -> dict[str, Any]:
    """Calculate P/E, P/S and P/B only from explicit, currency-matched inputs.

    earnings_period_basis must be explicitly supplied as annual or quarterly.
    Quarterly inputs are rejected rather than annualized or silently mixed.
    Market capitalization must carry source provenance and an observation time.
    """
    if not isinstance(instrument_key, str) or not instrument_key.strip():
        raise ValueError("instrument_key is required")
    if earnings_period_basis not in {"annual", "quarterly"}:
        raise ValueError("earnings_period_basis must be annual or quarterly")
    if not isinstance(facts, list) or not isinstance(market_cap, Mapping):
        raise ValueError("facts must be a list and market_cap must be a mapping")
    def parse_number(value: Any) -> Decimal | None:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
        return number if number.is_finite() else None

    cap = parse_number(market_cap.get("value"))
    currency = market_cap.get("unit")
    cap_as_of = market_cap.get("as_of_utc")
    cap_source_id = market_cap.get("source_id")
    cap_source_url = market_cap.get("source_url")
    if cap is None or cap <= 0:
        raise ValueError("market_cap.value must be a finite positive number")
    if not isinstance(currency, str) or not currency.strip():
        raise ValueError("market_cap.unit currency is required")
    if not isinstance(cap_as_of, str) or not cap_as_of.strip():
        raise ValueError("market_cap.as_of_utc is required")
    if not isinstance(cap_source_id, str) or not cap_source_id.strip():
        raise ValueError("market_cap.source_id is required")
    if not isinstance(cap_source_url, str) or not cap_source_url.startswith("https://"):
        raise ValueError("market_cap.source_url must be HTTPS")

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for fact in facts:
        if not isinstance(fact, Mapping):
            raise ValueError("each fact must be a mapping")
        if fact.get("instrument_key") != instrument_key:
            raise ValueError("all financial facts must match the requested instrument_key")
        dimension = fact.get("dimension")
        if isinstance(dimension, str):
            grouped.setdefault(dimension, []).append(fact)

    metrics: dict[str, dict[str, Any]] = {}
    missing: dict[str, str] = {}
    definitions = {
        "price_to_earnings": ("net_income", "annual earnings", True),
        "price_to_sales": ("revenue", "annual revenue", True),
        "price_to_book": ("stockholders_equity", "latest reported book equity", False),
    }
    for name, (dimension, label, duration) in definitions.items():
        if duration and earnings_period_basis != "annual":
            missing[name] = (
                "Quarterly earnings are not annualized; annual facts are required."
                if dimension == "net_income"
                else "Quarterly revenue is not annualized; annual facts are required."
            )
            continue
        candidates = grouped.get(dimension, [])
        dated = [item for item in candidates if isinstance(item.get("as_of_utc"), str)]
        if not dated:
            missing[name] = f"Missing {label} fact."
            continue
        latest = max(item["as_of_utc"] for item in dated)
        selected = [item for item in dated if item["as_of_utc"] == latest]
        if len(selected) != 1:
            missing[name] = "Ambiguous multiple observations for the latest reporting period."
            continue
        fact = selected[0]
        if not isinstance(fact.get("fact_id"), str) or not fact.get("fact_id").strip():
            missing[name] = "Financial fact is missing a stable source fact ID."
            continue
        if not isinstance(fact.get("source_url"), str) or not fact.get("source_url").startswith("https://"):
            missing[name] = "Financial fact is missing an HTTPS source URL."
            continue
        if fact.get("evidence_quality") not in {"verified_source", "estimated"}:
            missing[name] = "Financial fact evidence quality is missing or unsupported."
            continue
        if fact.get("unit") != currency:
            missing[name] = "Market capitalization and financial fact use different currencies."
            continue
        value = parse_number(fact.get("value"))
        if value is None:
            missing[name] = "Financial fact is not a finite numeric value."
            continue
        if value <= 0:
            missing[name] = "Metric is zero or negative; conventional valuation multiple is not meaningful."
            continue
        ratio = cap / value
        metrics[name] = {
            "value": _fmt(ratio),
            "unit": "x",
            "formula": f"market_capitalization / {dimension}",
            "market_cap_as_of_utc": cap_as_of,
            "financial_period_end_utc": fact["as_of_utc"],
            "market_cap_source_id": cap_source_id,
            "financial_source_fact_id": fact.get("fact_id"),
            "market_cap_source_url": cap_source_url,
            "financial_source_url": fact.get("source_url"),
            "status": "calculated",
            "interpretation_limit": (
                "Compares current market capitalization with the latest reported financial figure; "
                "the market-cap date and reporting period may differ."
            ),
        }

    return {
        "schema": "ma.valuation-multiples/v1",
        "instrument_key": instrument_key,
        "market_cap": {
            "value": str(cap), "unit": currency, "as_of_utc": cap_as_of,
            "source_id": cap_source_id, "source_url": cap_source_url,
        },
        "earnings_period_basis": earnings_period_basis,
        "metrics": metrics,
        "missing_metrics": missing,
        "status": "insufficient_evidence" if not metrics else ("complete" if not missing else "partial"),
        "limitations": [
            "P/E and P/S use explicitly declared annual net income and revenue; quarterly data is never annualized.",
            "P/B uses the latest reported stockholders' equity, not tangible book value.",
            "Market capitalization must be independently sourced; this function does not infer shares outstanding or price.",
            "Market-cap observation date and financial reporting period may differ.",
            "Negative earnings and negative/zero book equity do not produce conventional valuation multiples.",
            "Multiples are not investment recommendations and require peer, growth, capital-structure, and sector context.",
        ],
    }
