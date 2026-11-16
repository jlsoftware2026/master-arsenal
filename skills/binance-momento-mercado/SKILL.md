---
name: binance-momento-mercado
description: 'Informe de mercado a una hora concreta o snapshot intradía. Activar cuando el usuario diga “momento específico del mercado”, “estado del mercado ahora”, “resumen a esta hora”, “snapshot intradía” o solicite el comportamiento del día hasta una hora indicada. El análisis empieza al inicio del día local y termina en la hora de corte solicitada.'
version: 0.4.0
last_reviewed: 2026-11-16
---

# binance-momento-mercado

## Purpose
Generate a detailed intraday PDF snapshot from Dominican local midnight through an exact local cutoff, excluding any unfinished candle.

## Activation
- Activate on “momento específico del mercado”, “estado del mercado ahora”, “resumen a esta hora”, “snapshot intradía”, or equivalent wording.
- If no hour is supplied, use execution-time America/Santo_Domingo local time. Never reuse a stale or guessed cutoff.
- State whether U.S. equities are premarket, regular session, or postmarket only when reliable session-calendar evidence exists. Otherwise label the classification unavailable.
- Distinguish the local-calendar-day move from the rolling 24-hour ticker change. Do not call the snapshot a closing report or extrapolate the remaining session as observed fact.

## Required PDF sections
1. Executive snapshot with exact Dominican local cutoff and generation time.
2. U.S. market state (premarket, regular, postmarket) only when supported by a reliable calendar.
3. BTCUSDT and ETHUSDT local-day performance from local midnight to cutoff.
4. Rolling 24-hour ticker change shown separately from local-day performance.
5. Technical indicators, momentum, volume, support/resistance, and derivatives evidence when available.
6. Macro/news catalysts with source timestamps.
7. Bullish/long and bearish/short conditional scenarios, invalidation levels, risk, limitations, and source register.

Do not predict the rest of the session unless the user explicitly requests a clearly labeled scenario. Private-account analytics and full U.S. session/calendar coverage must be disclosed as unavailable until implemented.

## Local Engine workflow
- Job type: `market.intraday_snapshot`
- Fixed output directory: `reports/intraday`
- Filename: `snapshot-mercado_YYYY-MM-DD_HH-mm.pdf`
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

## Version history
- 0.1.0 — 2026-11-16: Initial ChatGPT/MASTER ARSENAL adaptation; preserves the original skill identity and documents the Local Engine/PDF workflow and current implementation gaps.


## Language parity status
The opening, closing, and intraday PDF composers and the audit PDF use Spanish labels and narrative text. Independent marker and artifact tests for all three operational report types passed in GitHub Actions run 43925472913 (Ubuntu/Windows, Python 3.11/3.12). This verifies required content markers and PDF structure, not full semantic equivalence to every original source requirement.

- 0.2.0 — 2026-11-16: Reconciled activation phrases, Dominican local-day semantics, PDF-only delivery, explicit limitations, and source-derived report requirements. Outstanding parity gaps remain disclosed.

- 0.3.0 — 2026-11-16: Localized report headings, tables, scenario narratives, disclaimers, and audit output into Spanish; added independent language-marker QA.
