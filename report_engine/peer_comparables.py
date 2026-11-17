"""Explicit-criteria equity peer valuation; no automatic peer discovery or ranking."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from statistics import median
from typing import Any, Mapping

from .fundamentals import calculate_valuation_multiples


PEER_CRITERIA = (
    "sector",
    "business_model",
    "geography",
    "market_cap_band",
    "revenue_model",
    "accounting_basis",
    "rationale",
)
MULTIPLES = ("price_to_earnings", "price_to_sales", "price_to_book")


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not number.is_finite():
        raise ValueError(f"{field} must be finite")
    return number


def _fmt(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _analyze_entity(entity: Mapping[str, Any], label: str) -> dict[str, Any]:
    key = _required_text(entity.get("instrument_key"), f"{label}.instrument_key")
    asset_class = _required_text(entity.get("asset_class"), f"{label}.asset_class")
    if asset_class not in {"listed_equity", "tokenized_equity"}:
        raise ValueError(f"{label}.asset_class must be listed_equity or tokenized_equity")
    name = _required_text(entity.get("name"), f"{label}.name")
    facts = entity.get("facts")
    if not isinstance(facts, list):
        raise ValueError(f"{label}.facts must be a list")
    multiples = calculate_valuation_multiples(
        facts,
        instrument_key=key,
        market_cap=entity.get("market_cap"),
        earnings_period_basis=entity.get("earnings_period_basis"),
    )
    return {
        "instrument_key": key,
        "asset_class": asset_class,
        "name": name,
        "facts": [dict(item) for item in facts],
        "market_cap": dict(entity.get("market_cap") or {}),
        "earnings_period_basis": entity.get("earnings_period_basis"),
        "valuation_metrics": multiples,
    }


def calculate_peer_comparables(
    candidate: Mapping[str, Any],
    peers: list[Mapping[str, Any]],
    *,
    minimum_peer_count: int = 3,
) -> dict[str, Any]:
    """Calculate median equity valuation multiples from an explicit analyst-selected peer set.

    Peer membership is never inferred. Each peer must include a written rationale and
    sector, business-model, geography, size-band, revenue-model, and accounting-basis
    criteria. The function calculates peer multiples from each peer's own sourced facts
    and market-cap observation. It does not certify that the analyst's peer selection
    is economically appropriate.
    """
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be a mapping")
    if not isinstance(peers, list):
        raise ValueError("peers must be a list")
    if isinstance(minimum_peer_count, bool) or not isinstance(minimum_peer_count, int) or minimum_peer_count < 2:
        raise ValueError("minimum_peer_count must be an integer of at least 2")

    candidate_result = _analyze_entity(candidate, "candidate")
    peer_results: list[dict[str, Any]] = []
    seen = {candidate_result["instrument_key"]}
    for index, peer in enumerate(peers):
        if not isinstance(peer, Mapping):
            raise ValueError(f"peers[{index}] must be a mapping")
        peer_result = _analyze_entity(peer, f"peers[{index}]")
        key = peer_result["instrument_key"]
        if key in seen:
            raise ValueError("peer instrument keys must be unique and must exclude the candidate")
        if peer_result["asset_class"] != candidate_result["asset_class"]:
            raise ValueError("candidate and peers must use the same equity asset class")
        criteria = peer.get("selection_criteria")
        if not isinstance(criteria, Mapping):
            raise ValueError(f"peers[{index}].selection_criteria must be a mapping")
        normalized_criteria = {
            field: _required_text(criteria.get(field), f"peers[{index}].selection_criteria.{field}")
            for field in PEER_CRITERIA
        }
        peer_result["selection_criteria"] = normalized_criteria
        peer_results.append(peer_result)
        seen.add(key)

    peer_count = len(peer_results)
    metrics: dict[str, dict[str, Any]] = {}
    missing_metrics: dict[str, str] = {}
    candidate_metrics = candidate_result["valuation_metrics"].get("metrics", {})

    for multiple in MULTIPLES:
        observations: list[tuple[str, Decimal]] = []
        for peer in peer_results:
            metric = (peer["valuation_metrics"].get("metrics") or {}).get(multiple)
            if metric is not None:
                observations.append((
                    peer["instrument_key"],
                    _decimal(metric.get("value"), f"{peer['instrument_key']}.{multiple}"),
                ))
        if len(observations) < minimum_peer_count:
            missing_metrics[multiple] = (
                f"Only {len(observations)} peers have a valid {multiple} observation; "
                f"at least {minimum_peer_count} are required."
            )
            continue

        values = [value for _, value in observations]
        peer_median = _median(values)
        candidate_metric = candidate_metrics.get(multiple)
        comparison = None
        if candidate_metric is not None and peer_median > 0:
            candidate_value = _decimal(candidate_metric.get("value"), f"candidate.{multiple}")
            comparison = _fmt((candidate_value / peer_median - Decimal("1")) * Decimal("100"))
        metrics[multiple] = {
            "peer_count": len(observations),
            "peer_instrument_keys": [key for key, _ in observations],
            "median": _fmt(peer_median),
            "minimum": _fmt(min(values)),
            "maximum": _fmt(max(values)),
            "candidate_value": candidate_metric.get("value") if candidate_metric else None,
            "candidate_premium_discount_pct_vs_median": comparison,
            "interpretation": (
                "Positive values indicate the candidate multiple is above the peer median; "
                "negative values indicate it is below. This is a descriptive comparison, not a buy/sell signal."
            ),
        }

    if peer_count < minimum_peer_count:
        status = "insufficient_peer_coverage"
    elif not metrics:
        status = "insufficient_peer_coverage"
    elif missing_metrics:
        status = "partial"
    else:
        status = "complete"

    return {
        "schema": "ma.peer-comparables/v1",
        "candidate_instrument_key": candidate_result["instrument_key"],
        "asset_class": candidate_result["asset_class"],
        "peer_selection_method": "explicit_analyst_selected",
        "peer_count": peer_count,
        "minimum_peer_count": minimum_peer_count,
        "candidate": candidate_result,
        "candidate_valuation_metrics": candidate_result["valuation_metrics"],
        "peers": peer_results,
        "metrics": metrics,
        "missing_metrics": missing_metrics,
        "status": status,
        "limitations": [
            "Peer membership and selection criteria are analyst supplied and are not independently certified.",
            "Sector, business model, geography, size, revenue mix, accounting policy, growth, leverage, and capital intensity can make multiples non-comparable.",
            "Peer medians are descriptive statistics, not intrinsic value estimates, target prices, or investment recommendations.",
            "Only peers with a valid source-attributed multiple contribute to that multiple's median.",
            "Negative earnings or book equity do not generate conventional P/E or P/B multiples.",
        ],
    }
