# binance-cierre-mercado

## Purpose
Generate a detailed PDF report for the current Dominican local calendar day, including a clearly labeled partial-day window when local midnight has not yet arrived.

## Local Engine workflow
- Job type: `market.closing_report`
- Fixed output directory: `reports/closing`
- Filename: `cierre-mercado_YYYY-MM-DD.pdf`
- Optional `parameters.session_date_local` selects the Dominican local report date. `parameters.cutoff_local` may set an exact local cutoff; if omitted for the current date, execution-time local time is used. Historical dates without a cutoff use the completed local day.
- The job must pass submit → validate → explicit approval → execute.

## Required report evidence
1. Record the exact Dominican local reporting window and UTC-converted boundaries. A current-day report before local midnight is partial, not a completed day; exclude any unfinished final candle.
2. Binance public market data for mandatory BTCUSDT and ETHUSDT.
3. Session OHLC/volume, performance, technical indicators, validation results, and provenance.
4. A separate 250-candle pre-session warm-up for indicator calculations; exclude it from session statistics and charts.
5. Date-bounded macroeconomic and digital-asset news context, with publisher, publication timestamp, URL, and feed status.
6. Conditional bullish and bearish scenarios using the completed session range, assumptions, invalidation references, and risk caveats. Separate observed session results from forward-looking interpretation.

## Integrity rules
The Local Engine may retain a source-linked raw-evidence manifest under `data/manifests` for independent audit. This is internal audit evidence; the user-facing report output remains PDF-only.

Disclose incomplete data and unavailable feeds. Headlines are candidate context only, not proof of market causation. Scenario levels are conditional references, not forecasts, targets, or probabilities. Never fabricate values, events, citations, or forecasts. Generate and independently inspect the PDF; if PDF generation or QA fails, fail the job and do not substitute another format.

## Status
Adapted against the user-supplied original Claude skill package. U.S. market data/calendar, private-account analytics, automated activation timing, and same-date opening forecast scorecard remain unavailable/not implemented and are disclosed.