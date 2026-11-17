# ClinicalTrials.gov API v2 adapter

## Purpose

The adapter in `report_engine/clinical_trials.py` retrieves one exact public NCT study record and extracts registry observations useful for biotech diligence. It uses the modern ClinicalTrials.gov API v2 endpoint:

`https://clinicaltrials.gov/api/v2/studies/{NCT_ID}`

The retired classic API must not be used.

## Extracted fields

Where present, the adapter records:

- Brief study title.
- Overall recruitment status.
- Study type and registered phase.
- Lead sponsor.
- Registered enrollment count and whether it is estimated or actual.
- Primary completion date and its registry date type.
- Registered primary outcome measures and time frames.
- Registered interventions.
- Whether a results section is present.

Each fact retains the NCT ID, exact registry source URL, source-field reference, record last-update date (or first-posted date fallback), first-posted date, and retrieval timestamp.

## Issuer and product attribution

The caller must provide the exact instrument key and an explicit `attribution_basis` explaining why the study is relevant to that issuer/product. The adapter does not infer that the lead sponsor owns the listed company, that a drug is the issuer's asset, or that the issuer will capture the economics. The returned packet labels this attribution as caller-supplied and not independently verified.

## Interpretation limits

- A registered trial is not proof of efficacy, safety, FDA approval, commercial viability, or future revenue.
- A results section being present does not imply positive or clinically meaningful results.
- Recruitment status, trial phase, enrollment target, and completion dates are registry fields; enrollment and completion dates may be estimated.
- Registry records are submitted by responsible parties. NLM states it does not verify the scientific validity or relevance of submitted information.
- The adapter does not interpret statistical power, endpoint hierarchy/multiplicity, protocol amendments, adverse events, trial results, regulatory filings, or peer-reviewed literature.
- Trial status and posted information can change. Preserve observation and retrieval dates and re-check the record before relying on it.

## Verification

Offline tests use deterministic study fixtures and an injected transport. They verify exact NCT identity, required issuer-attribution rationale, status/phase/endpoint extraction, date provenance, and missing-results behavior. They do not certify live API availability or clinical claims.
