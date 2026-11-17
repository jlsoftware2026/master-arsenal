"""Read-only ClinicalTrials.gov API v2 adapter for biotech diligence.

A caller must explicitly map a registry record to an instrument. Trial sponsorship
alone does not establish that a listed issuer owns or controls the intervention.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.request import Request, urlopen

from .research import normalize_research_fact

BASE_URL = "https://clinicaltrials.gov/api/v2/studies/"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _date_end_utc(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be YYYY-MM-DD")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    return parsed.isoformat().replace("+00:00", "Z")


def _nct_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("nct_id must be NCT followed by eight digits")
    value = value.strip().upper()
    if len(value) != 11 or not value.startswith("NCT") or not value[3:].isdigit():
        raise ValueError("nct_id must be NCT followed by eight digits")
    return value


def _path(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _text_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


class ClinicalTrialsGov:
    """Fetch one exact public study record and normalize registry observations."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        user_agent: str = "MASTER-ARSENAL/0.3 (public research client)",
        fetch_json: Callable[[str, dict[str, str], float], dict[str, Any]] | None = None,
    ) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(user_agent, str) or not user_agent.strip() or "\n" in user_agent or "\r" in user_agent:
            raise ValueError("user_agent must be a non-empty single-line string")
        self.timeout_seconds = float(timeout_seconds)
        self.user_agent = user_agent.strip()
        self._fetch_json = fetch_json or self._http_fetch_json

    @staticmethod
    def _http_fetch_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type.lower():
                raise ValueError("ClinicalTrials.gov response was not declared as JSON")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("ClinicalTrials.gov study response exceeds the 10 MB safety limit")
        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("ClinicalTrials.gov response must be a JSON object")
        return decoded

    def fetch_study(
        self,
        *,
        nct_id: str,
        instrument_key: str,
        attribution_basis: str,
        retrieved_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Fetch one exact NCT record; caller explicitly owns issuer-to-trial attribution."""
        nct = _nct_id(nct_id)
        if not isinstance(instrument_key, str) or not instrument_key.strip():
            raise ValueError("instrument_key is required")
        if not isinstance(attribution_basis, str) or not attribution_basis.strip():
            raise ValueError("attribution_basis is required; do not infer issuer ownership from sponsorship")
        retrieval_time = retrieved_at or datetime.now(timezone.utc)
        retrieved_iso = _utc_iso(retrieval_time)
        url = BASE_URL + nct
        payload = self._fetch_json(
            url,
            {"User-Agent": self.user_agent, "Accept": "application/json"},
            self.timeout_seconds,
        )
        if not isinstance(payload, dict):
            raise ValueError("ClinicalTrials.gov response must be a JSON object")
        protocol = payload.get("protocolSection")
        if not isinstance(protocol, dict):
            raise ValueError("ClinicalTrials.gov response is missing protocolSection")
        returned_nct = _path(protocol, "identificationModule", "nctId")
        if returned_nct != nct:
            raise ValueError("ClinicalTrials.gov returned a different NCT identifier")

        title = _text_or_none(_path(protocol, "identificationModule", "briefTitle"))
        status = _text_or_none(_path(protocol, "statusModule", "overallStatus"))
        last_update = _path(protocol, "statusModule", "studyLastUpdatePostDateStruct", "date")
        first_posted = _path(protocol, "statusModule", "studyFirstPostDateStruct", "date")
        as_of = _date_end_utc(last_update or first_posted, "last update/first posted date")
        published_at = _date_end_utc(first_posted, "first posted date") if first_posted else None
        sponsor = _text_or_none(_path(protocol, "sponsorCollaboratorsModule", "leadSponsor", "name"))
        design = _path(protocol, "designModule") or {}
        study_type = _text_or_none(design.get("studyType"))
        phases = design.get("phases") if isinstance(design.get("phases"), list) else []
        phase_text = ", ".join(str(item) for item in phases if isinstance(item, str))
        enrollment = design.get("enrollmentInfo") if isinstance(design.get("enrollmentInfo"), dict) else {}
        enrollment_count = enrollment.get("count")
        enrollment_type = _text_or_none(enrollment.get("type"))
        completion = _path(protocol, "statusModule", "primaryCompletionDateStruct")
        completion_date = _text_or_none(completion.get("date")) if isinstance(completion, dict) else None
        completion_type = _text_or_none(completion.get("type")) if isinstance(completion, dict) else None

        outcomes = _path(protocol, "outcomesModule", "primaryOutcomes")
        outcome_records = []
        if isinstance(outcomes, list):
            for item in outcomes:
                if not isinstance(item, dict):
                    continue
                outcome_records.append({
                    "measure": _text_or_none(item.get("measure")),
                    "description": _text_or_none(item.get("description")),
                    "time_frame": _text_or_none(item.get("timeFrame")),
                })
        interventions = _path(protocol, "armsInterventionsModule", "interventions")
        intervention_names = []
        if isinstance(interventions, list):
            for item in interventions:
                if isinstance(item, dict):
                    name = _text_or_none(item.get("name"))
                    if name:
                        intervention_names.append(name)

        results_section = payload.get("resultsSection")
        has_results = isinstance(results_section, dict)
        source_url = f"https://clinicaltrials.gov/study/{nct}"
        source_name = "U.S. National Library of Medicine — ClinicalTrials.gov"
        base_fact = {
            "instrument_key": instrument_key,
            "source_kind": "clinical_registry",
            "evidence_quality": "verified_source",
            "source_name": source_name,
            "source_url": source_url,
            "as_of_utc": as_of,
            "published_at_utc": published_at,
            "retrieved_at_utc": retrieved_iso,
        }

        facts: list[dict[str, Any]] = []

        def add_fact(field: str, label: str, value: Any, unit: str, reference: str) -> None:
            if value is None or value == "":
                return
            fact = dict(base_fact)
            fact.update({
                "fact_id": f"ctg-{nct}-{field}",
                "dimension": "clinical_development",
                "label": label,
                "value": value,
                "unit": unit,
                "source_reference": f"{nct}; protocolSection.{reference}",
            })
            facts.append(normalize_research_fact(fact))

        add_fact("title", "Registered study title", title, "text", "identificationModule.briefTitle")
        add_fact("status", "Registered recruitment status", status, "text", "statusModule.overallStatus")
        add_fact("study_type", "Study type", study_type, "text", "designModule.studyType")
        add_fact("phase", "Registered study phase", phase_text or None, "text", "designModule.phases")
        add_fact("lead_sponsor", "Lead study sponsor", sponsor, "text", "sponsorCollaboratorsModule.leadSponsor")
        if isinstance(enrollment_count, int) and not isinstance(enrollment_count, bool):
            add_fact(
                "enrollment", f"{enrollment_type or 'Registered'} enrollment count",
                str(enrollment_count), "participants", "designModule.enrollmentInfo"
            )
        if completion_date:
            add_fact(
                "primary_completion_date", "Primary completion date (registry)",
                completion_date, completion_type or "date_type_not_supplied",
                "statusModule.primaryCompletionDateStruct"
            )
        if outcome_records:
            add_fact(
                "primary_outcomes", "Registered primary outcome measures",
                json.dumps(outcome_records, ensure_ascii=False, sort_keys=True),
                "JSON text", "outcomesModule.primaryOutcomes"
            )
        if intervention_names:
            add_fact(
                "interventions", "Registered interventions",
                json.dumps(intervention_names, ensure_ascii=False),
                "JSON text", "armsInterventionsModule.interventions"
            )
        add_fact(
            "results_posted", "ClinicalTrials.gov results section present",
            has_results, "boolean", "resultsSection"
        )

        return {
            "provider": "ClinicalTrials.gov API v2",
            "nct_id": nct,
            "instrument_key": instrument_key,
            "issuer_trial_attribution": {
                "basis": attribution_basis.strip(),
                "status": "caller_supplied_not_independently_verified",
                "warning": "Lead sponsor or intervention name alone does not establish issuer ownership or economic rights.",
            },
            "study_title": title,
            "overall_status": status,
            "phase": phases,
            "lead_sponsor": sponsor,
            "source_url": source_url,
            "last_update_posted_date": last_update,
            "retrieved_at_utc": retrieved_iso,
            "facts": facts,
            "limitations": [
                "ClinicalTrials.gov is a study registry; registration is not proof of efficacy, safety, regulatory approval, or commercial success.",
                "Registry content is submitted by responsible parties; the NLM does not independently validate scientific validity or relevance.",
                "Sponsor-to-issuer ownership and intervention-to-product mapping are caller supplied and not independently established.",
                "Registry records can change; preserve retrieval time and last-update-posted date and review the current record before relying on it.",
                "The adapter does not analyze trial results, endpoint multiplicity, statistical power, protocol amendments, adverse events, or regulatory filings.",
                "The presence of a results section does not mean the results are positive or clinically meaningful.",
            ],
        }
