---
name: binance-momento-mercado
description: 'Informe de mercado a una hora concreta o snapshot intradía. Activar cuando el usuario diga “momento específico del mercado”, “estado del mercado ahora”, “resumen a esta hora”, “snapshot intradía” o solicite el comportamiento del día hasta una hora indicada. El análisis empieza al inicio del día local y termina en la hora de corte solicitada.'
version: 1.0.0
last_reviewed: 2026-11-17
---

# binance-momento-mercado

## Purpose
Generate a detailed intraday PDF snapshot from Dominican local midnight through an exact local cutoff, excluding any unfinished candle.

## Activation
- Activate on “momento específico del mercado”, “estado del mercado ahora”, “resumen a esta hora”, “snapshot intradía”, or equivalent wording.
- If no hour is supplied, use execution-time America/Santo_Domingo local time. Never reuse a stale or guessed cutoff.
- Use the integrated XNYS calendar to classify premarket, regular session, postmarket, or closed at the exact cutoff. If calendar evidence is unavailable, label the classification unavailable.
- Distinguish the local-calendar-day move from the rolling 24-hour ticker change. Do not call the snapshot a closing report or extrapolate the remaining session as observed fact.

## Required PDF sections
1. Executive snapshot with exact Dominican local cutoff and generation time.
2. U.S. market state (premarket, regular, postmarket) only when supported by a reliable calendar.
3. BTCUSDT and ETHUSDT local-day performance from local midnight to cutoff.
4. Rolling 24-hour ticker change shown separately from local-day performance.
5. Technical indicators, momentum, volume, support/resistance, and derivatives evidence when available.
6. Macro/news catalysts with source timestamps.
7. Bullish/long and bearish/short conditional scenarios, invalidation levels, risk, limitations, and source register.

Do not predict the rest of the session unless the user explicitly requests a clearly labeled scenario. Use the best-effort Yahoo Finance snapshot for major U.S. indices, VIX, futures, rates, DXY, commodities, and sector ETFs; retain each quote's observation timestamp and source URL. Disclose missing symbols, delayed/incomplete data, and the fact that this is not an execution feed. Market breadth and stock-level leaders/laggards remain unavailable. If a supported transaction-history CSV exists in data/account_exports, summarize events by type and asset. Do not infer account equity, unrealized PnL or flow-adjusted returns. The XNYS calendar supplies session state, not prices.

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

## Pre-investment and opportunity analysis

Intraday market context can support a prospective investment decision even when the user has no transaction history. Do not require a Binance CSV export for watchlist research, asset screening, or hypothetical scenario calculations. If the user declares a pre-investment state, account performance is not applicable and personal balances/positions are not supplied; never infer a zero balance solely from an absent export.

Identify the exact instrument and venue for every candidate, distinguishing listed equities, tokenized equity products, and cryptocurrencies. Keep observed market data separate from fundamental interpretation and forward-looking scenarios. State data timestamps, source coverage, uncertainty, catalysts, downside risks, and the conditions that would invalidate the thesis. Do not present a market snapshot as a guaranteed prediction or an automatic trade instruction.

## Source-backed equity and biotechnology research

When the user names an equity or biotech candidate for prospective investment research, use the exact instrument identity already validated by the instrument registry. Do not run issuer-fundamental research for an unspecified ticker or infer an issuer CIK from a ticker symbol.

- For a U.S. filer, the SEC EDGAR Company Facts adapter may retrieve annual or quarterly revenue, operating income, net income, operating cash flow, total assets, and cash/equivalents. Require an explicitly configured `MASTER_ARSENAL_SEC_USER_AGENT` and caller-supplied CIK. Preserve filing form, concept, accession, filing date, period end, and retrieval timestamp. Missing XBRL concepts remain missing, not zero. The adapter does not provide total debt, free cash flow, valuation multiples, peer analysis, or narrative risk-factor analysis.
- For a biotech candidate, retrieve exact NCT records through ClinicalTrials.gov API v2 only when an NCT ID is supplied or otherwise established by primary issuer evidence. Record trial status, phase, enrollment and estimated/actual label, primary completion date, primary outcomes, interventions, and results-section presence.
- Require a documented issuer-to-trial attribution basis, such as an issuer filing identifying the candidate/intervention. A trial's lead sponsor or drug name alone does not prove listed-company ownership, rights, or economic exposure.
- Treat registry fields as sponsor-submitted data. Trial registration, phase, recruitment status, and the existence of a results section are not proof of efficacy, safety, approval, or commercial success. Do not call trial results positive without analyzing the posted outcomes and source context.
- Keep filing period-end, filing/publication date, registry last-update date, and retrieval timestamp distinct. Apply explicit freshness rules; if CIK/NCT mapping or source evidence is missing, state that the relevant diligence is not verified.
- Use these modules only when a candidate is explicitly in scope; do not turn an intraday snapshot into a full fundamental report. Keep observed market conditions separate from long-term evidence and analyst scenarios.



## Crypto protocol and token-economics evidence

When a prospective crypto asset is explicitly in scope, use its validated instrument identity and only attach protocol metrics when the caller supplies the exact DeFiLlama protocol slug and a documented token/protocol attribution basis.

- The DeFiLlama adapter may retrieve latest protocol TVL, daily fees, daily protocol revenue, and daily token-holder revenue. Keep these four concepts distinct and retain observation/retrieval timestamps.
- TVL is not revenue, market capitalization, or token-holder value capture. Protocol fees and protocol revenue are not interchangeable; token-holder revenue is a separate measure and may be unavailable.
- Missing metrics are not zero. Do not infer protocol ownership, token rights, or economic exposure from a shared ticker, brand, or protocol name.
- Token supply, unlock schedules, holder concentration, security audits, exploit history, governance quality, and regulatory analysis are not covered by this adapter. Mark these dimensions not verified unless supported by separate primary evidence.
- Use these metrics only for an explicitly named candidate; do not expand a time-specific intraday snapshot into a full protocol diligence report unless requested.

## Scenario and hypothetical position-risk calculations

Do not add scenario calculations or position sizing to a routine intraday snapshot unless the user explicitly requests prospective investment analysis. If requested, calculate bull/base/bear returns only from explicit hypothetical prices and written assumptions; never invent target prices, probabilities, or expected returns.

Hypothetical sizing requires explicit capital, risk budget, allocation cap, entry/invalidation assumptions, and cost assumptions. The engine is cash-only and unlevered; it does not imply an actual position or submit an order. An invalidation price is not a guaranteed execution price. Missing required inputs mean no sizing result is produced.


## Dedicated investment opportunity PDF workflow

An intraday snapshot is not a full investment thesis. When the user separately requests a candidate-level pre-investment report, use the approved Local Engine job `investment.opportunity_report`. The job requires exact instrument identity, explicit provider configuration and caller-supplied assumptions; it writes a standalone PDF to the fixed `reports/opportunities` directory after validation/approval. Never infer CIK, NCT, protocol slug, issuer ownership, or token rights.

The generated PDF has a SHA-256-bound evidence manifest. The `skills.audit` job checks PDF/manifest integrity, rebuilds the evidence packet, and recalculates scenario and sizing arithmetic. This does not authenticate source contents or independently prove issuer/trial/protocol attribution.


## Status
Adapted against the user-supplied original Claude skill package. XNYS premarket/regular/postmarket classification is integrated; Yahoo market quotes are best-effort and partial, with breadth and stock-level leaders/laggards unavailable. Local transaction-history CSV activity can be summarized, but portfolio equity and flow-adjusted returns remain unavailable.

## Version history
- 1.0.0 — 2026-11-17: Added standalone opportunity PDF workflow and SHA-256 evidence-manifest audit controls.
- 0.9.0 — 2026-11-17: Added explicit-assumption scenario and cash-only hypothetical position-risk calculation controls.
- 0.1.0 — 2026-11-16: Initial ChatGPT/MASTER ARSENAL adaptation; preserves the original skill identity and documents the Local Engine/PDF workflow and current implementation gaps.


## Language parity status
The opening, closing, and intraday PDF composers and the audit PDF use Spanish labels and narrative text. Independent marker and artifact tests for all three operational report types passed in GitHub Actions run 43925472913 (Ubuntu/Windows, Python 3.11/3.12). This verifies required content markers and PDF structure, not full semantic equivalence to every original source requirement.

- 0.2.0 — 2026-11-16: Reconciled activation phrases, Dominican local-day semantics, PDF-only delivery, explicit limitations, and source-derived report requirements. Outstanding parity gaps remain disclosed.

- 0.3.0 — 2026-11-16: Localized report headings, tables, scenario narratives, disclaimers, and audit output into Spanish; added independent language-marker QA.
- 0.5.0 — 2026-11-16: Integrated XNYS holiday, early-close, DST, and exact-cutoff session-state classification.
- 0.6.0 — 2026-11-16: Added source-attributed best-effort Yahoo Finance quote snapshots for U.S. indices, volatility, futures, rates, dollar, commodities, and sectors.
- 0.7.0 — 2026-11-16: Added privacy-conscious local transaction-history CSV activity summaries; portfolio valuation remains unavailable.
