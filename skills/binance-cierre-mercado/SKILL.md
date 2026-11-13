# binance-cierre-mercado

## Purpose
Generate a detailed PDF report for the market session/day that has just closed.

## Required workflow
1. Confirm that the target session is complete; state its exact UTC start and end.
2. Acquire and validate Binance market data. BTCUSDT and ETHUSDT are mandatory.
3. Analyze the completed session: price action, trend, volatility, volume, technical indicators, derivatives context when available, macroeconomic drivers, and relevant news.
4. Present bullish/long and bearish/short scenarios with assumptions, invalidation conditions, and risk factors. Distinguish observed results from forward-looking interpretation.
5. Generate and verify the PDF.

## Output
cierre-mercado_YYYY-MM-DD.pdf

## Integrity rules
Disclose missing intervals, stale or partial data, unavailable sources, and provisional methodology. Never fabricate values, events, citations, or forecasts. If PDF generation fails, report the blocker; do not substitute another format.

## Status
Provisional ChatGPT adaptation. Exact original Claude skill parameters and report layout have not yet been reconciled against the original .skill source.