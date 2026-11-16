---
name: binance-apertura-mercado
description: 'Informe de apertura/premercado. Activar cuando el usuario diga “apertura de mercado”, “brief de apertura” o solicite el panorama antes de la apertura. Analiza la sesión bursátil estadounidense que abrirá hoy y el comportamiento de la cuenta Binance durante la sesión/día anterior. El día de referencia de la cuenta es el día calendario anterior a la fecha local de solicitud.'
version: 0.3.0
last_reviewed: 2026-11-16
---

# binance-apertura-mercado

## Purpose
Generate a detailed PDF report using the previous completed America/Santo_Domingo local calendar day as the Binance reference.

## Activation and scheduling
- Activate on “apertura de mercado”, “preapertura”, “resumen antes de abrir”, or an equivalent clear request.
- The original target is 15–20 minutes before the U.S. regular cash open (9:30 a.m. ET). Convert ET using the current U.S. DST rule; do not assume a fixed Dominican clock time.
- On U.S. weekends/holidays, disclose that no regular session opens and use the last completed U.S. cash session for equity context. Keep the Binance reference on the previous Dominican local calendar day.
- The current Local Engine does not schedule or enforce this activation time; disclose that limitation and require the caller to initiate the job.

## Required PDF sections
1. Executive summary and report timestamp.
2. U.S. premarket context: S&P 500, Nasdaq, Dow, Russell 2000, VIX, index futures, Treasury 10Y, DXY, WTI, and gold.
3. Sector breadth, leading/lagging groups, and notable stocks.
4. BTCUSDT and ETHUSDT previous Dominican local-day performance.
5. Technical indicators and support/resistance.
6. Macroeconomic calendar, Fed context, earnings, geopolitical catalysts, and timestamped news.
7. Binance account/portfolio: balances, equity, realized/unrealized PnL, fees/funding, positions, and flows, only when authorized account data or user exports exist.
8. Bullish/long and bearish/short scenarios with triggers and invalidation.
9. Risk management, assumptions, source register, limitations, and conclusion.

If U.S. market or account data is unavailable, state that explicitly. Never infer portfolio performance from public candles. The current build does not yet integrate full U.S. market/calendar data or private-account exports; the PDF must disclose both gaps.

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

## Version history
- 0.1.0 — 2026-11-16: Initial ChatGPT/MASTER ARSENAL adaptation; preserves the original skill identity and documents the Local Engine/PDF workflow and current implementation gaps.


## Language parity status
The report composers have been localized to Spanish. Language parity is not certified until opening, closing, and intraday PDFs all pass independent Spanish-marker QA on the same code head.

- 0.2.0 — 2026-11-16: Reconciled activation phrases, Dominican local-day semantics, PDF-only delivery, explicit limitations, and source-derived report requirements. Outstanding parity gaps remain disclosed.

- 0.3.0 — 2026-11-16: Localized report headings, tables, scenario narratives, disclaimers, and audit output into Spanish; added independent language-marker QA.
