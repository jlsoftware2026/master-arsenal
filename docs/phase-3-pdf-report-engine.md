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

### Completed UTC-day opening and closing reports

- `binance_data_engine.session.acquire_completed_market_day` acquires a complete 24-hour UTC session for BTCUSDT and ETHUSDT.
- The requested session must be complete according to Binance server time.
- Default session selection is the most recently completed UTC calendar day; a caller may supply `session_date_utc`.
- Opening and closing reports share the same evidence contract and renderer but have distinct report titles and perspectives.
- The current scenario framework uses prior/session range high and low as conditional breakout and invalidation references. It does not invent targets or probabilities.
- Output:
  - `apertura-mercado_YYYY-MM-DD.pdf`
  - `cierre-mercado_YYYY-MM-DD.pdf`

### Intraday snapshot

- The report window is `[00:00 UTC, cutoff_utc)` with an explicit UTC cutoff aligned to the selected interval.
- BTCUSDT and ETHUSDT are mandatory.
- The exact report-window candle count and each open/close boundary are validated; no interpolation or synthetic candles are used.
- The output includes source-attributed market context, technical indicator tables, session-only charts, conditional range scenarios, risk notes, and provenance when evidence is available.
- Output: `snapshot-mercado-YYYY-MM-DD_HH-mm.pdf`, based on UTC cutoff.

### Macro and news context

The standard-library RSS collector uses configured public feeds for:
- Digital-asset news: CoinDesk, Cointelegraph, and The Block.
- Macroeconomic/central-bank releases: Federal Reserve, Bureau of Labor Statistics, and European Central Bank.

Only items with publisher timestamps inside the report's UTC window are included. Each displayed item carries publisher, publication timestamp, URL, and a relevance disclaimer. Retrieval time and feed status are retained. Failed feeds are reported as unavailable; an empty feed result is not presented as proof that no relevant event occurred. Headlines are candidate context only and are not treated as proof of price causation. RSS coverage is not exhaustive.

### Independent skills audit

- `report_engine.audit.build_skills_audit_pdf` creates `auditoria-skills-binance_YYYY-MM-DD.pdf`.
- The Local Engine audit handler scans the fixed opening, closing, and intraday report directories, computes SHA-256 digests, and independently parses/renders every discovered PDF.
- Missing artifacts and QA failures become explicit findings. No artifacts means insufficient evidence, not a pass.
- The current automated audit focuses on artifact structure/readability. It does not yet independently recalculate every market indicator, verify all news claims, certify scenario quality, or prove parity with the original Claude skill source files.

## Local Engine job integration

All report jobs retain the existing sequence: submit → validate → explicit approval → claim → execute. No report handler starts before approval. Outputs are fixed by job type:

| Job type | Parameters | Output directory |
|---|---|---|
| `market.opening_report` | optional `session_date_utc`, `interval`, `market` | `reports/opening` |
| `market.closing_report` | optional `session_date_utc`, `interval`, `market` | `reports/closing` |
| `market.intraday_snapshot` | required `cutoff_utc`, optional `interval`, `market` | `reports/intraday` |
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

For opening/closing, optional `parameters.session_date_utc` uses `YYYY-MM-DD`; otherwise the most recently completed UTC day is selected. Intraday requires an explicit aligned UTC cutoff. Submit, validate, approve, and execute each job:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL submit opening-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL validate JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL approve JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL run JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL status JOB_UUID
```

## Verification and limitations

- CI is fixture-driven and covers Ubuntu/Windows with Python 3.11/3.12.
- Offline tests cover candle completeness, indicator warm-up, UTC boundaries, PDF generation, charts, source-context parsing, audit status, and Local Engine approval gates.
- Live Binance and RSS feed availability is not certified by offline CI. Binance geographic restrictions are not bypassed.
- The audit does not currently perform full semantic market-analysis recalculation.
- The original Claude `.skill` files have not been recovered verbatim. These remain provisional ChatGPT adaptations until the originals and their exact report layouts/checklists are reconciled.
- No OpenJarvis integration is included in this phase.

## Verification commands

```bash
python -m pip install -e .
python -m unittest discover -s binance_data_engine/tests -v
python -m unittest discover -s local_engine/tests -p 'test_local_engine.py' -v
python -m unittest discover -s report_engine/tests -v
```
