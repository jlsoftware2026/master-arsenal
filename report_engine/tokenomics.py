"""Transparent token supply, unlock, and holder-concentration calculations.

All observations are caller-supplied and source-attributed. This module does not
discover token contracts, infer wallet ownership, forecast unlocks, or authenticate
source contents. Incomplete coverage is reported explicitly.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping
from urllib.parse import urlparse

SCHEMA = "ma.tokenomics/v1"


def _decimal(value: Any, field: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be a finite {'non-negative' if allow_zero else 'positive'} number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite {'non-negative' if allow_zero else 'positive'} number") from exc
    if not result.is_finite() or (result < 0 if allow_zero else result <= 0):
        raise ValueError(f"{field} must be a finite {'non-negative' if allow_zero else 'positive'} number")
    return result


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def _source(record: Mapping[str, Any], label: str) -> dict[str, str]:
    name = record.get("source_name")
    url = record.get("source_url")
    reference = record.get("source_reference")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{label}.source_name is required")
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"{label}.source_url is required")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{label}.source_url must be an HTTPS URL")
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError(f"{label}.source_reference is required")
    return {"source_name": name.strip(), "source_url": url.strip(), "source_reference": reference.strip()}


def _fmt(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _observation(
    record: Mapping[str, Any],
    field: str,
    *,
    instrument_key: str,
    as_of: datetime,
) -> tuple[Decimal, dict[str, str]]:
    if not isinstance(record, Mapping):
        raise ValueError(f"{field} observation must be a mapping")
    if record.get("instrument_key") != instrument_key:
        raise ValueError(f"{field} instrument_key does not match")
    observed = _utc(record.get("as_of_utc"), f"{field}.as_of_utc")
    if observed > as_of:
        raise ValueError(f"{field} observation is after the analysis cutoff")
    unit = record.get("unit")
    if unit != "token":
        raise ValueError(f"{field}.unit must be 'token'")
    value = _decimal(record.get("value"), f"{field}.value")
    provenance = _source(record, field)
    provenance["as_of_utc"] = observed.isoformat().replace("+00:00", "Z")
    provenance["fact_id"] = str(record.get("fact_id") or field)
    return value, provenance


def calculate_tokenomics(
    *,
    instrument_key: str,
    as_of_utc: str,
    circulating_supply: Mapping[str, Any],
    total_supply: Mapping[str, Any],
    max_supply: Mapping[str, Any] | None = None,
    price: Mapping[str, Any] | None = None,
    unlock_events: list[Mapping[str, Any]] | None = None,
    holder_balances: list[Mapping[str, Any]] | None = None,
    holder_coverage_pct: Any | None = None,
) -> dict[str, Any]:
    """Calculate supply ratios, scheduled unlock pressure, and observed holder concentration."""
    if not isinstance(instrument_key, str) or not instrument_key.strip():
        raise ValueError("instrument_key is required")
    key = instrument_key.strip()
    cutoff = _utc(as_of_utc, "as_of_utc")
    circulating, circ_source = _observation(
        circulating_supply, "circulating_supply", instrument_key=key, as_of=cutoff
    )
    total, total_source = _observation(
        total_supply, "total_supply", instrument_key=key, as_of=cutoff
    )
    if circulating > total:
        raise ValueError("circulating_supply cannot exceed total_supply")

    sources = {"circulating_supply": circ_source, "total_supply": total_source}
    maximum = None
    if max_supply is not None:
        maximum, sources["max_supply"] = _observation(
            max_supply, "max_supply", instrument_key=key, as_of=cutoff
        )
        if maximum < total:
            raise ValueError("max_supply cannot be below total_supply")

    price_value = None
    market_cap = None
    fdv = None
    if price is not None:
        if not isinstance(price, Mapping):
            raise ValueError("price observation must be a mapping")
        if price.get("instrument_key") != key:
            raise ValueError("price instrument_key does not match")
        price_time = _utc(price.get("as_of_utc"), "price.as_of_utc")
        if price_time > cutoff:
            raise ValueError("price observation is after the analysis cutoff")
        currency = price.get("quote_currency")
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("price.quote_currency is required")
        price_value = _decimal(price.get("value"), "price.value")
        sources["price"] = _source(price, "price")
        sources["price"]["as_of_utc"] = price_time.isoformat().replace("+00:00", "Z")
        sources["price"]["fact_id"] = str(price.get("fact_id") or "price")
        market_cap = price_value * circulating
        fdv = price_value * (maximum if maximum is not None else total)
    else:
        currency = None

    unlock_results = []
    scheduled_total = Decimal("0")
    horizons = {"30d": cutoff + timedelta(days=30), "90d": cutoff + timedelta(days=90), "365d": cutoff + timedelta(days=365)}
    unlock_sums = {name: Decimal("0") for name in horizons}
    if unlock_events is not None:
        if not isinstance(unlock_events, list):
            raise ValueError("unlock_events must be a list")
        seen_events: set[str] = set()
        for index, event in enumerate(unlock_events):
            if not isinstance(event, Mapping):
                raise ValueError(f"unlock_events[{index}] must be a mapping")
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or not event_id.strip() or event_id in seen_events:
                raise ValueError("unlock event IDs must be unique non-empty strings")
            seen_events.add(event_id)
            event_time = _utc(event.get("unlock_at_utc"), f"unlock_events[{index}].unlock_at_utc")
            amount = _decimal(event.get("amount"), f"unlock_events[{index}].amount")
            if event_time <= cutoff:
                continue
            provenance = _source(event, f"unlock_events[{index}]")
            scheduled_total += amount
            for horizon, end in horizons.items():
                if event_time <= end:
                    unlock_sums[horizon] += amount
            unlock_results.append({
                "event_id": event_id,
                "unlock_at_utc": event_time.isoformat().replace("+00:00", "Z"),
                "amount": str(amount),
                "recipient_category": str(event.get("recipient_category") or "not_classified"),
                **provenance,
            })
        unlock_results.sort(key=lambda item: (item["unlock_at_utc"], item["event_id"]))
    else:
        unlock_results = None

    holder_results = None
    holder_summary = {"status": "not_assessed"}
    if holder_balances is not None:
        if not isinstance(holder_balances, list):
            raise ValueError("holder_balances must be a list")
        coverage = _decimal(holder_coverage_pct, "holder_coverage_pct")
        if coverage > 100:
            raise ValueError("holder_coverage_pct must not exceed 100")
        normalized_holders = []
        seen_holders: set[str] = set()
        for index, holder in enumerate(holder_balances):
            if not isinstance(holder, Mapping):
                raise ValueError(f"holder_balances[{index}] must be a mapping")
            holder_id = holder.get("holder_id")
            if not isinstance(holder_id, str) or not holder_id.strip() or holder_id in seen_holders:
                raise ValueError("holder IDs must be unique non-empty strings")
            seen_holders.add(holder_id)
            if holder.get("instrument_key") != key:
                raise ValueError("holder instrument_key does not match")
            amount = _decimal(holder.get("balance"), f"holder_balances[{index}].balance", allow_zero=True)
            category = holder.get("category")
            if not isinstance(category, str) or not category.strip():
                raise ValueError(f"holder_balances[{index}].category is required")
            provenance = _source(holder, f"holder_balances[{index}]")
            holder_time = _utc(holder.get("as_of_utc"), f"holder_balances[{index}].as_of_utc")
            if holder_time > cutoff:
                raise ValueError("holder observation is after the analysis cutoff")
            normalized_holders.append({
                "holder_id": holder_id,
                "category": category.strip(),
                "balance": str(amount),
                "share_of_circulating_pct": _fmt(amount / circulating * Decimal("100")),
                "as_of_utc": holder_time.isoformat().replace("+00:00", "Z"),
                **provenance,
            })
        normalized_holders.sort(key=lambda item: Decimal(item["balance"]), reverse=True)
        observed_total = sum((Decimal(item["balance"]) for item in normalized_holders), Decimal("0"))
        if observed_total > circulating:
            raise ValueError("observed holder balances cannot exceed circulating supply")
        holder_results = normalized_holders
        holder_summary = {
            "status": "partial" if coverage < 100 else "reported_coverage",
            "coverage_pct": str(coverage),
            "observed_balance": str(observed_total),
            "observed_share_of_circulating_pct": _fmt(observed_total / circulating * Decimal("100")),
            "top_1_observed_pct": normalized_holders[0]["share_of_circulating_pct"] if normalized_holders else "0",
            "top_5_observed_pct": _fmt(sum((Decimal(item["balance"]) for item in normalized_holders[:5]), Decimal("0")) / circulating * Decimal("100")),
            "holder_count": len(normalized_holders),
            "limitations": [
                "Wallet addresses are not necessarily beneficial owners; exchange, custody, contract, treasury, and burn wallets require reliable classification.",
                "Observed concentration applies only to the supplied holder set and coverage declaration; it is not a complete ownership or decentralization measure.",
            ],
        }

    return {
        "schema": SCHEMA,
        "instrument_key": key,
        "as_of_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "supply": {
            "circulating": str(circulating),
            "total": str(total),
            "max": str(maximum) if maximum is not None else None,
            "circulating_pct_of_total": _fmt(circulating / total * Decimal("100")),
            "circulating_pct_of_max": _fmt(circulating / maximum * Decimal("100")) if maximum is not None else None,
            "sources": sources,
        },
        "valuation": {
            "quote_currency": currency,
            "price": str(price_value) if price_value is not None else None,
            "market_cap": str(market_cap) if market_cap is not None else None,
            "fully_diluted_valuation": str(fdv) if fdv is not None else None,
            "source_note": "Market capitalization and FDV are arithmetic estimates from caller-supplied price and supply observations, not independently verified valuations.",
        },
        "unlock_schedule": {
            "status": "not_supplied" if unlock_results is None else "recorded",
            "events": unlock_results,
            "known_future_unlock_total": str(scheduled_total),
            "known_unlocks_pct_of_circulating": {
                name: _fmt(amount / circulating * Decimal("100"))
                for name, amount in unlock_sums.items()
            },
            "coverage_note": "Only supplied scheduled events are included; absence of events does not establish that no future unlocks exist.",
        },
        "holder_concentration": holder_summary,
        "holders": holder_results,
        "limitations": [
            "All inputs are caller-supplied observations and are not authenticated by this calculator.",
            "Supply definitions can differ across providers and may include or exclude locked, bridged, treasury, burned, or non-circulating balances.",
            "Market capitalization and FDV are only comparable when price and supply definitions, units, and timestamps are aligned.",
            "Unlock schedules can change, be delayed, accelerated, or contain discretionary allocations.",
            "No protocol quality, security, governance, legal status, or investment suitability conclusion is produced.",
        ],
    }
