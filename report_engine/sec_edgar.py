"""Read-only SEC EDGAR Company Facts adapter for U.S. issuer fundamentals.

CIK-to-instrument mapping must be supplied explicitly. This adapter does not
infer that a ticker identifies a particular filer or security.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.request import Request, urlopen

from .research import normalize_research_fact

SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_TICKER_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
MAX_RESPONSE_BYTES = 25 * 1024 * 1024

# The first concept present with a usable USD unit is selected. Tags are
# alternatives, not additive components; this avoids double-counting.
METRICS = {
    "revenue": {
        "concepts": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
        "kind": "duration",
    },
    "operating_income": {"concepts": ("OperatingIncomeLoss",), "kind": "duration"},
    "net_income": {"concepts": ("NetIncomeLoss",), "kind": "duration"},
    "gross_profit": {"concepts": ("GrossProfit",), "kind": "duration"},
    "capital_expenditures": {
        "concepts": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
        "kind": "duration",
    },
    "current_assets": {"concepts": ("AssetsCurrent",), "kind": "instant"},
    "current_liabilities": {"concepts": ("LiabilitiesCurrent",), "kind": "instant"},
    "stockholders_equity": {
        "concepts": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        "kind": "instant",
    },
    "operating_cash_flow": {
        "concepts": ("NetCashProvidedByUsedInOperatingActivities",),
        "kind": "duration",
    },
    "total_assets": {"concepts": ("Assets",), "kind": "instant"},
    "cash_and_equivalents": {
        "concepts": (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
        "kind": "instant",
    },
}
FORM_QUALITY = {
    "10-K": "audited_financials",
    "20-F": "audited_financials",
    "40-F": "audited_financials",
    "10-Q": "issuer_disclosure",
    "6-K": "issuer_disclosure",
    "8-K": "issuer_disclosure",
}


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _date_end_utc(value: str, field: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"SEC {field} must be YYYY-MM-DD") from exc
    return _utc_iso(parsed)


def _normalize_cik(cik: str | int) -> str:
    text = str(cik).strip()
    if not text.isdigit() or not 1 <= int(text) <= 9_999_999_999:
        raise ValueError("cik must be a numeric SEC Central Index Key")
    return text.zfill(10)


class SECEdgarCompanyFacts:
    """Fetch and normalize selected USD fundamentals from SEC Company Facts."""

    def __init__(
        self,
        user_agent: str | None = None,
        *,
        timeout_seconds: float = 20.0,
        fetch_json: Callable[[str, dict[str, str], float], dict[str, Any]] | None = None,
    ) -> None:
        self.user_agent = (user_agent or os.environ.get("MASTER_ARSENAL_SEC_USER_AGENT", "")).strip()
        if not self.user_agent:
            raise ValueError(
                "SEC User-Agent is required; set MASTER_ARSENAL_SEC_USER_AGENT "
                "to identify the application and a responsible contact."
            )
        if len(self.user_agent) < 8 or "\n" in self.user_agent or "\r" in self.user_agent:
            raise ValueError("SEC User-Agent must be a valid descriptive header value")
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be a finite positive number")
        self.timeout_seconds = float(timeout_seconds)
        self._fetch_json = fetch_json or self._http_fetch_json

    @staticmethod
    def _http_fetch_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type.lower():
                raise ValueError("SEC response was not declared as JSON")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("SEC Company Facts response exceeds the 25 MB safety limit")
        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("SEC Company Facts response must be a JSON object")
        return decoded

    def fetch_facts(
        self,
        *,
        cik: str | int,
        instrument_key: str,
        issuer_name: str,
        period: str = "annual",
        retrieved_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Fetch selected facts; period is annual or quarterly for duration metrics."""
        if period not in {"annual", "quarterly"}:
            raise ValueError("period must be 'annual' or 'quarterly'")
        if not isinstance(instrument_key, str) or not instrument_key.strip():
            raise ValueError("instrument_key is required")
        if not isinstance(issuer_name, str) or not issuer_name.strip():
            raise ValueError("issuer_name is required")
        cik_text = _normalize_cik(cik)
        retrieval_time = retrieved_at or datetime.now(timezone.utc)
        retrieved_iso = _utc_iso(retrieval_time)
        url = SEC_COMPANYFACTS_URL.format(cik=cik_text)
        payload = self._fetch_json(
            url,
            {"User-Agent": self.user_agent, "Accept": "application/json"},
            self.timeout_seconds,
        )
        if not isinstance(payload, dict):
            raise ValueError("SEC Company Facts response must be a JSON object")
        entity_name = payload.get("entityName")
        if not isinstance(entity_name, str) or not entity_name.strip():
            raise ValueError("SEC Company Facts response is missing entityName")
        response_cik = payload.get("cik")
        if not isinstance(response_cik, int) or response_cik != int(cik_text):
            raise ValueError("SEC Company Facts response CIK does not match the requested CIK")
        facts_root = payload.get("facts")
        if not isinstance(facts_root, dict):
            raise ValueError("SEC Company Facts response is missing facts")
        us_gaap = facts_root.get("us-gaap")
        if not isinstance(us_gaap, dict):
            raise ValueError("SEC Company Facts response has no us-gaap taxonomy")

        normalized: list[dict[str, Any]] = []
        missing: list[str] = []
        for dimension, spec in METRICS.items():
            selected: tuple[str, dict[str, Any]] | None = None
            for concept in spec["concepts"]:
                entry = us_gaap.get(concept)
                if not isinstance(entry, dict) or not isinstance(entry.get("units"), dict):
                    continue
                usd_rows = entry["units"].get("USD")
                if not isinstance(usd_rows, list):
                    continue
                candidates = []
                for row in usd_rows:
                    if not isinstance(row, dict) or row.get("form") not in FORM_QUALITY:
                        continue
                    if not isinstance(row.get("val"), (int, float)) or isinstance(row.get("val"), bool):
                        continue
                    try:
                        end = datetime.strptime(row.get("end", ""), "%Y-%m-%d").date()
                    except (TypeError, ValueError):
                        continue
                    if spec["kind"] == "duration":
                        try:
                            start = datetime.strptime(row.get("start", ""), "%Y-%m-%d").date()
                        except (TypeError, ValueError):
                            continue
                        days = (end - start).days + 1
                        if period == "annual" and not 300 <= days <= 400:
                            continue
                        if period == "quarterly" and not 70 <= days <= 110:
                            continue
                    elif row.get("start") is not None:
                        continue
                    candidates.append(row)
                if candidates:
                    candidates.sort(
                        key=lambda row: (row.get("filed", ""), row.get("end", ""), row.get("accn", "")),
                        reverse=True,
                    )
                    selected = (concept, candidates[0])
                    break
            if selected is None:
                missing.append(dimension)
                continue

            concept, row = selected
            form = row["form"]
            accession = row.get("accn")
            accession_parts = accession.split("-") if isinstance(accession, str) else []
            if (len(accession_parts) != 3
                    or tuple(map(len, accession_parts)) != (10, 2, 6)
                    or not all(part.isdigit() for part in accession_parts)):
                raise ValueError("SEC fact is missing a valid accession number")
            accession_compact = accession.replace("-", "")
            source_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik_text)}/"
                f"{accession_compact}/"
            )
            filed = row.get("filed")
            filed_iso = _date_end_utc(filed, "filed date")
            period_end_iso = _date_end_utc(row["end"], "period end")
            quality = FORM_QUALITY[form]
            fact = {
                "fact_id": f"sec-{cik_text}-{concept}-{row['end']}-{form}-{accession}",
                "instrument_key": instrument_key,
                "dimension": dimension,
                "label": f"{issuer_name.strip()} {dimension.replace('_', ' ')}",
                "value": str(row["val"]),
                "unit": "USD",
                "source_kind": quality,
                "evidence_quality": "verified_source",
                "source_name": f"U.S. SEC EDGAR Company Facts ({entity_name})",
                "source_url": source_url,
                "source_reference": (
                    f"CIK {cik_text}; us-gaap:{concept}; form {form}; "
                    f"filed {filed}; period end {row['end']}; accession {accession}"
                ),
                "as_of_utc": period_end_iso,
                "published_at_utc": filed_iso,
                "retrieved_at_utc": retrieved_iso,
            }
            normalized.append(normalize_research_fact(fact))

        return {
            "provider": "SEC EDGAR Company Facts",
            "provider_entity_name": entity_name,
            "cik": cik_text,
            "instrument_key": instrument_key,
            "period": period,
            "source_url": url,
            "retrieved_at_utc": retrieved_iso,
            "facts": normalized,
            "missing_dimensions": missing,
            "limitations": [
                "SEC Company Facts contains reported XBRL facts, not a complete normalized financial model.",
                "Concept availability and reporting practices vary by issuer; absent concepts are not zero.",
                "The selected concept is the first available alternative, not a sum of potentially overlapping tags.",
                "The adapter does not calculate total debt, free cash flow, valuation multiples, or restated historical series.",
                "The CIK mapping is either caller-supplied or resolved from the SEC ticker directory; neither path independently establishes legal issuer/security identity.",
                "SEC facts and filing references require analyst review before use in an investment conclusion.",
            ],
        }


    @staticmethod
    def _normalize_issuer_name(value: str) -> str:
        import re
        normalized = re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()
        tokens = normalized.split()
        suffixes = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY",
                    "LTD", "LIMITED", "PLC", "LLC", "LP"}
        while tokens and tokens[-1] in suffixes:
            tokens.pop()
        return " ".join(tokens)

    def resolve_ticker(
        self,
        *,
        ticker: str,
        exchange: str | None = None,
        issuer_name: str | None = None,
        retrieved_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Resolve an exact listed-equity ticker/exchange/name against the SEC directory.

        The SEC itself cautions that ticker associations may be incomplete or
        inaccurate. This lookup is a candidate mapping, not proof of security
        ownership, legal identity, or current exchange listing.
        """
        for field, value in (("ticker", ticker), ("exchange", exchange),
                             ("issuer_name", issuer_name)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required for SEC ticker resolution")
        ticker_key = ticker.strip().upper()
        exchange_key = exchange.strip().casefold()
        issuer_key = self._normalize_issuer_name(issuer_name)
        if not issuer_key:
            raise ValueError("issuer_name must contain an issuer name")

        retrieval_time = retrieved_at or datetime.now(timezone.utc)
        retrieved_iso = _utc_iso(retrieval_time)
        payload = self._fetch_json(
            SEC_TICKER_EXCHANGE_URL,
            {"User-Agent": self.user_agent, "Accept": "application/json"},
            self.timeout_seconds,
        )
        if not isinstance(payload, dict):
            raise ValueError("SEC ticker directory must be a JSON object")
        fields = payload.get("fields")
        rows = payload.get("data")
        if not isinstance(fields, list) or not isinstance(rows, list):
            raise ValueError("SEC ticker directory must contain fields and data arrays")
        required = {"cik", "name", "ticker", "exchange"}
        if not required.issubset(set(fields)):
            raise ValueError("SEC ticker directory is missing required columns")
        indexes = {name: fields.index(name) for name in required}
        matches: list[dict[str, Any]] = []
        for row_index, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(fields):
                continue
            raw_ticker = row[indexes["ticker"]]
            raw_exchange = row[indexes["exchange"]]
            raw_name = row[indexes["name"]]
            raw_cik = row[indexes["cik"]]
            if not isinstance(raw_ticker, str) or not isinstance(raw_exchange, str):
                continue
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            if isinstance(raw_cik, bool) or not isinstance(raw_cik, int) or raw_cik <= 0:
                continue
            if raw_ticker.strip().upper() != ticker_key:
                continue
            if raw_exchange.strip().casefold() != exchange_key:
                continue
            matches.append({
                "cik": _normalize_cik(raw_cik),
                "issuer_name": raw_name.strip(),
                "ticker": raw_ticker.strip().upper(),
                "exchange": raw_exchange.strip(),
                "record_index": row_index,
            })

        base = {
            "ticker": ticker_key,
            "exchange": exchange.strip(),
            "source_url": SEC_TICKER_EXCHANGE_URL,
            "retrieved_at_utc": retrieved_iso,
            "limitations": [
                "The SEC periodically updates ticker associations but does not guarantee their accuracy or scope.",
                "The directory is a candidate mapping; issuer/security identity and current listing status require independent confirmation.",
            ],
        }
        if not matches:
            return {"status": "not_found", **base, "candidates": []}

        confirmed = [
            item for item in matches
            if self._normalize_issuer_name(item["issuer_name"]) == issuer_key
        ]
        if not confirmed:
            return {
                "status": "issuer_name_mismatch",
                **base,
                "candidates": matches,
                "reason": "Ticker and exchange matched, but the SEC issuer name did not match the supplied issuer name.",
            }
        if len(confirmed) != 1:
            return {
                "status": "ambiguous",
                **base,
                "candidates": confirmed,
                "reason": "Multiple SEC records match the supplied ticker, exchange, and issuer name.",
            }
        return {"status": "resolved", **base, **confirmed[0]}
