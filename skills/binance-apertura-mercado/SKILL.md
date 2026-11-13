# binance-apertura-mercado

## Purpose
Generate a detailed PDF report analyzing the previous completed market session/day.

## Required workflow
1. Determine the previous completed session using the skill's explicit session definition; use UTC for all boundaries and state them in the report.
2. Acquire and validate Binance market data. BTCUSDT and ETHUSDT are mandatory.
3. Analyze price structure, trend, volatility, volume, technical indicators, derivatives context when available, macroeconomic drivers, and relevant news.
4. Present bullish/long and bearish/short scenarios, assumptions, invalidation levels, and risk factors.
5. Generate and verify the PDF.

## Output
apertura-mercado_YYYY-MM-DD.pdf

## Integrity rules
Disclose missing intervals, stale or partial data, unavailable sources, and any provisional methodology. Never fabricate values, events, citations, or forecasts. If PDF generation fails, report the blocker; do not substitute another format.

## Status
Provisional ChatGPT adaptation. Exact original Claude skill parameters and report layout have not yet been reconciled against the original .skill source.