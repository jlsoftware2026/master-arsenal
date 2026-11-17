# Local Engine investment opportunity report workflow

## Job contract

The versioned Local Engine protocol now supports `investment.opportunity_report`. It uses the existing validate-and-approve lifecycle and has a fixed PDF output directory: `reports/opportunities`. The caller cannot choose an arbitrary output path.

The job is read-only. It can call only the configured public source adapters and does not access private exchange accounts, store API keys, or place orders.

## Parameters

- `instrument_candidate` (required): asset-class-specific identity input for listed equity, tokenized equity, or crypto.
- `venue_evidence` (optional): caller-supplied timestamped exact-product evidence.
- `binance_spot_check` (optional boolean): when true, queries public Binance Spot `exchangeInfo` for the exact candidate base/quote product. It is mutually exclusive with `venue_evidence`, restricted to crypto/tokenized-equity product identity, and does not access private accounts or place orders. Listed shares are not treated as Binance Spot products.
- `research_facts` (optional): caller-supplied source-attributed facts. Each fact must use the exact normalized `instrument_key`.
- `freshness_limits_hours` (optional): explicit per-dimension freshness policy. Missing policies remain `not_assessed`.
- `sec_edgar` (optional): either exact caller-supplied `cik` plus `issuer_name`, or `resolve_ticker: true` for automatic exact SEC ticker/exchange/issuer resolution from a `listed_equity` candidate; optional `period` (`annual` or `quarterly`). Requires `MASTER_ARSENAL_SEC_USER_AGENT`. Tokenized equity requires an explicit CIK.
- `clinical_trials` (optional): up to ten records, each containing exact `nct_id` and documented `attribution_basis`. Restricted to equity candidates.
- `defillama` (optional): exact `protocol_slug` and documented `attribution_basis`. Restricted to crypto candidates.
- `scenario_inputs` (optional): complete inputs for the long-only scenario calculator, including the exact instrument key.
- `position_sizing_inputs` (optional): complete inputs for the cash-only sizing calculator, including the exact instrument key.
- `conclusion` (optional): one of `potential_candidate_for_further_diligence`, `wait_for_confirmation`, `insufficient_evidence`, or `avoid_for_now`. Defaults to `insufficient_evidence`.
- `executive_summary`, `risks`, `thesis_invalidation`, `unresolved_questions`, and `methodology_notes` (optional): report narrative fields.

Unknown top-level parameters are rejected. Source adapters are called only when their explicit configuration is present. The Local Engine never guesses CIK, NCT, protocol slug, issuer ownership, or token value capture. SEC ticker resolution is an explicit opt-in lookup against the official exchange-aware directory and fails closed on ambiguity or issuer-name mismatch.

## Evidence and conclusion gates

When `binance_spot_check` is enabled, the handler first queries exact public Spot product metadata and records `verified`, `unavailable`, or `not_verified` with source/time provenance; a successful result supplies the exact venue identity to the instrument validator. It then collects supplied facts and selected public-provider facts and constructs a single research packet bound to that instrument key. Duplicate fact IDs, mismatched instrument keys, invalid timestamps, invalid provenance, and unsupported freshness policies fail validation.

A `potential_candidate_for_further_diligence` conclusion is rejected when the packet is classified as `insufficient_evidence`. Missing venue evidence is disclosed and does not become a claim of Binance tradability. Provider coverage gaps remain visible.

## Scenario and sizing

Scenario calculations require explicit hypothetical prices, assumptions, invalidation, horizon, and timestamp. Position sizing requires explicit capital, risk budget, allocation cap, entry/invalidation prices, and price-basis rationale. The sizing model is cash-only and unlevered. Neither calculator generates probabilities, expected returns, or orders.

## Output and security

The PDF is written only to `reports/opportunities`, checked for a valid PDF signature, and returned with a SHA-256 digest. The job requires the same explicit validation and approval steps as the existing market-report jobs. No caller-controlled shell, code, or output path is accepted.

## Independent audit integration

Every generated opportunity PDF is accompanied by a JSON evidence manifest under `data/manifests/opportunities`. The manifest stores the normalized report input, research packet, provider statuses, scenario and sizing outputs, the PDF filename, and the PDF SHA-256 digest.

The `skills.audit` job scans opportunity PDFs and manifests and runs `OPPORTUNITY-01`. It verifies the fixed manifest/PDF paths, PDF hash and structural QA, reconstructs the research packet from its facts and freshness policy, and independently recalculates any scenario and cash-only position-size outputs. Missing/orphan manifests or mismatched hashes/calculations are reported as audit findings.

This is an independent arithmetic, provenance-metadata, and artifact-integrity check. It does not independently authenticate source publishers, prove CIK/NCT/protocol attribution, verify the contents of SEC or ClinicalTrials.gov filings, or establish that clinical or financial claims are true. Those remain analyst diligence requirements.


The Binance Spot check proves only that the exact product was present in exchangeInfo with `status=TRADING` and `isSpotTradingAllowed=true` at retrieval time. It does not establish account eligibility, jurisdictional access, liquidity, or investment suitability. For tokenized equity, it verifies the token product only and does not establish rights in the underlying share. See [binance-spot-verification.md](binance-spot-verification.md).
