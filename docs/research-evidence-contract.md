# Source-attributed investment research evidence contract

## Purpose and limits

The implementation in `report_engine/research.py` provides a deterministic, source-attributed record format for investment research. It is designed to preserve the distinction between sourced observations, estimates, disputed claims, unverified claims, and explicit analyst/user assumptions.

It validates metadata and provenance fields only. It does **not** retrieve source material, authenticate a publisher, independently confirm that a statement appears at the cited location, judge materiality, or establish that a claim is true. A citation is traceability, not proof.

## Fact record

Each fact requires:

- Unique `fact_id` within the packet.
- Exact `instrument_key` from the instrument identity layer.
- Supported research `dimension`, human-readable `label`, scalar `value`, and `unit`.
- `source_kind` and `evidence_quality`.
- `as_of_utc` and `retrieved_at_utc` as timezone-aware ISO-8601 timestamps.

External source kinds require a source name and HTTPS URL. A `verified_source` quality label also requires a specific source reference (e.g., filing section, table, page, endpoint, or protocol document section). The label records the submitter's evidence classification; it is not an automated verification result.

User and analyst assumptions require an explicit `assumption_note` and cannot carry an external source URL. They remain visibly labeled as assumptions.

## Research dimensions

The schema recognizes business model, revenue/growth, margins, cash flow, debt/liquidity, valuation, capital allocation, competition, clinical development, regulatory matters, patents/IP, reimbursement, product adoption, customer concentration, technology differentiation, protocol utility/adoption, developer activity, tokenomics, supply/unlocks, holder concentration, governance, security, protocol usage/revenue, market price/volume/structure, volatility, derivatives positioning, catalysts, risks, and thesis invalidation.

The dimension list is a classification aid, not a claim that every dimension is relevant to every asset.

## Freshness and quality

Freshness is assessed only when a caller supplies an explicit per-dimension maximum age. Without a policy, the fact is marked `not_assessed`; the engine does not invent universal expiry rules for financial statements, clinical trial updates, token unlock schedules, or market observations.

- `fresh`: observation is within the configured age.
- `stale`: observation exceeds the configured age.
- `future_dated`: observation timestamp is later than packet generation.
- `not_assessed`: no freshness threshold was supplied.

Stale, future-dated, disputed, or unverified facts make packet data quality `insufficient_evidence`. Estimated facts are retained and explicitly listed; they are not silently upgraded to verified facts. If no freshness policy is provided, the packet status is `freshness_not_assessed` unless stronger quality issues already require `insufficient_evidence`.

## Packet behavior

`build_research_packet` rejects facts for a different instrument, duplicate fact IDs, invalid dimensions/source kinds, malformed timestamps, non-HTTPS external URLs, non-finite numeric values, and unsupported freshness policies. It records dimension coverage and lists stale, future-dated, unassessed, disputed, unverified, and estimated fact IDs.

The packet does not calculate valuation, growth rates, scenario returns, or investment recommendations. Those require separately specified calculation logic and explicit assumptions.

## Current provider adapters and implementation boundary

The shared research-fact module is a data contract. Two read-only issuer/biotech source adapters now feed it:

- `report_engine/sec_edgar.py`: SEC EDGAR Company Facts for a bounded set of U.S. GAAP USD fundamentals. Requires an explicit CIK and SEC User-Agent; it does not resolve tickers to CIKs, parse narrative filings, calculate total debt/free cash flow/valuation, or reconcile restatements.
- `report_engine/clinical_trials.py`: ClinicalTrials.gov API v2 for one exact NCT record. Requires caller-supplied issuer-to-trial attribution; it does not prove sponsor ownership, efficacy, safety, regulatory approval, or commercial success.

These adapters preserve source URLs, field references, publication/filing or record-update dates, and retrieval timestamps. Offline tests use fixtures and injected transports; they do not certify live endpoint availability. The adapters do not independently authenticate source content or validate the scientific/financial interpretation of each record.

Crypto/on-chain fundamentals, broader regulatory-event coverage, issuer narrative filing analysis, source-content verification, conflict reconciliation, provider licensing/coverage checks, and peer/valuation calculations remain separate work. Reports must not imply that a provider was queried merely because a valid source record can be constructed.

## Safety and analytical boundaries

- No account credentials, private account data, order placement, or trading is introduced.
- Sourced observations and analyst/user assumptions remain distinguishable.
- A complete-looking packet is not equivalent to an investment thesis.
- Missing evidence is disclosed rather than replaced by invented values.
- Scenario probabilities, target prices, and expected returns are not produced by this contract.
