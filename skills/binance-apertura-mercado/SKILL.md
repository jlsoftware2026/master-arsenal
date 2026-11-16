# binance-apertura-mercado

## Purpose
Generate a detailed PDF report using the previous completed America/Santo_Domingo local calendar day as the Binance reference.

## Local Engine workflow
- Job type: `market.opening_report`
- Fixed output directory: `reports/opening`
- Filename: `apertura-mercado_YYYY-MM-DD.pdf`
- Optional `parameters.session_date_local` is the local request date; the Binance reference is the preceding Dominican calendar date. If omitted, the current Dominican local date is used as the request date.
- The job must pass submit → validate → explicit approval → execute.

## Required report evidence
1. Exact Dominican local midnight-to-next-midnight boundaries, their UTC conversions, and generation timestamp.
2. Binance public market data for mandatory BTCUSDT and ETHUSDT.
3. Full session candles, OHLC/volume, performance, technical indicators, data validation, and provenance.
4. A separate 250-candle pre-session warm-up for indicator calculations. Warm-up candles must not be included in session statistics or charts.
5. Date-bounded macroeconomic and digital-asset news context, with publisher, publication timestamp, URL, and feed status.
6. Conditional bullish and bearish scenarios using prior-session range levels, with explicit invalidation references and risk caveats.

## Integrity rules
The Local Engine may retain a source-linked raw-evidence manifest under `data/manifests` for independent audit. This is internal audit evidence; the user-facing report output remains PDF-only.

Disclose unavailable data and RSS feeds. Headlines are candidate context only, not proof of market causation. Scenario levels are conditional references, not forecasts, targets, or probabilities. Never fabricate values, events, citations, or analysis. Generate and independently inspect the PDF; if PDF generation or QA fails, fail the job and do not substitute another format.

## Status
Adapted against the user-supplied original Claude skill package. U.S. market data/calendar and private-account evidence remain explicitly unavailable until integrated.