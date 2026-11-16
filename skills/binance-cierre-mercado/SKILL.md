# binance-cierre-mercado

## Purpose
Generate a detailed PDF report for a market day that has just completed.

## Local Engine workflow
- Job type: `market.closing_report`
- Fixed output directory: `reports/closing`
- Filename: `cierre-mercado_YYYY-MM-DD.pdf`
- Optional `parameters.session_date_utc` selects a specific completed UTC date. If omitted, the engine selects the most recently completed UTC calendar day.
- The job must pass submit → validate → explicit approval → execute.

## Required report evidence
1. Confirm the entire 24-hour UTC session is complete according to Binance server time.
2. Binance public market data for mandatory BTCUSDT and ETHUSDT.
3. Session OHLC/volume, performance, technical indicators, validation results, and provenance.
4. A separate 250-candle pre-session warm-up for indicator calculations; exclude it from session statistics and charts.
5. Date-bounded macroeconomic and digital-asset news context, with publisher, publication timestamp, URL, and feed status.
6. Conditional bullish and bearish scenarios using the completed session range, assumptions, invalidation references, and risk caveats. Separate observed session results from forward-looking interpretation.

## Integrity rules
Disclose incomplete data and unavailable feeds. Headlines are candidate context only, not proof of market causation. Scenario levels are conditional references, not forecasts, targets, or probabilities. Never fabricate values, events, citations, or forecasts. Generate and independently inspect the PDF; if PDF generation or QA fails, fail the job and do not substitute another format.

## Status
Provisional ChatGPT adaptation. Exact original Claude skill parameters and report layout have not yet been reconciled against the original .skill source.