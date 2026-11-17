# Phase 3 — PDF Report Engine

## Current implementation

Phase 3 now contains the shared PDF foundation and end-to-end acquisition/composition paths for the three market reports, plus an independent artifact-audit PDF.

### Shared PDF infrastructure

- ReportLab provides shared page templates, typography, headers/footers, tables, vector charts, metadata, and atomic file publication.
- `report_engine.charts.MarketChart` renders close-price line charts and base-volume bar charts directly into PDFs. It validates finite values and label/value counts and applies bounded deterministic downsampling.
- `report_engine.qa.inspect_pdf_artifact` independently parses PDFs with PyMuPDF, extracts text, checks page geometry and text bounds, renders every page, and rejects blank/unreadable output.
- Every composer runs independent structural/render QA after writing. If QA fails, the newly generated PDF is removed.
- Automated QA is not human visual sign-off or proof of analytical correctness.

### Historical indicator warm-up

- Intraday and completed-session acquisition fetch 250 preceding candles separately from the report window.
- EMA 20/50/200, RSI 14, MACD, ATR 14, Bollinger 20, and volume SMA 20 are calculated from lookback plus report candles.
- The lookback is excluded from session/intraday candle counts, price-performance calculations, and charts.
- The preceding history must be complete, correctly aligned, validated, and exactly the requested length. Missing or malformed history fails closed.

### Dominican local-calendar opening and closing reports

- Opening acquisition uses the previous completed `America/Santo_Domingo` local calendar day relative to the requested local report date. Closing acquisition uses the requested local calendar day and supports an exact partial-day cutoff before local midnight.
- Local midnight boundaries and cutoffs are converted to UTC only at the Binance request boundary; completeness is checked against Binance server time. Unfinished final candles are excluded.
- Historical closing dates without an explicit cutoff use the completed local day. Current-day closing reports default to execution-time Dominican local time.
- Opening and closing reports share the same evidence contract and renderer but have distinct report titles, dates, filenames, and perspectives. Opening filenames use the local request date; the Binance evidence inside the report refers to the previous local date.
- The current scenario framework uses prior/session range high and low as conditional breakout and invalidation references. It does not invent targets or probabilities.
- Output:
  - `apertura-mercado_YYYY-MM-DD.pdf` (local request date; Binance evidence is previous local date)
  - `cierre-mercado_YYYY-MM-DD.pdf` (local report date)

### Intraday snapshot

- The report window is local midnight through the exact `America/Santo_Domingo` cutoff. If no cutoff is supplied, execution-time local time is resolved at runtime.
- Local boundaries are converted to UTC for Binance requests. The exact cutoff is retained, and an unfinished final candle is excluded rather than rounded into the report.
- All three operational reports show Dominican local and UTC timestamps. Opening/closing PDFs include the 9:30 a.m./4:00 p.m. ET scheduled reference converted with `America/New_York`; intraday PDFs show the exact cutoff and generation times in ET. These conversions are DST-aware but do not certify whether an exchange session is open on a weekend or holiday.
- BTCUSDT and ETHUSDT are mandatory.
- The exact report-window candle count and each open/close boundary are validated; no interpolation or synthetic candles are used. Report intervals are bounded to one minute or higher to avoid unbounded per-second report artifacts.
- The output includes a seven-point Spanish executive summary, source-attributed market context, technical indicator tables, session-only charts, conditional range scenarios, risk notes, and provenance when evidence is available. With `market=usdm`, it also attempts premium index, funding history, open interest, global long/short account ratio, basis, mark-price klines, and index-price klines; each unavailable endpoint is disclosed rather than silently omitted.
- Output: `snapshot-mercado_YYYY-MM-DD_HH-mm.pdf`, based on Dominican local report date and cutoff.

### Macro and news context

The standard-library RSS collector uses configured public feeds for:
- Digital-asset news: CoinDesk, Cointelegraph, and The Block.
- Macroeconomic/central-bank releases: Federal Reserve, Bureau of Labor Statistics, and European Central Bank.

For USD-M reports, optional derivatives evidence includes premium index, funding history, current/historical open interest, global long/short account ratio, basis, and mark/index-price klines. Endpoint errors are recorded as unavailable; no restriction is bypassed.

Only items with publisher timestamps inside the report's UTC window are included. Each displayed item carries publisher, publication timestamp, URL, and a relevance disclaimer. Retrieval time and feed status are retained. Failed feeds are reported as unavailable; an empty feed result is not presented as proof that no relevant event occurred. Headlines are candidate context only and are not treated as proof of price causation. RSS coverage is not exhaustive.

### Independent skills audit

- `report_engine.audit.build_skills_audit_pdf` creates `auditoria-skills-binance_YYYY-MM-DD.pdf`.
- The Local Engine audit handler scans the fixed opening, closing, and intraday report directories, computes SHA-256 digests, and independently parses/renders every discovered PDF.
- Missing artifacts and QA failures become explicit findings. No artifacts means insufficient evidence, not a pass.
- The audit PDF now records a source-skill desk-check matrix, Crítico/Alto/Medio/Bajo severity, Spanish verdict (No aprobado / Aprobado con reservas / Aprobado), and a version/change-history section. XNYS calendar/session-state checks are implemented and independently reconciled in CI; full portfolio accounting, U.S. breadth/stock-level price coverage, and source-package integrity cases remain unresolved. A privacy-conscious local parser imports Binance transaction-history CSV events, hashes and rechecks files, suppresses overlapping duplicates, and aggregates balance changes by event/asset. The same-date range-scenario scorecard is implemented and CI-verified.
- Every Local Engine market report also stores an internal `ma.report-evidence/v2` JSON manifest under `data/manifests`. This is internal audit evidence, not an alternate user-facing report format. It contains raw report-window candles and separate warm-up candles, bound to the PDF by SHA-256.
- The audit checks artifact structure/readability, expected filename prefixes, mandatory BTC/ETH and required sections; verifies manifest/PDF digests; revalidates raw candle windows; independently recalculates technical indicators; and compares overlapping OHLCV evidence across reports.
- The audit does not verify the factual accuracy of every news claim, certify scenario quality, or prove parity with the original Claude skill source files. The local audit queries GitHub Actions read-only for the exact local Git HEAD when repository origin, commit SHA, and network access are available; it requires all four Ubuntu/Windows × Python 3.11/3.12 jobs to succeed. The audit running inside GitHub Actions does not query or self-certify its own run. Live provider availability remains separate from offline CI.

## Local Engine job integration

All report jobs retain the existing sequence: submit → validate → explicit approval → claim → execute. No report handler starts before approval. Outputs are fixed by job type:

| Job type | Parameters | Output directory |
|---|---|---|
| `market.opening_report` | optional `session_date_local`, `interval`, `market` | `reports/opening` |
| `market.closing_report` | optional `session_date_local`, `cutoff_local`, `interval`, `market` | `reports/closing` |
| `market.intraday_snapshot` | optional `cutoff_local` (or legacy `cutoff_utc`), `interval`, `market`; omitted cutoff resolves execution time | `reports/intraday` |
| `skills.audit` | no caller-supplied parameters | `reports/audit` |

All four outputs are PDF-only. Job-supplied paths, shell commands, code, or arbitrary endpoints are not accepted. Binance data acquisition remains public and read-only; there are no API credentials, private account endpoints, or trading operations.

### CLI examples

Create a job template:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL new-job market.opening_report --output opening-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL new-job market.closing_report --output closing-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL new-job market.intraday_snapshot --output intraday-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL new-job skills.audit --output audit-job.json
```

For opening, `parameters.session_date_local` is the request date; the Binance reference day is the previous Dominican local date. For closing, it is the report date; a current-day cutoff may be supplied as ISO-8601 `parameters.cutoff_local`. Historical dates without a cutoff use the completed local day. The legacy `session_date_utc` parameter remains accepted as a compatibility alias.

For intraday, `parameters.cutoff_local` is an ISO-8601 local datetime. It may be omitted to resolve current Dominican local time. The legacy `cutoff_utc` parameter remains accepted, but both cutoff fields cannot be supplied together. Submit, validate, approve, and execute each job:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL submit opening-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL validate JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL approve JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL run JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL status JOB_UUID
```

## Verification and limitations

- CI is fixture-driven and covers Ubuntu/Windows with Python 3.11/3.12.
- Offline tests cover candle completeness, indicator warm-up, Dominican local-day boundaries, exact and partial cutoffs, exclusion of unfinished candles, PDF generation, charts, source-context parsing, audit status, and Local Engine approval gates.
- Live Binance and RSS feed availability is not certified by offline CI. Binance geographic restrictions are not bypassed.
- The audit does not currently perform full semantic market-analysis recalculation.
- The four original Claude `.skill` packages were supplied on 2026-11-16 and are the behavioral source of truth. Reconciliation is recorded in `docs/original-claude-skills-reconciliation.md`.
- Full U.S. market breadth/stock-level leader coverage, private Binance equity/position/flow-adjusted return analytics, and complete original audit desk-check parity are not yet implemented. Supported transaction-history CSV activity can be imported from the fixed local data/account_exports directory; no private API connection is used. Best-effort Yahoo Finance quote snapshots for major indices, VIX, futures, rates, DXY, commodities, and sector ETFs are integrated with source URLs and observation timestamps; they are not an execution feed and may be delayed or incomplete. Same-date opening-to-closing range-scenario scorecard linkage is implemented when an integrity-checked opening manifest exists. The XNYS calendar is integrated for holidays, early closes, DST, and session classification. Yahoo Finance quote snapshots are best-effort and source-attributed; breadth/stock-level leader coverage remains unavailable. PDFs must disclose these limitations; public market candles are never represented as private account data.
- No OpenJarvis integration is included in this phase.

## Verification commands

```bash
python -m pip install -e .
python -m unittest discover -s binance_data_engine/tests -v
python -m unittest discover -s local_engine/tests -p 'test_local_engine.py' -v
python -m unittest discover -s report_engine/tests -v
```


## Original-skill parity status
The three original operational skills specify Spanish-language PDF output. The opening, closing, and intraday composers and audit PDF are localized. Independent marker checks cover all three operational report types; the final code-head CI result remains the release verification gate. The exact original intraday filename is `snapshot-mercado_YYYY-MM-DD_HH-mm.pdf`.


## Final distribution requirement
The mandatory single-download executable JAR requirement is recorded in `docs/distribution-requirements.md`. It is a release gate outside this PDF-engine phase; no bootstrapper, Python provisioning, packaging, signing, or CI/CD changes are implemented or authorized by this documentation entry.


## Cross-platform verification
The latest full four-job matrix passed on commit `b47c3a2c508c691933c97128944f28b26c1d6d64` in GitHub Actions run `44170918819`: Ubuntu/Windows × Python 3.11/3.12. Each environment passed 27 Binance Data Engine tests, 37 Local Engine tests, and 220 PDF Report Engine tests (284 tests per environment). This includes the SEC exchange-aware ticker-to-CIK resolver, fail-closed identity matching, approval-gated opportunity workflow integration, opportunity-manifest issuer-mapping consistency audit, same-period financial-ratio calculations, cross-source conflict detection and PDF disclosure, and all existing report, market-data, calendar, privacy, and arithmetic tests. Live SEC, Binance, RSS, ClinicalTrials.gov, DeFiLlama, and Yahoo availability is not certified by offline CI. Any later code change must rerun the full matrix.

## Pre-investment research scope (owner-approved direction)

MASTER ARSENAL must support research before the first transaction. Opportunity research is independent of personal portfolio accounting: a user may screen equities and cryptocurrencies, review sector/fundamental evidence, compare market conditions, and calculate hypothetical scenarios without a Binance transaction-history CSV. A declared pre-investment state must not be confused with an active account whose exports are missing. Missing exports do not prove zero balances or zero holdings; personal account metrics remain unavailable/not supplied unless explicitly configured. The detailed research contract and acceptance criteria are in [investment-opportunity-analysis.md](investment-opportunity-analysis.md).

The next development work is instrument identity/venue verification, source-attributed equity and crypto research inputs, reproducible bull/base/bear calculations, hypothetical risk sizing, and integration into the four PDF skills and independent audit. Listed shares, tokenized equity products, and cryptocurrencies must be treated as distinct instruments. No private account access, order placement, or automated trading is in scope.


## Instrument identity and venue verification

A deterministic candidate identity contract is implemented in `report_engine/instruments.py` for listed equities, tokenized equities, and cryptocurrencies. It validates asset-class-specific identity fields and treats tokenized equity as distinct from its underlying listed share. Exact venue evidence must match venue name, product ID, and market type, carry an HTTPS source URL and timezone-aware observation timestamp, and be no older than the configured freshness window. Missing, stale, future-dated, or mismatched evidence remains `not_verified`. The identity validator is deliberately network-free, while the optional `report_engine/binance_venue.py` adapter uses public Binance Spot `exchangeInfo` to verify exact crypto products. It requires exact base/quote matches, `TRADING` status, and `isSpotTradingAllowed=true`; API failure remains `not_verified`. Listed shares are not treated as Spot products; tokenized equity remains not verified by ticker-only matching and requires separate contract/issuer/rights evidence. Contract: [instrument-identity-contract.md](instrument-identity-contract.md); adapter limits: [binance-spot-verification.md](binance-spot-verification.md). Offline tests cover the adapter and Local Engine integration.


## Source-attributed investment research evidence

A deterministic evidence record and research packet builder now lives in `report_engine/research.py`. It requires an exact instrument key, typed research dimension, scalar value/unit, evidence classification, source metadata (or explicit assumption note), and timezone-aware observation/retrieval timestamps. External sources require HTTPS; a `verified_source` classification requires a precise source reference. Freshness is only assessed against an explicit per-dimension age policy. Stale, future-dated, disputed, or unverified facts are surfaced as insufficient evidence; estimated values remain labeled. This layer validates metadata and provenance only—it does not fetch or authenticate source content. See [research-evidence-contract.md](research-evidence-contract.md). Read-only provider retrieval is implemented for SEC Company Facts, ClinicalTrials.gov, and DeFiLlama, and same-period issuer ratios are calculated with independent audit. Basic same-label/same-unit/same-period conflict detection is implemented in the research packet; semantic source reconciliation and source-content authentication remain outstanding. Broader sector-specific evidence coverage and issuer/trial/protocol attribution verification also remain outstanding.


## SEC EDGAR fundamental-data adapter

A read-only SEC EDGAR Company Facts adapter is implemented in `report_engine/sec_edgar.py`. It uses the public Company Facts JSON endpoint, requires an explicitly configured descriptive SEC User-Agent, and validates that the returned CIK matches either the caller-supplied CIK or the exact SEC directory mapping recorded for the candidate. It extracts a bounded set of revenue, operating income, net income, operating cash flow, total assets, and cash facts with annual/quarterly duration filters and point-in-time handling. Each fact carries filing form, XBRL concept, accession, filing date, period end, SEC source URL, and retrieval time. Missing concepts remain missing, and alternative tags are never summed. Automatic listed-equity ticker-to-CIK resolution is now implemented through the SEC exchange-aware directory with exact ticker/exchange/issuer matching and fail-closed ambiguity handling. Tokenized-equity candidates still require an explicit underlying-issuer CIK. Total-debt aggregation, valuation multiples, narrative filing analysis, persistent mapping cache, and live endpoint certification remain outstanding. Details: [sec-edgar-adapter.md](sec-edgar-adapter.md). Offline tests use injected fixtures and do not certify SEC live availability.


## ClinicalTrials.gov biotech evidence adapter

A read-only ClinicalTrials.gov API v2 adapter is implemented in `report_engine/clinical_trials.py` for exact NCT record retrieval. It captures trial status, phase, study type, lead sponsor, enrollment and its estimated/actual label, primary completion date, primary outcomes, interventions, and whether a results section is present. It preserves the NCT record's update date, retrieval time, and field-level provenance. Issuer-to-trial attribution must be supplied explicitly by the caller and is not independently verified; sponsor identity alone is not ownership proof. The registry is not evidence of efficacy or regulatory approval, and the NLM does not verify scientific validity/relevance of submitted information. See [clinicaltrials-adapter.md](clinicaltrials-adapter.md). Offline fixture tests do not certify live API availability or clinical conclusions.


## DeFiLlama protocol metrics adapter

A read-only DeFiLlama public API adapter is implemented in `report_engine/defillama.py` for caller-identified protocol slugs. It extracts the latest available TVL, daily fees, protocol revenue, and token-holder revenue observations, preserving exact endpoint/series provenance and UTC observation/retrieval timestamps. Fees, protocol revenue, and token-holder revenue are kept distinct; missing metrics are not zero-filled. The caller must supply an explicit protocol-to-instrument attribution basis, which is not independently verified. This adapter does not establish token-holder value capture, token supply/unlocks, security, governance, or regulatory status. Details: [defillama-adapter.md](defillama-adapter.md). Offline fixture tests do not certify live API availability.


## Scenario calculation and hypothetical risk sizing

Two deterministic calculators now exist: `report_engine/scenarios.py` computes long-only bull/base/bear price returns, downside to invalidation, and bull/base reward-to-risk from explicit hypothetical prices and rationales; `report_engine/position_sizing.py` computes a cash-only hypothetical maximum size under explicit capital, risk-budget, allocation, fee, and slippage assumptions. Neither generates probabilities, expected returns, price targets, or trading instructions; neither submits orders. Details and limitations: [scenario-and-risk-engine.md](scenario-and-risk-engine.md). Offline tests are added for arithmetic and validation.


## Standalone opportunity PDF and Local Engine job

A new approved job type `investment.opportunity_report` is registered in the Local Engine protocol with a fixed `reports/opportunities` PDF output. The handler normalizes exact instrument identity, optionally calls explicitly configured SEC/ClinicalTrials.gov/DeFiLlama public adapters, combines facts into one instrument-bound research packet, optionally calculates explicit-assumption scenarios and cash-only sizing, and produces a standalone opportunity PDF. Empty/insufficient evidence cannot support a potential-candidate conclusion. The job remains read-only and approval-gated. Structural PDF QA runs at generation; independent opportunity-manifest and scenario/source audit integration remains outstanding. See [opportunity-report-workflow.md](opportunity-report-workflow.md).

## Opportunity evidence manifest and independent audit

Opportunity reports receive a JSON sidecar under `data/manifests/opportunities`, bound to the PDF by SHA-256. The `skills.audit` job scans opportunity PDFs and manifests under the fixed workspace paths, checks PDF structure/hash, reconstructs the normalized research packet (including same-label source-conflict detection), checks recorded SEC ticker-mapping and Binance Spot product-evidence consistency, and independently recalculates financial ratios, scenarios, and cash-only position sizing. It records an `OPPORTUNITY-01` desk check and renders opportunity audit results in the audit PDF. This verifies artifact integrity, evidence metadata consistency, and arithmetic—not the truth of source contents or the correctness of issuer/trial/protocol attribution.


## Derived issuer financial ratios

The SEC adapter now extracts additional gross-profit, capital-expenditure, current-asset/current-liability, and stockholders' equity facts. `report_engine/fundamentals.py` calculates same-period margins, free cash flow, liquidity ratios, and period-end ROA/ROE proxies only when inputs share period end and currency. It preserves source fact IDs and formulas, flags missing/ambiguous inputs, and does not calculate growth rates, total debt, valuation multiples, or peer comparisons. Opportunity PDFs display these ratios, and opportunity manifests allow `skills.audit` to independently recalculate them. See [sec-edgar-adapter.md](sec-edgar-adapter.md).


## Automatic SEC issuer resolution

The SEC Company Facts adapter now supports opt-in automatic CIK resolution for listed equities using the SEC's official exchange-aware ticker directory. The resolver requires exact ticker, exchange, and issuer-name agreement; ambiguous, missing, and mismatched results fail closed. The opportunity workflow records lookup provenance and then validates the Company Facts response against the resolved CIK. Tokenized equity remains separate and requires a caller-supplied CIK for the underlying issuer. The official SEC directory may be incomplete or inaccurate by the SEC's own notice, so the mapping is a research convenience rather than independent legal/security verification. Tests cover exact matches, exchange mismatches, issuer-name mismatches, duplicate records, malformed directory data, and Local Engine integration.


The SEC directory integration is now also checked by the opportunity manifest audit for internal consistency: the recorded ticker, exchange, normalized issuer name, directory URL, retrieval time, resolved CIK, and SEC fact identifiers must agree with the report instrument. This check does not independently re-query or authenticate the SEC directory. Manual CIK inputs are explicitly labeled as not independently verified.


## Cross-source research conflict handling

The research packet builder now detects differing external values when the instrument, dimension, label, unit, and exact observation timestamp match. It normalizes numeric formatting, excludes explicit analyst/user assumptions, records each conflicting value and its source/fact provenance, and marks the packet insufficient until the discrepancy is reconciled. It never chooses a preferred source or averages conflicting values. Clinical trial fact labels are scoped to the exact NCT record to avoid comparing separate studies as one observation. The opportunity PDF displays unresolved conflicts, and the existing independent packet-reconstruction audit rechecks the conflict set. This is deterministic metadata/value comparison, not semantic equivalence analysis or source-content authentication.


## Binance Spot product discovery

The approval-gated opportunity job now supports opt-in `binance_spot_check: true`. It uses the existing public Binance client to retrieve Spot exchange metadata, matches exact base asset, quote asset, and product symbol, and only reports `verified` when the product is `TRADING` and Spot trading is explicitly allowed. Missing products or disabled products are reported as unavailable; API failures, malformed data, or ambiguous results remain not verified. Listed equity is never treated as a Binance Spot share, and tokenized equity is not automatically verified from a ticker match. No private API, account data, or order placement is used.


The opportunity manifest audit now also checks the recorded Binance Spot product evidence against the normalized crypto instrument, exact base/quote product ID, trading status, Spot permission, source endpoint, and observation timestamp. Caller-supplied venue evidence is labeled as not independently re-queried. This audit verifies internal consistency only; it does not certify account eligibility or live exchange availability after report generation.

## Exact-commit GitHub Actions audit evidence

`report_engine/github_ci.py` resolves the local checkout's HEAD SHA and GitHub origin without invoking a shell, then queries the public GitHub Actions API read-only. `CI-01` passes only when a pull-request run for the exact SHA is completed successfully and all four required jobs are completed with a successful conclusion: Ubuntu/Windows × Python 3.11/3.12. A different SHA, missing matrix job, failed/cancelled job, missing Git metadata, API error, or in-progress run cannot pass. The audit process skips querying GitHub Actions when it is itself running inside GitHub Actions, avoiding self-certification and network-dependent unit tests. This check verifies CI execution only; it does not verify live SEC, Binance, ClinicalTrials.gov, DeFiLlama, RSS, or Yahoo data availability, nor the factual correctness of provider content.


## Crypto tokenomics and opportunity-report integration

The standalone opportunity composer accepts optional `tokenomics` and `tokenomics_inputs` for crypto instruments only. It rejects tokenomics data on listed or tokenized equities, requires schema `ma.tokenomics/v1` and matching instrument identity, and recalculates the result from the explicit inputs before PDF creation. The PDF reports circulating/total/max supply, same-UTC-date market-cap/FDV arithmetic, known unlocks over 30/90/365 days, and observed holder concentration with declared coverage. The opportunity manifest stores the inputs and the independent audit recalculates the result. Missing schedules remain not supplied; missing holder coverage remains not assessed. This is not a live discovery adapter and does not verify beneficial ownership, protocol security, governance, or regulatory status. The tokenomics unit and opportunity integration tests are part of the current cross-platform CI gate.
