"""Validated identity and venue-evidence contract for investment candidates.

This module deliberately performs no network lookup. A venue is considered
verified only when a caller supplies timestamped, source-attributed evidence
for the exact instrument/product identifier.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import urlparse

ASSET_CLASSES = {"listed_equity", "tokenized_equity", "crypto"}
VERIFICATION_STATES = {"verified", "unavailable", "not_verified"}


def _required_text(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required and must be a non-empty string")
    return value.strip()


def _optional_text(data: Mapping[str, Any], field: str) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string when supplied")
    return value.strip()


def _utc_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def normalize_instrument(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize an equity, tokenized-equity, or crypto identity."""
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be a mapping")
    asset_class = _required_text(candidate, "asset_class").lower()
    if asset_class not in ASSET_CLASSES:
        raise ValueError(f"asset_class must be one of: {', '.join(sorted(ASSET_CLASSES))}")

    record: dict[str, Any] = {
        "asset_class": asset_class,
        "name": _required_text(candidate, "name"),
        "symbol": _required_text(candidate, "symbol").upper(),
        "quote_currency": _required_text(candidate, "quote_currency").upper(),
    }

    if asset_class == "listed_equity":
        record.update({
            "issuer": _required_text(candidate, "issuer"),
            "exchange": _required_text(candidate, "exchange").upper(),
            "security_type": _optional_text(candidate, "security_type") or "common_stock",
        })
        if candidate.get("network") or candidate.get("contract_address"):
            raise ValueError("listed_equity must not declare a token network or contract address")
    elif asset_class == "tokenized_equity":
        record.update({
            "underlying_issuer": _required_text(candidate, "underlying_issuer"),
            "underlying_symbol": _required_text(candidate, "underlying_symbol").upper(),
            "product_issuer": _required_text(candidate, "product_issuer"),
            "rights_summary": _required_text(candidate, "rights_summary"),
            "redemption_terms": _required_text(candidate, "redemption_terms"),
        })
        record["network"] = _optional_text(candidate, "network")
        record["contract_address"] = _optional_text(candidate, "contract_address")
        if record["contract_address"]:
            record["contract_address"] = record["contract_address"].lower()
    else:
        record["network"] = _optional_text(candidate, "network")
        record["contract_address"] = _optional_text(candidate, "contract_address")
        record["protocol"] = _optional_text(candidate, "protocol")
        if record["network"] and record["contract_address"]:
            record["contract_address"] = record["contract_address"].lower()

    venue = candidate.get("venue")
    if venue is not None:
        if not isinstance(venue, Mapping):
            raise ValueError("venue must be a mapping when supplied")
        record["venue"] = {
            "name": _required_text(venue, "name"),
            "product_id": _required_text(venue, "product_id"),
            "market_type": _required_text(venue, "market_type").lower(),
        }
    else:
        record["venue"] = None

    identity_parts = [asset_class, record["symbol"], record["quote_currency"]]
    if asset_class == "listed_equity":
        identity_parts.extend([record["issuer"], record["exchange"]])
    elif asset_class == "tokenized_equity":
        identity_parts.extend([
            record["underlying_issuer"], record["underlying_symbol"],
            record["product_issuer"], record["network"] or "",
            record["contract_address"] or "",
        ])
    else:
        identity_parts.extend([record["network"] or "", record["contract_address"] or ""])
    record["instrument_key"] = "|".join(identity_parts).casefold()
    return record


def validate_venue_evidence(
    instrument: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    max_age: timedelta = timedelta(hours=24),
) -> dict[str, Any]:
    """Validate exact-product venue evidence without making a live availability claim."""
    if not isinstance(instrument, Mapping) or instrument.get("asset_class") not in ASSET_CLASSES:
        raise ValueError("instrument must be a normalized instrument record")
    if evidence is None:
        return {"status": "not_verified", "reason": "No venue evidence was supplied."}
    if not isinstance(evidence, Mapping):
        raise ValueError("evidence must be a mapping")
    state = _required_text(evidence, "status").lower()
    if state not in VERIFICATION_STATES:
        raise ValueError(f"status must be one of: {', '.join(sorted(VERIFICATION_STATES))}")
    venue = _required_text(evidence, "venue")
    if state == "not_verified":
        result = {
            "status": "not_verified",
            "venue": venue,
            "reason": _optional_text(evidence, "reason") or "Evidence is insufficient to establish current availability.",
        }
        source_url = _optional_text(evidence, "source_url")
        if source_url is not None:
            parsed_url = urlparse(source_url)
            if parsed_url.scheme != "https" or not parsed_url.netloc:
                raise ValueError("source_url must be an HTTPS URL")
            result["source_url"] = source_url
        observed_value = evidence.get("observed_at_utc")
        if observed_value is not None:
            observed = _utc_datetime(observed_value, "observed_at_utc")
            result["observed_at_utc"] = observed.isoformat().replace("+00:00", "Z")
        return result
    if state == "unavailable":
        source_url = _required_text(evidence, "source_url")
        parsed_url = urlparse(source_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise ValueError("source_url must be an HTTPS URL")
        observed = _utc_datetime(evidence.get("observed_at_utc"), "observed_at_utc")
        return {
            "status": "unavailable",
            "venue": venue,
            "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
            "source_url": source_url,
            "reason": _required_text(evidence, "reason"),
        }

    source_url = _required_text(evidence, "source_url")
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("source_url must be an HTTPS URL")
    observed = _utc_datetime(evidence.get("observed_at_utc"), "observed_at_utc")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    age = current.astimezone(timezone.utc) - observed
    if age < timedelta(0):
        return {"status": "not_verified", "venue": venue, "reason": "Evidence timestamp is in the future."}
    if age > max_age:
        return {
            "status": "not_verified", "venue": venue,
            "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
            "reason": "Venue evidence is stale and cannot establish current availability.",
        }

    product_id = _required_text(evidence, "product_id")
    market_type = _required_text(evidence, "market_type").lower()
    if instrument.get("venue") is None:
        return {"status": "not_verified", "venue": venue, "reason": "The instrument has no declared venue product identity."}
    declared = instrument["venue"]
    if (
        venue.casefold() != declared["name"].casefold()
        or product_id.casefold() != declared["product_id"].casefold()
        or market_type != declared["market_type"]
    ):
        return {
            "status": "not_verified", "venue": venue,
            "reason": "Evidence does not match the candidate's exact venue, product ID, and market type.",
        }
    return {
        "status": "verified",
        "venue": venue,
        "product_id": product_id,
        "market_type": market_type,
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "source_url": source_url,
        "evidence_note": _optional_text(evidence, "evidence_note"),
        "age_seconds": int(age.total_seconds()),
    }


def build_instrument_record(
    candidate: Mapping[str, Any],
    venue_evidence: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a report-safe candidate identity with explicit venue-verification state."""
    instrument = normalize_instrument(candidate)
    instrument["venue_verification"] = validate_venue_evidence(
        instrument, venue_evidence, now=now
    )
    return instrument
