# binance-momento-mercado

## Purpose
Generate a detailed intraday PDF snapshot from Dominican local midnight through an exact local cutoff, excluding any unfinished candle.

## Local Engine workflow
- Job type: `market.intraday_snapshot`
- Fixed output directory: `reports/intraday`
- Filename: `snapshot-mercado-YYYY-MM-DD_HH-mm.pdf`
- Optional `parameters.cutoff_local`; if omitted, resolve execution-time America/Santo_Domingo local time. Legacy `cutoff_utc` remains accepted. Preserve the exact cutoff and record the last fully closed candle boundary separately.
- Optional `interval` and `market` parameters; defaults are 1h and spot.
- The job must pass submit → validate → explicit approval → execute.

## Required report evidence
1. Exact Dominican local reporting window `[local midnight, local cutoff)`, UTC-converted boundaries, generation time, and Binance server time.
2. Complete, aligned Binance candles for mandatory BTCUSDT and ETHUSDT. Missing, duplicate, malformed, partial, or unclosed candles fail acquisition.
3. A separate 250-candle historical warm-up for EMA/RSI/MACD/ATR/Bollinger/volume calculations. Exclude warm-up candles from report-window counts, statistics, and charts.
4. Date-bounded macroeconomic and digital-asset news context with publisher, publication timestamp, URL, retrieval time, and unavailable-feed disclosures.
5. Price/volume charts, conditional bullish/bearish range scenarios for the remaining period, invalidation references, and risks.

## Integrity rules
The Local Engine may retain a source-linked raw-evidence manifest under `data/manifests` for independent audit. This is internal audit evidence; the user-facing report output remains PDF-only.

Do not treat an incomplete day as a closed session. Headlines are candidate context only, not proof of market causation. Scenario levels are conditional references, not forecasts, targets, or probabilities. Never fabricate values, events, citations, or forecasts. Generate and independently inspect the PDF; if PDF generation or QA fails, fail the job and do not substitute another format.

## Status
Adapted against the user-supplied original Claude skill package. U.S. equity premarket/regular/postmarket classification and full market coverage remain unavailable/not verified.