"""Source-attributed research facts and freshness assessment.

This module validates provenance and evidence metadata. It does not fetch sources,
independently establish factual truth, or generate investment recommendations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import urlparse

DIMENSIONS = {
    "business_model", "revenue", "growth", "margins", "cash_flow", "debt",
    "liquidity", "valuation", "capital_allocation", "competition",
    "clinical_development", "regulatory", "patents_ip", "reimbursement",
    "product_adoption", "customer_concentration", "technology_differentiation",
    "protocol_utility", "network_adoption", "developer_activity",
    "tokenomics", "supply_unlocks", "holder_concentration", "governance",
    "security", "protocol_usage", "protocol_revenue", "market_price",
    "market_volume", "market_structure", "volatility", "derivatives_positioning",
    "catalyst", "risk", "thesis_invalidation",
}
SOURCE_KINDS = {
    "regulatory_filing", "issuer_disclosure", "audited_financials",
    "clinical_registry", "regulatory_agency", "protocol_documentation",
    "exchange_data", "market_data_provider", "on_chain_data",
    "reputable_secondary", "user_assumption", "analyst_assumption",
}
EVIDENCE_QUALITIES = {"verified_source", "estimated", "disputed", "unverified"}
FRESHNESS_STATES = {"fresh", "stale", "future_dated", "not_assessed"}


def _text(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required and must be non-empty text")
    return value.strip()


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def _https_url(value: Any, field: str) -> str:
    url = _text({"value": value}, "value")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an HTTPS URL")
    return url


def normalize_research_fact(fact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a single research observation, preserving source/assumption labels."""
    if not isinstance(fact, Mapping):
        raise ValueError("fact must be a mapping")
    dimension = _text(fact, "dimension").lower()
    if dimension not in DIMENSIONS:
        raise ValueError(f"dimension must be one of the supported research dimensions")
    source_kind = _text(fact, "source_kind").lower()
    if source_kind not in SOURCE_KINDS:
        raise ValueError("source_kind is not supported")
    quality = _text(fact, "evidence_quality").lower()
    if quality not in EVIDENCE_QUALITIES:
        raise ValueError("evidence_quality is not supported")

    value = fact.get("value")
    if value is None or isinstance(value, (dict, list)):
        raise ValueError("value must be a non-null scalar")
    if isinstance(value, float):
        import math
        if not math.isfinite(value):
            raise ValueError("numeric value must be finite")

    record: dict[str, Any] = {
        "fact_id": _text(fact, "fact_id"),
        "instrument_key": _text(fact, "instrument_key"),
        "dimension": dimension,
        "label": _text(fact, "label"),
        "value": value,
        "unit": _text(fact, "unit"),
        "source_kind": source_kind,
        "evidence_quality": quality,
        "as_of_utc": _timestamp(fact.get("as_of_utc"), "as_of_utc").isoformat().replace("+00:00", "Z"),
        "retrieved_at_utc": _timestamp(fact.get("retrieved_at_utc"), "retrieved_at_utc").isoformat().replace("+00:00", "Z"),
    }
    if fact.get("published_at_utc") is not None:
        record["published_at_utc"] = _timestamp(
            fact.get("published_at_utc"), "published_at_utc"
        ).isoformat().replace("+00:00", "Z")

    is_assumption = source_kind in {"user_assumption", "analyst_assumption"}
    if is_assumption:
        record["assumption_note"] = _text(fact, "assumption_note")
        if fact.get("source_url") is not None:
            raise ValueError("assumptions must not be represented as externally sourced facts")
    else:
        record["source_name"] = _text(fact, "source_name")
        record["source_url"] = _https_url(fact.get("source_url"), "source_url")
        if quality == "verified_source" and not fact.get("source_reference"):
            raise ValueError("verified_source evidence requires a source_reference")
        if fact.get("source_reference") is not None:
            record["source_reference"] = _text(fact, "source_reference")

    if fact.get("notes") is not None:
        record["notes"] = _text(fact, "notes")
    return record


def assess_freshness(
    fact: Mapping[str, Any],
    *,
    now: datetime,
    max_age: timedelta | None,
) -> dict[str, Any]:
    """Assess age against an explicit policy; absence of policy is not a freshness claim."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    observed = _timestamp(fact.get("as_of_utc"), "as_of_utc")
    current = now.astimezone(timezone.utc)
    age = current - observed
    if age < timedelta(0):
        return {"status": "future_dated", "age_seconds": int(age.total_seconds())}
    if max_age is None:
        return {"status": "not_assessed", "age_seconds": int(age.total_seconds())}
    if max_age < timedelta(0):
        raise ValueError("max_age must not be negative")
    return {
        "status": "stale" if age > max_age else "fresh",
        "age_seconds": int(age.total_seconds()),
        "max_age_seconds": int(max_age.total_seconds()),
    }


def build_research_packet(
    instrument_key: str,
    facts: list[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    freshness_limits_hours: Mapping[str, int | float] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, source-attributed packet with explicit coverage gaps."""
    if not isinstance(instrument_key, str) or not instrument_key.strip():
        raise ValueError("instrument_key must be non-empty text")
    if not isinstance(facts, list):
        raise ValueError("facts must be a list")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    limits = freshness_limits_hours or {}
    if not isinstance(limits, Mapping):
        raise ValueError("freshness_limits_hours must be a mapping")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in facts:
        fact = normalize_research_fact(raw)
        if fact["instrument_key"] != instrument_key:
            raise ValueError("all facts must belong to the requested instrument_key")
        if fact["fact_id"] in seen:
            raise ValueError("fact_id values must be unique within a research packet")
        seen.add(fact["fact_id"])
        limit = limits.get(fact["dimension"])
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit < 0:
                raise ValueError(f"freshness limit for {fact['dimension']} must be a non-negative number")
            max_age = timedelta(hours=float(limit))
        else:
            max_age = None
        freshness = assess_freshness(fact, now=current, max_age=max_age)
        fact["freshness"] = freshness
        normalized.append(fact)

    dimensions_present = sorted({item["dimension"] for item in normalized})
    stale = [item["fact_id"] for item in normalized if item["freshness"]["status"] == "stale"]
    future = [item["fact_id"] for item in normalized if item["freshness"]["status"] == "future_dated"]
    unassessed = [item["fact_id"] for item in normalized if item["freshness"]["status"] == "not_assessed"]
    return {
        "schema": "ma.investment-research/v1",
        "instrument_key": instrument_key,
        "generated_at_utc": current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "fact_count": len(normalized),
        "dimensions_covered": dimensions_present,
        "facts": normalized,
        "data_quality": {
            "status": "insufficient_evidence" if not normalized or stale or future else (
                "freshness_not_assessed" if unassessed else "evidence_recorded"
            ),
            "stale_fact_ids": stale,
            "future_dated_fact_ids": future,
            "freshness_not_assessed_fact_ids": unassessed,
            "limitations": [
                "This packet validates metadata and provenance fields; it does not independently verify source contents.",
                "A source citation does not establish that a claim is true, material, or correctly interpreted.",
                "Facts without an explicit freshness limit are not assessed for staleness.",
                "Assumptions remain labeled as assumptions and must not be presented as sourced facts.",
            ],
        },
    }
