"""Read-only DeFiLlama free API adapter for protocol TVL, fees, and revenue.

Protocol slug and issuer/token attribution are caller-supplied. Aggregated protocol
metrics are not proof of token-holder value capture or ownership.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .research import normalize_research_fact

BASE_URL = "https://api.llama.fi"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
FEE_METRICS = (
    ("dailyFees", "protocol_fees", "Daily protocol fees"),
    ("dailyRevenue", "protocol_revenue", "Daily protocol revenue"),
    ("dailyHoldersRevenue", "protocol_revenue", "Daily token-holder revenue"),
)


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_iso(value: Any, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite Unix timestamp")
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError(f"{field} is outside the supported timestamp range") from exc


def _slug(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("protocol_slug must be a non-empty slug")
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
        raise ValueError("protocol_slug contains unsupported characters")
    return value


def _latest_tvl(rows: Any) -> tuple[float, int] | None:
    if not isinstance(rows, list):
        return None
    valid = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp, value = row.get("date"), row.get("totalLiquidityUSD")
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(float(value)) or value < 0):
            continue
        valid.append((float(timestamp), float(value)))
    if not valid:
        return None
    timestamp, value = max(valid, key=lambda item: item[0])
    return value, int(timestamp)


def _latest_chart(rows: Any) -> tuple[float, int] | None:
    if not isinstance(rows, list):
        return None
    valid = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            continue
        timestamp, value = row
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(float(value))):
            continue
        valid.append((float(timestamp), float(value)))
    if not valid:
        return None
    timestamp, value = max(valid, key=lambda item: item[0])
    return value, int(timestamp)


class DeFiLlamaProtocolResearch:
    """Fetch public protocol TVL and daily fee/revenue series without an API key."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        user_agent: str = "MASTER-ARSENAL/0.3 (public protocol research client)",
        fetch_json: Callable[[str, dict[str, str], float], Any] | None = None,
    ) -> None:
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be a finite positive number")
        if not isinstance(user_agent, str) or not user_agent.strip() or "\n" in user_agent or "\r" in user_agent:
            raise ValueError("user_agent must be a non-empty single-line string")
        self.timeout_seconds = float(timeout_seconds)
        self.user_agent = user_agent.strip()
        self._fetch_json = fetch_json or self._http_fetch_json

    @staticmethod
    def _http_fetch_json(url: str, headers: dict[str, str], timeout: float) -> Any:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type.lower():
                raise ValueError("DeFiLlama response was not declared as JSON")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("DeFiLlama response exceeds the 20 MB safety limit")
        return json.loads(payload.decode("utf-8"))

    def _get(self, path: str, query: dict[str, str] | None = None) -> tuple[str, Any]:
        url = BASE_URL + path
        if query:
            url += "?" + urlencode(query)
        payload = self._fetch_json(
            url,
            {"User-Agent": self.user_agent, "Accept": "application/json"},
            self.timeout_seconds,
        )
        return url, payload

    def fetch_protocol_research(
        self,
        *,
        protocol_slug: str,
        instrument_key: str,
        attribution_basis: str,
        retrieved_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Fetch a caller-identified protocol and attach metrics to a caller-identified instrument."""
        slug = _slug(protocol_slug)
        if not isinstance(instrument_key, str) or not instrument_key.strip():
            raise ValueError("instrument_key is required")
        if not isinstance(attribution_basis, str) or not attribution_basis.strip():
            raise ValueError("attribution_basis is required; do not infer token value capture")
        retrieved_iso = _utc_iso(retrieved_at or datetime.now(timezone.utc))
        protocol_url, protocol = self._get(f"/protocol/{slug}")
        if not isinstance(protocol, dict):
            raise ValueError("DeFiLlama protocol response must be a JSON object")
        protocol_name = protocol.get("name")
        if not isinstance(protocol_name, str) or not protocol_name.strip():
            raise ValueError("DeFiLlama response is missing protocol name")
        returned_slug = protocol.get("slug")
        if returned_slug is not None and returned_slug != slug:
            raise ValueError("DeFiLlama returned a different protocol slug")

        facts: list[dict[str, Any]] = []
        missing: list[str] = []
        errors: list[str] = []
        base = {
            "instrument_key": instrument_key,
            "source_kind": "on_chain_data",
            "evidence_quality": "verified_source",
            "source_name": "DeFiLlama public API",
            "retrieved_at_utc": retrieved_iso,
        }

        tvl = _latest_tvl(protocol.get("tvl"))
        if tvl is None:
            missing.append("protocol_tvl")
        else:
            value, timestamp = tvl
            facts.append(normalize_research_fact({
                **base,
                "fact_id": f"defillama-{slug}-protocol-tvl-{timestamp}",
                "dimension": "protocol_usage",
                "label": f"{protocol_name} total value locked (TVL)",
                "value": str(value),
                "unit": "USD",
                "source_url": protocol_url,
                "source_reference": f"protocol/{slug}; tvl[{timestamp}].totalLiquidityUSD",
                "as_of_utc": _epoch_iso(timestamp, "TVL timestamp"),
            }))

        fee_summary: dict[str, Any] = {}
        for data_type, dimension, label in FEE_METRICS:
            try:
                fee_url, summary = self._get(
                    f"/summary/fees/{slug}", {"dataType": data_type}
                )
            except Exception as exc:
                missing.append(data_type)
                errors.append(f"{data_type}: {type(exc).__name__}: {exc}")
                continue
            if not isinstance(summary, dict):
                missing.append(data_type)
                errors.append(f"{data_type}: response was not a JSON object")
                continue
            point = _latest_chart(summary.get("totalDataChart"))
            if point is None:
                missing.append(data_type)
                continue
            value, timestamp = point
            facts.append(normalize_research_fact({
                **base,
                "fact_id": f"defillama-{slug}-{data_type}-{timestamp}",
                "dimension": dimension,
                "label": f"{protocol_name} {label.lower()}",
                "value": str(value),
                "unit": "USD/day",
                "source_url": fee_url,
                "source_reference": (
                    f"summary/fees/{slug}?dataType={data_type}; "
                    f"totalDataChart[{timestamp}]"
                ),
                "as_of_utc": _epoch_iso(timestamp, f"{data_type} timestamp"),
            }))
            fee_summary[data_type] = {
                "latest_daily_value_usd": str(value),
                "as_of_utc": _epoch_iso(timestamp, f"{data_type} timestamp"),
            }

        chains = protocol.get("chains") if isinstance(protocol.get("chains"), list) else []
        return {
            "provider": "DeFiLlama public API",
            "protocol_slug": slug,
            "protocol_name": protocol_name,
            "category": protocol.get("category"),
            "symbol": protocol.get("symbol"),
            "chains": chains,
            "gecko_id": protocol.get("gecko_id"),
            "instrument_key": instrument_key,
            "protocol_instrument_attribution": {
                "basis": attribution_basis.strip(),
                "status": "caller_supplied_not_independently_verified",
                "warning": "Protocol-level TVL, fees, or revenue do not by themselves establish token-holder value capture, issuer ownership, or token economic rights.",
            },
            "source_url": protocol_url,
            "retrieved_at_utc": retrieved_iso,
            "facts": facts,
            "fee_metrics": fee_summary,
            "missing_metrics": missing,
            "provider_errors": errors,
            "data_quality_status": "insufficient_evidence" if not facts else (
                "partial" if missing else "evidence_recorded"
            ),
            "limitations": [
                "DeFiLlama metrics are aggregated protocol-level estimates and may reflect methodology choices, double-counting controls, and source coverage limits.",
                "TVL is not protocol revenue, token market capitalization, or token-holder value capture.",
                "Protocol fees, protocol revenue, and token-holder revenue are distinct measures and must not be conflated.",
                "Missing fee/revenue series are not zero and may be unavailable for protocols without covered methodology.",
                "Protocol-to-token/issuer attribution is caller supplied and not independently verified.",
                "The adapter does not provide token supply, unlock schedules, holder concentration, smart-contract audits, exploit history, governance quality, or regulatory analysis.",
                "Offline tests use fixtures; live API availability and the current methodology for a given protocol are not certified.",
            ],
        }
