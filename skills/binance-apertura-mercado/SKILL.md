---
name: binance-apertura-mercado
description: 'Informe de apertura/premercado. Activar cuando el usuario diga “apertura de mercado”, “brief de apertura” o solicite el panorama antes de la apertura. Analiza la sesión bursátil estadounidense que abrirá hoy y el comportamiento de la cuenta Binance durante la sesión/día anterior. El día de referencia de la cuenta es el día calendario anterior a la fecha local de solicitud.'
version: 1.3.0
last_reviewed: 2026-11-17
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

If U.S. market or account data is unavailable, state that explicitly. Never infer portfolio performance from public candles. The XNYS exchange calendar supplies U.S. cash-session holidays, early closes, DST-aware session times, and session classification. A best-effort Yahoo Finance snapshot now covers major indices, VIX, index futures, Treasury 10Y yield, DXY, WTI, gold, and sector ETFs with source URLs and observation timestamps. It is not a licensed execution feed; breadth and stock-level leaders/laggards remain unavailable. If a supported Binance transaction-history CSV is present in data/account_exports, summarize balance-change activity by event type and asset; otherwise mark account activity unavailable. Never infer equity or returns from this CSV.

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

## Pre-investment and opportunity analysis

Market research and portfolio accounting are separate capabilities. A user may request an opening outlook, screen an equity or cryptocurrency, and evaluate a hypothetical investment before making any Binance transaction. Do not require a transaction-history export to perform market or asset research. When the user has declared a pre-investment state, label account performance as not applicable and account balances/positions as not supplied; do not infer a zero balance from a missing CSV.

For each candidate, identify the exact instrument and venue before analysis. Distinguish ordinary listed shares from tokenized equity products and from cryptocurrencies. Verify whether the instrument is currently available through the requested venue; do not assume a stock ticker is tradable on Binance. Separate company/sector fundamentals from market timing, and present bullish, base, and bearish scenarios with explicit assumptions, catalysts, invalidation conditions, data timestamps, and source links. The user’s sector knowledge (for example medicine, biotechnology, medical devices, and technology) can guide screening, but does not replace independent evidence or risk analysis.

## Source-backed equity and biotechnology research

When the user names an equity or biotech candidate for prospective investment research, use the exact instrument identity already validated by the instrument registry. Do not run issuer-fundamental research for an unspecified ticker. For U.S. listed equities, the opportunity workflow may opt in to the SEC exchange-aware ticker directory using the candidate's exact symbol, exchange, and issuer name; it must fail closed on missing, ambiguous, or mismatched records. Tokenized equity still requires an explicit underlying-issuer CIK.

- For a U.S. filer, the SEC EDGAR Company Facts adapter may retrieve annual or quarterly revenue, gross profit, operating income, net income, operating cash flow, capital expenditures, total/current assets, current liabilities, stockholders' equity, and cash/equivalents. Require an explicitly configured `MASTER_ARSENAL_SEC_USER_AGENT`. Use either a manually confirmed CIK or the opt-in exact ticker/exchange/issuer resolver for listed equities; do not guess or silently select an ambiguous match. Preserve filing form, concept, accession, filing date, period end, and retrieval timestamp. Missing XBRL concepts remain missing, not zero.
- The derived ratio engine calculates gross/operating/net/cash-flow margins, free cash flow and margin, current ratio, cash/current-liabilities, and period-end ROA/ROE proxies only from same-period, same-currency facts. It preserves formulas and source fact IDs; it skips missing, mismatched, ambiguous, or zero-denominator inputs. It does not calculate growth rates, total-debt aggregation, valuation multiples, peer analysis, or narrative risk-factor analysis.
- For a biotech candidate, retrieve exact NCT records through ClinicalTrials.gov API v2 only when an NCT ID is supplied or otherwise established by primary issuer evidence. Record trial status, phase, enrollment and estimated/actual label, primary completion date, primary outcomes, interventions, and results-section presence.
- Require a documented issuer-to-trial attribution basis, such as an issuer filing identifying the candidate/intervention. A trial's lead sponsor or drug name alone does not prove listed-company ownership, rights, or economic exposure.
- Treat registry fields as sponsor-submitted data. Trial registration, phase, recruitment status, and the existence of a results section are not proof of efficacy, safety, approval, or commercial success. Do not call trial results positive without analyzing the posted outcomes and source context.
- Keep filing period-end, filing/publication date, registry last-update date, and retrieval timestamp distinct. Apply explicit freshness rules; if CIK/NCT mapping or source evidence is missing, state that the relevant diligence is not verified.
- Inspect the research packet's unresolved source conflicts. Different sourced values for the same labeled metric, unit, and observation period must be disclosed with source provenance; do not choose a preferred value or average them. A conflict keeps the packet insufficient until reconciled. Analyst/user assumptions are not source conflicts.
- These research modules provide evidence, not a buy/sell decision. Present positive evidence, counterevidence, unresolved questions, catalysts, and thesis-invalidation conditions separately from the market-opening snapshot.



## Crypto protocol and token-economics evidence

When a prospective crypto asset is explicitly in scope, use its validated instrument identity and only attach protocol metrics when the caller supplies the exact DeFiLlama protocol slug and a documented token/protocol attribution basis.

- The DeFiLlama adapter may retrieve latest protocol TVL, daily fees, daily protocol revenue, and daily token-holder revenue. Keep these four concepts distinct and retain observation/retrieval timestamps.
- TVL is not revenue, market capitalization, or token-holder value capture. Protocol fees and protocol revenue are not interchangeable; token-holder revenue is a separate measure and may be unavailable.
- Missing metrics are not zero. Do not infer protocol ownership, token rights, or economic exposure from a shared ticker, brand, or protocol name.
- Token supply, unlock schedules, holder concentration, security audits, exploit history, governance quality, and regulatory analysis are not covered by this adapter. Mark these dimensions not verified unless supported by separate primary evidence.
- Use protocol fundamentals as a separate long-horizon research layer; do not confuse them with the previous local day's Binance market performance or opening conditions.

## Scenario and hypothetical position-risk calculations

When the user explicitly requests a forward-looking investment scenario, the scenario engine may calculate bull/base/bear price returns and reward-to-risk only from caller-supplied hypothetical entry, invalidation, and scenario prices with written assumptions. Never invent target prices, probabilities, expected returns, or a forecast.

Hypothetical position sizing is permitted only when the user explicitly supplies available capital, risk budget, maximum allocation, entry/invalidation assumptions, and cost assumptions. The calculator is cash-only and unlevered. Do not infer that the user owns the asset or has placed an order. State that an invalidation level is not a guaranteed execution price and actual losses can exceed the estimate. If any required input is absent, do not fill it with a guessed default; report that sizing is not calculated.


## Dedicated investment opportunity PDF workflow

The opening-market PDF remains a time-specific market-session report. When the user separately requests a candidate-level pre-investment report, use the approved Local Engine job `investment.opportunity_report` rather than silently expanding the opening snapshot. The job requires an exact asset identity, accepts only explicitly configured SEC/ClinicalTrials.gov/DeFiLlama sources and caller-supplied assumptions, and writes to the fixed `reports/opportunities` directory after the normal validation/approval gate. Never infer CIK, NCT, protocol slug, issuer ownership, or token rights.

The generated PDF has a SHA-256-bound evidence manifest. The `skills.audit` job checks the PDF/manifest link, rebuilds the evidence packet, and recalculates scenario and sizing arithmetic. This does not prove source-content truth or the correctness of issuer/trial/protocol attribution; disclose those remaining diligence limits.


## Status
Adapted against the user-supplied original Claude skill package. The XNYS calendar and best-effort Yahoo Finance quote snapshot are integrated. Breadth and stock-level leaders/laggards remain unavailable. Transaction-history CSV activity can be summarized, but account equity, unrealized PnL and flow-adjusted returns remain unavailable.

## Version history
- 1.3.0 — 2026-11-17: Added cross-source conflict detection and disclosure in opportunity reports.
- 1.2.0 — 2026-11-17: Added opt-in SEC ticker-to-CIK resolution with exact exchange/issuer matching and fail-closed ambiguity handling.
- 1.1.0 — 2026-11-17: Added same-period SEC-derived financial ratios and independent ratio recalculation in opportunity reports.
- 1.0.0 — 2026-11-17: Added standalone opportunity PDF workflow and SHA-256 evidence-manifest audit controls.
- 0.9.0 — 2026-11-17: Added explicit-assumption scenario and cash-only hypothetical position-risk calculation controls.
- 0.1.0 — 2026-11-16: Initial ChatGPT/MASTER ARSENAL adaptation; preserves the original skill identity and documents the Local Engine/PDF workflow and current implementation gaps.


## Language parity status
The opening, closing, and intraday PDF composers and the audit PDF use Spanish labels and narrative text. Independent marker and artifact tests for all three operational report types passed in GitHub Actions run 43925472913 (Ubuntu/Windows, Python 3.11/3.12). This verifies required content markers and PDF structure, not full semantic equivalence to every original source requirement.

- 0.2.0 — 2026-11-16: Reconciled activation phrases, Dominican local-day semantics, PDF-only delivery, explicit limitations, and source-derived report requirements. Outstanding parity gaps remain disclosed.

- 0.3.0 — 2026-11-16: Localized report headings, tables, scenario narratives, disclaimers, and audit output into Spanish; added independent language-marker QA.
- 0.5.0 — 2026-11-16: Integrated XNYS holiday/early-close calendar and a 09:10 ET premarket reference.
- 0.6.0 — 2026-11-16: Added source-attributed Yahoo Finance quotes for major U.S. indices, VIX, futures, rates, dollar, commodities, and sector ETFs.
- 0.7.0 — 2026-11-16: Added read-only local Binance transaction-history CSV activity summaries; portfolio equity and flow-adjusted returns remain unavailable.
