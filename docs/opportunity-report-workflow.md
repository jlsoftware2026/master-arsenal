# Local Engine investment opportunity report workflow

## Job contract

The versioned Local Engine protocol now supports `investment.opportunity_report`. It uses the existing validate-and-approve lifecycle and has a fixed PDF output directory: `reports/opportunities`. The caller cannot choose an arbitrary output path.

The job is read-only. It can call only the configured public source adapters and does not access private exchange accounts, store API keys, or place orders.

## Parameters

- `instrument_candidate` (required): asset-class-specific identity input for listed equity, tokenized equity, or crypto.
- `venue_evidence` (optional): timestamped exact-product evidence. If omitted, venue status remains `not_verified`.
- `research_facts` (optional): caller-supplied source-attributed facts. Each fact must use the exact normalized `instrument_key`.
- `freshness_limits_hours` (optional): explicit per-dimension freshness policy. Missing policies remain `not_assessed`.
- `sec_edgar` (optional): exact caller-supplied `cik`, `issuer_name`, and optional `period` (`annual` or `quarterly`). Requires `MASTER_ARSENAL_SEC_USER_AGENT`.
- `clinical_trials` (optional): up to ten records, each containing exact `nct_id` and documented `attribution_basis`. Restricted to equity candidates.
- `defillama` (optional): exact `protocol_slug` and documented `attribution_basis`. Restricted to crypto candidates.
- `scenario_inputs` (optional): complete inputs for the long-only scenario calculator, including the exact instrument key.
- `position_sizing_inputs` (optional): complete inputs for the cash-only sizing calculator, including the exact instrument key.
- `conclusion` (optional): one of `potential_candidate_for_further_diligence`, `wait_for_confirmation`, `insufficient_evidence`, or `avoid_for_now`. Defaults to `insufficient_evidence`.
- `executive_summary`, `risks`, `thesis_invalidation`, `unresolved_questions`, and `methodology_notes` (optional): report narrative fields.

Unknown top-level parameters are rejected. Source adapters are called only when their explicit configuration is present. The Local Engine never infers CIK, NCT, protocol slug, issuer ownership, or token value capture.

## Evidence and conclusion gates

The handler builds the normalized instrument identity first, then collects supplied facts and selected public-provider facts, and constructs a single research packet bound to that instrument key. Duplicate fact IDs, mismatched instrument keys, invalid timestamps, invalid provenance, and unsupported freshness policies fail validation.

A `potential_candidate_for_further_diligence` conclusion is rejected when the packet is classified as `insufficient_evidence`. Missing venue evidence is disclosed and does not become a claim of Binance tradability. Provider coverage gaps remain visible.

## Scenario and sizing

Scenario calculations require explicit hypothetical prices, assumptions, invalidation, horizon, and timestamp. Position sizing requires explicit capital, risk budget, allocation cap, entry/invalidation prices, and price-basis rationale. The sizing model is cash-only and unlevered. Neither calculator generates probabilities, expected returns, or orders.

## Output and security

The PDF is written only to `reports/opportunities`, checked for a valid PDF signature, and returned with a SHA-256 digest. The job requires the same explicit validation and approval steps as the existing market-report jobs. No caller-controlled shell, code, or output path is accepted.

## Current audit boundary

The opportunity PDF is structurally inspected by PyMuPDF when generated. Full integration of opportunity manifests and independent recalculation into the `skills.audit` job remains a separate acceptance item; until that is implemented, the market audit must not be described as independently auditing opportunity-report source facts or scenario arithmetic.
