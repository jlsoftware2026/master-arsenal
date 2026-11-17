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
- The audit does not verify the factual accuracy of every news claim, certify scenario quality, or prove parity with the original Claude skill source files. CI/live endpoint evidence must be attached separately; the local audit does not query GitHub Actions.

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
The full four-job matrix passed on commit `09d975364b5102c998068db17d6691b59603d09b` in GitHub Actions run `43948707494`: Ubuntu/Windows × Python 3.11/3.12. Each job passed 27 Binance Data Engine tests, 29 Local Engine tests, and 89 PDF Report Engine tests (145 tests per environment). The PDF suite covers Spanish content, partial-close scorecard behavior, ET/DST conversion, Yahoo quote cutoff/provenance, Binance transaction-history CSV parsing/privacy/deduplication, and evidence-manifest binding. The Local Engine integration test generates all three operational PDFs, imports local account activity, independently re-parses and re-hashes the CSV exports, detects post-report tampering, and audits the three report manifests. XNYS holiday/session evidence, quote provenance, and same-date scorecard linkage are included in this passing matrix. Live Binance/RSS/Yahoo availability is not certified by offline CI. Any later code change must rerun the full matrix.


## Pre-investment research scope (owner-approved direction)

MASTER ARSENAL must support research before the first transaction. Opportunity research is independent of personal portfolio accounting: a user may screen equities and cryptocurrencies, review sector/fundamental evidence, compare market conditions, and calculate hypothetical scenarios without a Binance transaction-history CSV. A declared pre-investment state must not be confused with an active account whose exports are missing. Missing exports do not prove zero balances or zero holdings; personal account metrics remain unavailable/not supplied unless explicitly configured. The detailed research contract and acceptance criteria are in [investment-opportunity-analysis.md](investment-opportunity-analysis.md).

The next development work is instrument identity/venue verification, source-attributed equity and crypto research inputs, reproducible bull/base/bear calculations, hypothetical risk sizing, and integration into the four PDF skills and independent audit. Listed shares, tokenized equity products, and cryptocurrencies must be treated as distinct instruments. No private account access, order placement, or automated trading is in scope.


## Instrument identity and venue verification

A deterministic candidate identity contract is implemented in `report_engine/instruments.py` for listed equities, tokenized equities, and cryptocurrencies. It validates asset-class-specific identity fields and treats tokenized equity as distinct from its underlying listed share. Exact venue evidence must match venue name, product ID, and market type, carry an HTTPS source URL and timezone-aware observation timestamp, and be no older than the configured freshness window. Missing, stale, future-dated, or mismatched evidence remains `not_verified`. The module is deliberately network-free; live exchange product discovery is a separate adapter still required before reports may claim current venue availability. Contract and boundaries: [instrument-identity-contract.md](instrument-identity-contract.md). Offline unit tests are included in `report_engine/tests/test_instruments.py`; the full CI matrix remains the verification gate.


## Source-attributed investment research evidence

A deterministic evidence record and research packet builder now lives in `report_engine/research.py`. It requires an exact instrument key, typed research dimension, scalar value/unit, evidence classification, source metadata (or explicit assumption note), and timezone-aware observation/retrieval timestamps. External sources require HTTPS; a `verified_source` classification requires a precise source reference. Freshness is only assessed against an explicit per-dimension age policy. Stale, future-dated, disputed, or unverified facts are surfaced as insufficient evidence; estimated values remain labeled. This layer validates metadata and provenance only—it does not fetch or authenticate source content. See [research-evidence-contract.md](research-evidence-contract.md). Provider retrieval, source-content verification, conflict reconciliation, fundamental calculations, and sector adapters remain outstanding.
