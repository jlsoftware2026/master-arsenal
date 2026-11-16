---
name: binance-cierre-mercado
description: 'Informe de cierre y recapitulación diaria. Activar cuando el usuario diga “cierre de mercado”, “resumen de cierre” o solicite cómo terminó la sesión. Analiza el día de la fecha local de solicitud, tanto la sesión bursátil estadounidense como la actividad de la cuenta Binance.'
version: 0.3.0
last_reviewed: 2026-11-16
---

# binance-cierre-mercado

## Purpose
Generate a detailed PDF report for the current Dominican local calendar day, including a clearly labeled partial-day window when local midnight has not yet arrived.

## Activation and scheduling
- Activate on “cierre de mercado”, “resumen de cierre”, “cómo cerró el mercado”, or an equivalent clear request.
- The original target is normally 15–20 minutes after 4:00 p.m. ET. Convert ET using the current U.S. DST rule.
- If the U.S. regular session has not closed, do not present a definitive closing report; state that it is still open and offer an intraday snapshot.
- On U.S. weekends/holidays, disclose the absence of a regular session and use the last completed cash session for equity context. Binance still uses the requested Dominican local calendar date, partial until local midnight if necessary.
- The current Local Engine does not schedule or enforce this activation time; disclose that limitation.

## Required PDF sections
1. Executive summary, Dominican local report date, exact cutoff, and partial/completed-day status.
2. U.S. session result: S&P 500, Nasdaq, Dow, Russell 2000, VIX, index futures, Treasury 10Y, DXY, WTI, and gold.
3. Sector performance, breadth, leaders/laggards, and major stock moves.
4. BTCUSDT and ETHUSDT local-day performance through the exact cutoff.
5. Technical indicators, support/resistance, and observed volatility.
6. Macroeconomic/Fed/earnings/geopolitical catalysts and timestamped news.
7. Binance account/portfolio results, fees/funding, open positions, and flows only with authorized account data or user exports.
8. Same-date opening forecast scorecard when an opening report exists.
9. Bullish/long and bearish/short scenarios, risks, source register, limitations, and conclusion.

If account, U.S. market, or opening-scorecard evidence is unavailable, disclose it. Never call a partial Binance local day complete. The current build does not yet integrate full U.S. market/calendar data, private-account exports, or opening-scorecard linkage.

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

## Version history
- 0.1.0 — 2026-11-16: Initial ChatGPT/MASTER ARSENAL adaptation; preserves the original skill identity and documents the Local Engine/PDF workflow and current implementation gaps.


## Language parity status
The report composers have been localized to Spanish. Language parity is not certified until opening, closing, and intraday PDFs all pass independent Spanish-marker QA on the same code head.

- 0.2.0 — 2026-11-16: Reconciled activation phrases, Dominican local-day semantics, PDF-only delivery, explicit limitations, and source-derived report requirements. Outstanding parity gaps remain disclosed.

- 0.3.0 — 2026-11-16: Localized report headings, tables, scenario narratives, disclaimers, and audit output into Spanish; added independent language-marker QA.
