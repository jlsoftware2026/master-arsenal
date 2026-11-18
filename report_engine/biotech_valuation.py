"""Stage-aware biotech valuation context and cash-runway calculations.

This module deliberately avoids risk-adjusted NPV and clinical success probabilities.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from typing import Any, Mapping

STAGES = {"preclinical", "clinical", "commercial"}

def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not number.is_finite():
        raise ValueError(f"{field} must be finite")
    return number

def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed


def _source_observation(value: Mapping[str, Any], field: str, instrument_key: str) -> tuple[Decimal, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a source-attributed mapping")
    amount = _decimal(value.get("value"), f"{field}.value")
    currency = value.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        raise ValueError(f"{field}.currency is required")
    _timestamp(value.get("as_of_utc"), f"{field}.as_of_utc")
    if value.get("instrument_key") != instrument_key:
        raise ValueError(f"{field}.instrument_key must match the requested instrument")
    if not isinstance(value.get("source_id"), str) or not value["source_id"].strip():
        raise ValueError(f"{field}.source_id is required")
    if not isinstance(value.get("source_url"), str) or not value["source_url"].startswith("https://"):
        raise ValueError(f"{field}.source_url must be HTTPS")
    if value.get("evidence_quality") not in {"verified_source", "estimated"}:
        raise ValueError(f"{field}.evidence_quality must be verified_source or estimated")
    return amount, currency.strip().upper()

def _fmt(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def assess_biotech_valuation(
    *, instrument_key: str, development_stage: str, analysis_cutoff_utc: str,
    cash: Mapping[str, Any] | None = None,
    quarterly_net_cash_burn: Mapping[str, Any] | None = None,
    market_cap: Mapping[str, Any] | None = None,
    annual_revenue: Mapping[str, Any] | None = None,
    clinical_catalysts: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Calculate sourced runway and commercial price-to-sales; never infer pipeline value."""
    if not isinstance(instrument_key, str) or not instrument_key.strip():
        raise ValueError("instrument_key is required")
    if development_stage not in STAGES:
        raise ValueError("development_stage must be preclinical, clinical, or commercial")
    cutoff = _timestamp(analysis_cutoff_utc, "analysis_cutoff_utc")

    metrics: dict[str, dict[str, Any]] = {}
    missing: dict[str, str] = {}
    warnings = [
        "Screening framework only; not an intrinsic valuation or investment recommendation.",
        "Clinical phase, recruitment status, and registry endpoints do not establish efficacy, safety, approval, or commercial value.",
        "No risk-adjusted NPV, probability of technical/regulatory success, or pipeline asset value is inferred.",
    ]
    cash_pair = _source_observation(cash, "cash", instrument_key) if cash is not None else None
    burn_pair = _source_observation(quarterly_net_cash_burn, "quarterly_net_cash_burn", instrument_key) if quarterly_net_cash_burn is not None else None
    if cash_pair and burn_pair:
        cash_value, cash_currency = cash_pair
        burn_value, burn_currency = burn_pair
        if _timestamp(cash["as_of_utc"], "cash.as_of_utc") > cutoff or _timestamp(quarterly_net_cash_burn["as_of_utc"], "quarterly_net_cash_burn.as_of_utc") > cutoff:
            missing["cash_runway_months"] = "Cash or burn observation is after the analysis cutoff."
        elif cash_currency != burn_currency:
            missing["cash_runway_months"] = "Cash and quarterly net cash burn use different currencies."
        elif _timestamp(cash["as_of_utc"], "cash.as_of_utc") != _timestamp(quarterly_net_cash_burn["as_of_utc"], "quarterly_net_cash_burn.as_of_utc"):
            missing["cash_runway_months"] = "Cash balance and quarterly net cash burn must share the same period-end observation date."
        elif cash_value < 0 or burn_value <= 0:
            missing["cash_runway_months"] = "Cash must be non-negative and quarterly net cash burn must be positive."
        else:
            metrics["cash_runway_months"] = {
                "value": _fmt(cash_value / burn_value * Decimal("3")),
                "unit": "months",
                "formula": "cash balance / quarterly net cash burn * 3",
                "cash_source_id": cash["source_id"],
                "burn_source_id": quarterly_net_cash_burn["source_id"],
                "cash_as_of_utc": cash["as_of_utc"],
                "burn_period_end_utc": quarterly_net_cash_burn["as_of_utc"],
                "interpretation": "Mechanical runway estimate assuming the supplied quarterly net burn remains constant; not a forecast.",
            }
    else:
        missing["cash_runway_months"] = "Requires both source-attributed cash and positive quarterly net cash burn."

    if development_stage == "commercial":
        if market_cap is None or annual_revenue is None:
            missing["price_to_sales"] = "Commercial-stage price-to-sales requires sourced market capitalization and annual revenue."
        else:
            cap, cap_currency = _source_observation(market_cap, "market_cap", instrument_key)
            revenue, revenue_currency = _source_observation(annual_revenue, "annual_revenue", instrument_key)
            if _timestamp(market_cap["as_of_utc"], "market_cap.as_of_utc") > cutoff or _timestamp(annual_revenue["as_of_utc"], "annual_revenue.as_of_utc") > cutoff:
                missing["price_to_sales"] = "Market-cap or revenue observation is after the analysis cutoff."
            elif cap <= 0 or revenue <= 0:
                missing["price_to_sales"] = "Market capitalization and annual revenue must both be positive."
            elif cap_currency != revenue_currency:
                missing["price_to_sales"] = "Market capitalization and annual revenue use different currencies."
            else:
                metrics["price_to_sales"] = {
                    "value": _fmt(cap / revenue), "unit": "multiple",
                    "formula": "market capitalization / annual revenue",
                    "market_cap_source_id": market_cap["source_id"],
                    "revenue_source_id": annual_revenue["source_id"],
                    "market_cap_as_of_utc": market_cap["as_of_utc"],
                    "revenue_as_of_utc": annual_revenue["as_of_utc"],
                    "interpretation": "Equity value-to-sales screening multiple; ignores debt, cash, growth, margins, and revenue quality.",
                }
    else:
        missing["price_to_sales"] = "Not applied to a pre-revenue or clinical-stage company; pipeline assets are not revenue."

    catalysts = []
    if clinical_catalysts is not None:
        if not isinstance(clinical_catalysts, list):
            raise ValueError("clinical_catalysts must be a list")
        for index, catalyst in enumerate(clinical_catalysts):
            if not isinstance(catalyst, Mapping):
                raise ValueError(f"clinical_catalysts[{index}] must be a mapping")
            nct, url = catalyst.get("nct_id"), catalyst.get("source_url")
            if not isinstance(nct, str) or len(nct) != 11 or not nct.startswith("NCT") or not nct[3:].isdigit() or not isinstance(url, str) or url != f"https://clinicaltrials.gov/study/{nct}" or not isinstance(catalyst.get("attribution_basis"), str) or not catalyst["attribution_basis"].strip():
                raise ValueError(f"clinical_catalysts[{index}] requires NCT ID and ClinicalTrials.gov source URL")
            catalysts.append({
                "nct_id": nct, "phase": catalyst.get("phase"),
                "status": catalyst.get("status"),
                "primary_completion_date": catalyst.get("primary_completion_date"),
                "source_url": url, "attribution_basis": catalyst.get("attribution_basis"),
                "warning": "Registry milestone only; not an efficacy, approval, or probability assessment.",
            })
    if development_stage in {"preclinical", "clinical"}:
        warnings.append("Conventional earnings and sales multiples may be unavailable or misleading for pre-revenue development-stage issuers.")
    if "cash_runway_months" in metrics:
        warnings.append("Runway excludes future financing, milestone payments, debt maturities, working-capital changes, and changes in trial/commercial spending.")
    return {
        "schema": "ma.biotech-valuation/v1", "instrument_key": instrument_key.strip(),
        "development_stage": development_stage, "analysis_cutoff_utc": analysis_cutoff_utc,
        "metrics": metrics, "missing_metrics": missing, "clinical_catalysts": catalysts,
        "status": "complete" if metrics and not missing else ("partial" if metrics else "insufficient_evidence"),
        "warnings": warnings,
    }
