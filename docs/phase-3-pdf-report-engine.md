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

- `binance_data_engine.session.acquire_completed_market_day` acquires a complete 24-hour UTC session for BTCUSDT and ETHUSDT.
- The requested session must be complete according to Binance server time.
- Default session selection is the most recently completed UTC calendar day; a caller may supply `session_date_utc`.
- Opening and closing reports share the same evidence contract and renderer but have distinct report titles and perspectives.
- The current scenario framework uses prior/session range high and low as conditional breakout and invalidation references. It does not invent targets or probabilities.
- Output:
  - `apertura-mercado_YYYY-MM-DD.pdf`
  - `cierre-mercado_YYYY-MM-DD.pdf`

### Intraday snapshot

- The report window is local midnight through the exact `America/Santo_Domingo` cutoff. If no cutoff is supplied, execution-time local time is resolved at runtime.\n- Local boundaries are converted to UTC for Binance requests. The exact cutoff is retained, and an unfinished final candle is excluded rather than rounded into the report.
- BTCUSDT and ETHUSDT are mandatory.
- The exact report-window candle count and each open/close boundary are validated; no interpolation or synthetic candles are used. Report intervals are bounded to one minute or higher to avoid unbounded per-second report artifacts.
- The output includes source-attributed market context, technical indicator tables, session-only charts, conditional range scenarios, risk notes, and provenance when evidence is available. With `market=usdm`, it also attempts premium index, funding history, open interest, global long/short account ratio, basis, mark-price klines, and index-price klines; each unavailable endpoint is disclosed rather than silently omitted.
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
- Missing artifacts and QA failures become explicit findings. No artifacts means insufficient evidence, not a pass.\n- The audit PDF now records a source-skill desk-check matrix, Critical/High/Medium/Low severity, Spanish verdict (No aprobado / Aprobado con reservas / Aprobado), and a version/change-history section. U.S. calendar/DST, account-ledger, source-package integrity, and scorecard cases remain unresolved and are not marked as passed.
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

For opening, `parameters.session_date_local` is the request date; the Binance reference day is the previous Dominican local date. For closing, it is the report date; a current-day cutoff may be supplied as ISO-8601 `parameters.cutoff_local`. Historical dates without a cutoff use the completed local day. The legacy `session_date_utc` parameter remains accepted as a compatibility alias.\n\nFor intraday, `parameters.cutoff_local` is an ISO-8601 local datetime. It may be omitted to resolve current Dominican local time. The legacy `cutoff_utc` parameter remains accepted, but both cutoff fields cannot be supplied together. Submit, validate, approve, and execute each job:
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
- The four original Claude `.skill` packages were supplied on 2026-11-16 and are the behavioral source of truth. Reconciliation is recorded in `docs/original-claude-skills-reconciliation.md`.\n- Full U.S. equity-market data/calendar coverage, private Binance account exports/connection, opening-to-closing forecast scorecard linkage, and the original audit desk-check matrix are not yet implemented. PDFs must disclose these limitations; public market candles are never represented as private account data.
- No OpenJarvis integration is included in this phase.

## Verification commands

```bash
python -m pip install -e .
python -m unittest discover -s binance_data_engine/tests -v
python -m unittest discover -s local_engine/tests -p 'test_local_engine.py' -v
python -m unittest discover -s report_engine/tests -v
```
