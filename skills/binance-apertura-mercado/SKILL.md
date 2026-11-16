# binance-apertura-mercado

## Purpose
Generate a detailed PDF report analyzing the previous completed UTC market day.

## Local Engine workflow
- Job type: `market.opening_report`
- Fixed output directory: `reports/opening`
- Filename: `apertura-mercado_YYYY-MM-DD.pdf`
- Optional `parameters.session_date_utc` selects a specific completed UTC date. If omitted, the engine selects the most recently completed UTC calendar day.
- The job must pass submit → validate → explicit approval → execute.

## Required report evidence
1. Exact 24-hour UTC session boundaries and generation timestamp.
2. Binance public market data for mandatory BTCUSDT and ETHUSDT.
3. Full session candles, OHLC/volume, performance, technical indicators, data validation, and provenance.
4. A separate 250-candle pre-session warm-up for indicator calculations. Warm-up candles must not be included in session statistics or charts.
5. Date-bounded macroeconomic and digital-asset news context, with publisher, publication timestamp, URL, and feed status.
6. Conditional bullish and bearish scenarios using prior-session range levels, with explicit invalidation references and risk caveats.

## Integrity rules
Disclose unavailable data and RSS feeds. Headlines are candidate context only, not proof of market causation. Scenario levels are conditional references, not forecasts, targets, or probabilities. Never fabricate values, events, citations, or analysis. Generate and independently inspect the PDF; if PDF generation or QA fails, fail the job and do not substitute another format.

## Status
Provisional ChatGPT adaptation. Exact original Claude skill parameters and report layout have not yet been reconciled against the original .skill source.