# binance-momento-mercado

## Purpose
Generate a detailed intraday PDF snapshot of market behavior from 00:00 UTC through the requested/current cutoff.

## Required workflow
1. Set the reporting window to the current UTC day beginning 00:00 and ending at the explicitly stated cutoff. Never treat an incomplete day as a closed session.
2. Acquire and validate Binance market data. BTCUSDT and ETHUSDT are mandatory.
3. Analyze intraday price action, trend, volatility, volume, technical indicators, derivatives context when available, macroeconomic drivers, and relevant news.
4. Present bullish/long and bearish/short scenarios, assumptions, invalidation conditions, and risks for the remaining period. Label forecasts as uncertain.
5. Generate and verify the PDF.

## Output
snapshot-mercado-YYYY-MM-DD_HH-mm.pdf

## Integrity rules
State the cutoff and data retrieval time in UTC. Disclose missing intervals, stale or partial data, unavailable sources, and provisional methodology. Never fabricate values, events, citations, or forecasts. If PDF generation fails, report the blocker; do not substitute another format.

## Status
Provisional ChatGPT adaptation. Exact original Claude skill parameters and report layout have not yet been reconciled against the original .skill source.