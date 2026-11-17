---
name: binance-revision-skills
description: 'Audita, valida y mejora las tres Skills de análisis de mercado de Binance: Apertura de mercado, Cierre de mercado y Momento específico del mercado. Activar cuando el usuario solicite revisar, corregir, actualizar, comparar, probar o mantener cualquiera de esas Skills o el conjunto completo.'
version: 1.4.0
last_reviewed: 2026-11-17
---

# binance-revision-skills

## Purpose
Independently audit the other three market-report workflows, their source data, and generated PDF artifacts.

## Local Engine workflow
- Job type: `skills.audit`
- Fixed output directory: `reports/audit`
- Filename: `auditoria-skills-binance_YYYY-MM-DD.pdf`
- No caller-supplied parameters are accepted.
- The job must pass submit → validate → explicit approval → execute.

## Required audit scope
1. **Temporal correctness:** date, timezone, session boundaries, intraday cutoff, candle close semantics.
2. **Data integrity:** Binance source provenance, retrieval timestamps, completeness, gaps, duplicates, stale responses, pagination, and symbol/interval correctness.
3. **Methodology:** indicator calculations and warm-up requirements; assumptions; derivatives, macro/news attribution; scenario logic; reproducibility.
4. **Cross-report consistency:** comparable values and claims agree when reporting windows overlap; explain legitimate differences.
5. **Testing:** distinguish offline unit tests from live API/feed tests; record exact commands, results, and limitations.
6. **PDF quality:** required sections, readable charts/tables, metadata, filenames, page integrity, and evidence traceability.
7. **Findings:** classify severity, cite inspectable evidence, explain impact, and recommend corrective actions.

## Current automated checks
The Local Engine scans the fixed opening, closing, and intraday report folders, hashes discovered PDFs, independently parses each artifact, extracts text, checks text bounds, raster-renders pages, validates filename prefixes, and checks mandatory BTC/ETH, scenario, macro/news, provenance, and feed-status sections. It also reads internal source-linked evidence manifests, verifies the PDF digest, revalidates raw candle windows, recalculates technical indicators independently, and compares overlapping OHLCV candles across reports. Missing manifests, missing artifacts, failed checks, or absent CI evidence remain explicit findings. An empty artifact set is insufficient evidence, never a pass.

## Original-skill desk-check matrix

The audit PDF records each case with status, severity, evidence, and corrective action:
1. Dominican local midnight, previous-local-day opening, exact partial closing cutoff, and intraday cutoff default.
2. U.S. weekends and exchange holidays; use the last completed cash session without changing the Binance local-day reference.
3. U.S. daylight-saving transitions and premarket/regular/postmarket session classification.
4. Missing or unsupported Binance transaction-history CSV: disclose account activity as unavailable/partial and never substitute public market candles for account data. Supported CSV events are aggregated by event type and asset only; do not infer equity, unrealized PnL, or flow-adjusted returns.
5. External deposits and withdrawals: do not count them as trading profit or loss.
6. Missing historical account balances: do not claim portfolio return where opening equity cannot be reconstructed.
7. Same-date opening forecast versus closing outcome scorecard, when the opening forecast exists.
8. Raw candle integrity, report/evidence digests, package integrity, and version/change history.
9. Offline CI versus live API/feed verification; report exact evidence and limitations.
10. PDF section, filename, chart, table, page, and provenance checks.

La severidad se clasifica como Crítico, Alto, Medio o Bajo. The verdict is No aprobado when unresolved Critical/High findings remain; Aprobado con reservas when only Medium findings remain; and Aprobado only when no unresolved findings remain. Unavailable/not implemented checks must remain visible and must not be counted as passed.

## Independence and integrity
Do not certify a skill based solely on its own assertions. The current automated audit independently recalculates stored indicators from retained raw candles and compares overlapping report candles. It does not yet verify the factual accuracy of every news claim, certify scenario quality, or prove parity with the original Claude skill source. CI and live endpoint results must be attached separately; the local audit does not fetch or trust external CI status. Mark those areas NOT VERIFIED unless separate evidence is supplied. The audit itself must be a PDF; if PDF generation fails, report the blocker and do not substitute another format.

## Pre-investment and opportunity-analysis audit

The audit must verify that operational reports and asset research remain usable when the user has not made any transactions. Missing transaction exports must not block market/asset analysis and must not be interpreted as proof of a zero account balance. A user-declared pre-investment state should label personal performance as not applicable and balances/positions as not supplied.

For each analyzed candidate, verify instrument identity and venue, and distinguish listed equity, tokenized equity, and cryptocurrency. Check that fundamental/sector evidence, valuation or tokenomics, market data, scenario assumptions, risk disclosures, source timestamps, and invalidation conditions are present. Flag unsupported target prices, fabricated probabilities, untraceable claims, and any recommendation that confuses observed data with forecasts.

## Fundamental and clinical-evidence adapter audit

When a report contains SEC or ClinicalTrials.gov evidence, independently check:

1. Exact instrument identity and CIK/NCT-to-instrument mapping. For automatic SEC resolution, inspect the recorded exact ticker, exchange, issuer-name match, mapping source URL, retrieval timestamp, and resolved CIK; reject ambiguous, missing, or mismatched mappings. A ticker match or lead-sponsor match alone is not enough.
2. SEC response CIK matches the requested CIK; each financial fact retains its XBRL concept, form, accession, period end, filing date, source URL, and retrieval time.
3. Annual and quarterly duration filters are not mixing year-to-date values with quarter-only values. Instantaneous balance-sheet facts are kept distinct from duration metrics.
4. Missing SEC concepts are reported as missing, never as zero. Alternative XBRL concepts are not added together without a documented reconciliation.
5. Derived gross/operating/net/cash-flow margins, free cash flow, current ratio, cash/current-liabilities, and period-end ROA/ROE use same-period, same-currency facts; formulas and source fact IDs must be present. Missing or mismatched inputs are not filled.
6. ClinicalTrials.gov NCT identifier matches the requested record; last-update and first-posted dates are retained; estimated enrollment/completion values remain labeled.
6. Trial-to-issuer attribution has a primary-source rationale. Registry sponsorship alone does not establish ownership, licensing, or economic exposure.
7. A registered trial, phase, recruitment status, or results-section presence is never treated as proof of efficacy, safety, regulatory approval, or positive results.
8. The `skills.audit` opportunity manifest check independently recalculates derived financial ratios from the stored source facts and flags mismatches.
9. Offline fixture tests are distinguished from live provider availability and independent review of filing/registry content.

Mark unavailable, ambiguous, or issuer-mismatched CIK/NCT mappings, stale records, missing metrics, unsupported clinical interpretations, and absent source evidence as not verified. Also inspect research-packet conflicts: same-label/same-unit/same-period sourced values that disagree must remain unresolved, be traceable to their fact IDs and sources, and block a supported-candidate conclusion until reconciled. For Binance Spot evidence, verify exact product/base/quote identity, `TRADING` status, `isSpotTradingAllowed=true`, source URL, and observation timestamp; never treat a listed share as a Spot product or a token listing as proof of underlying-share rights. The audit checks recorded consistency, not account eligibility or live re-query. The packet audit verifies deterministic conflict reconstruction, not source truth or semantic equivalence. The opportunity audit may verify recorded mapping consistency but does not independently authenticate the SEC directory or legal issuer/security identity. SEC and ClinicalTrials.gov adapters validate and preserve data provenance; they do not replace analyst review or a full financial/clinical diligence process.



## Crypto protocol evidence audit

For DeFiLlama evidence, independently check:

1. Exact protocol slug and caller-supplied protocol-to-token/issuer attribution basis.
2. TVL, daily fees, protocol revenue, and token-holder revenue are separate fields and retain their own endpoint, source reference, observation timestamp, and retrieval timestamp.
3. TVL is not represented as revenue, token market capitalization, or token-holder value capture.
4. Missing series remain missing, not zero. A missing token-holder revenue series is not evidence that holders receive no value.
5. The report does not imply that token supply, unlocks, holder concentration, security, exploit history, governance, or regulatory risks were assessed by the DeFiLlama adapter.
6. Aggregated protocol metrics are checked against provider methodology and, where material, primary protocol disclosures.

Mark unverified protocol/token attribution, missing source coverage, stale observations, or unsupported token-economics claims as not verified.

## Scenario and position-sizing audit

For scenario or sizing outputs, independently verify:

1. The exact instrument key, quote currency, analysis horizon, and as-of timestamp.
2. Bull/base/bear prices and their written rationales are explicit caller-supplied assumptions; prices obey bull ≥ base ≥ bear.
3. Invalidation is below the reference entry for a long scenario and its rationale is present.
4. Scenario return, downside, and reward-to-risk arithmetic can be recalculated from displayed inputs.
5. Probabilities and expected returns are absent unless a separately specified, evidence-backed methodology is implemented and approved.
6. Position sizing uses explicit available capital, risk budget, maximum allocation, entry/invalidation prices, and fee/slippage assumptions; cash-only units/notional do not exceed either cap.
7. No leverage, actual holdings, order submission, guaranteed stop execution, or guaranteed maximum loss is implied.

Mark missing assumptions, inconsistent arithmetic, hidden defaults, or unsupported forecasts as findings.


## Opportunity report manifest and independent audit

The Local Engine `skills.audit` job now scans `reports/opportunities` and `data/manifests/opportunities` and emits the `OPPORTUNITY-01` desk check. It verifies that each opportunity PDF has a fixed-path JSON manifest, checks the SHA-256 link and PDF structural QA, rebuilds the research packet from stored facts and freshness rules, and independently recalculates bull/base/bear scenarios and cash-only position sizing.

Treat a missing/orphan manifest, hash mismatch, packet mismatch, or arithmetic mismatch as an audit finding. Do not overstate the result: this is an artifact-integrity, evidence-metadata, and calculation audit. It does not authenticate publishers, prove CIK/NCT/protocol mapping, independently verify issuer ownership or token rights, or validate the truth/scientific merit of source claims.


## Status
Adapted against the user-supplied original Claude audit skill. The PDF records a desk-check matrix, severity levels, Spanish verdict, and change-history section. XNYS holiday/session-state classification is integrated and independently recalculated by the audit. The audit now validates Yahoo quote source URLs, timestamps not later than the report cutoff, and explicit unavailable-symbol lists. Overall U.S. breadth/stock-level leader coverage and full private-account portfolio reconciliation remain incomplete; transaction-history CSV activity can be imported with file-hash verification. Same-date opening-to-closing range-scenario reconciliation is implemented when a valid opening manifest exists; the audit must verify its evidence. Repository CI passed in GitHub Actions run 43925472913; the local audit still requires CI evidence to be attached because it does not query GitHub Actions. The uploaded original archives and extracted SKILL.md hashes were independently rechecked against the manifest during this development session. The ZIP payloads are not embedded in the repository, so a deployed runtime must still report archive integrity as NOT VERIFIED. The audit must not certify full source-skill parity.

## Version history
- 1.4.0 — 2026-11-17: Added exact Binance Spot product evidence checks and audit disclosures.
- 1.3.0 — 2026-11-17: Added unresolved cross-source conflict detection and independent packet reconstruction checks.
- 1.2.0 — 2026-11-17: Added opt-in SEC ticker-to-CIK resolution with exact exchange/issuer matching and fail-closed ambiguity handling.
- 1.1.0 — 2026-11-17: Added same-period SEC-derived financial ratios and independent ratio recalculation in opportunity reports.
- 1.0.0 — 2026-11-17: Added standalone opportunity PDF workflow and SHA-256 evidence-manifest audit controls.
- 0.9.0 — 2026-11-17: Added explicit-assumption scenario and cash-only hypothetical position-risk calculation controls.
- 0.1.0 — 2026-11-16: Initial ChatGPT/MASTER ARSENAL adaptation; preserves the original skill identity and documents the Local Engine/PDF workflow and current implementation gaps.

- 0.2.0 — 2026-11-16: Reconciled activation phrases, Dominican local-day semantics, PDF-only delivery, explicit limitations, and source-derived report requirements. Outstanding parity gaps remain disclosed.

- 0.3.0 — 2026-11-16: Localized report headings, tables, scenario narratives, disclaimers, and audit output into Spanish; added independent language-marker QA.
- 0.5.0 — 2026-11-16: Added XNYS calendar desk-check reconciliation, including holidays, early closes, DST, and session-state classification; corrected source instruction typos.
- 0.6.0 — 2026-11-16: Added source/cutoff provenance checks for Yahoo Finance market quote evidence.
- 0.7.0 — 2026-11-16: Added SHA-256 and schema checks for local Binance transaction-history CSV imports; portfolio equity and flow-adjusted returns remain outside supported scope.
