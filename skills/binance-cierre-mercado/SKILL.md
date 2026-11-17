---
name: binance-cierre-mercado
description: 'Informe de cierre y recapitulación diaria. Activar cuando el usuario diga “cierre de mercado”, “resumen de cierre” o solicite cómo terminó la sesión. Analiza el día de la fecha local de solicitud, tanto la sesión bursátil estadounidense como la actividad de la cuenta Binance.'
version: 1.6.0
last_reviewed: 2026-11-17
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

If account, U.S. market, or opening-scorecard evidence is unavailable, disclose it. Never call a partial Binance local day complete. The XNYS calendar now supplies session holidays, early closes, and DST-aware session-state classification. Best-effort Yahoo Finance quotes now cover major indices, VIX, futures, Treasury 10Y yield, DXY, WTI, gold, and sector ETFs with source URLs and observation timestamps. The feed may be delayed/incomplete and is not for execution. Market breadth and stock-level leaders/laggards remain unavailable. If a supported local transaction-history CSV is supplied, summarize activity by event and asset; account equity, unrealized PnL, full cost basis, and flow-adjusted returns remain unavailable. Same-date opening-to-closing scenario reconciliation is implemented when an integrity-checked opening manifest exists; otherwise the report states that no opening forecast was available.

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

## Pre-investment and opportunity analysis

A completed market recap must remain useful even when the user has not begun investing. Do not require transaction-history CSVs to research or assess candidate equities and cryptocurrencies. If the user declares a pre-investment state, show account performance as not applicable and account balances/positions as not supplied; a missing export alone must never be interpreted as proof of a zero balance.

For every candidate, verify the exact instrument, asset class, and venue. Listed shares, tokenized equity products, and cryptocurrencies are different instruments and must not be conflated. Evaluate company or protocol fundamentals, sector catalysts, valuation/tokenomics, liquidity, technical conditions, and downside risks. Present bullish, base, and bearish scenarios with transparent assumptions and invalidation conditions. Do not fabricate target prices, probabilities, or expected returns.

## Source-backed equity and biotechnology research

When the user names an equity or biotech candidate for prospective investment research, use the exact instrument identity already validated by the instrument registry. Do not run issuer-fundamental research for an unspecified ticker. For U.S. listed equities, the opportunity workflow may opt in to the SEC exchange-aware ticker directory using the candidate's exact symbol, exchange, and issuer name; it must fail closed on missing, ambiguous, or mismatched records. Tokenized equity still requires an explicit underlying-issuer CIK.

- For a U.S. filer, the SEC EDGAR Company Facts adapter may retrieve annual or quarterly revenue, gross profit, operating income, net income, operating cash flow, capital expenditures, total/current assets, current liabilities, stockholders' equity, and cash/equivalents. Require an explicitly configured `MASTER_ARSENAL_SEC_USER_AGENT`. Use either a manually confirmed CIK or the opt-in exact ticker/exchange/issuer resolver for listed equities; do not guess or silently select an ambiguous match. Preserve filing form, concept, accession, filing date, period end, and retrieval timestamp. Missing XBRL concepts remain missing, not zero.
- The derived ratio engine calculates gross/operating/net/cash-flow margins, free cash flow and margin, current ratio, cash/current-liabilities, and period-end ROA/ROE proxies only from same-period, same-currency facts. It preserves formulas and source fact IDs; it skips missing, mismatched, ambiguous, or zero-denominator inputs. It does not calculate growth rates, total-debt aggregation, valuation multiples, peer analysis, or narrative risk-factor analysis.
- For a biotech candidate, retrieve exact NCT records through ClinicalTrials.gov API v2 only when an NCT ID is supplied or otherwise established by primary issuer evidence. Record trial status, phase, enrollment and estimated/actual label, primary completion date, primary outcomes, interventions, and results-section presence.
- Require a documented issuer-to-trial attribution basis, such as an issuer filing identifying the candidate/intervention. A trial's lead sponsor or drug name alone does not prove listed-company ownership, rights, or economic exposure.
- Treat registry fields as sponsor-submitted data. Trial registration, phase, recruitment status, and the existence of a results section are not proof of efficacy, safety, approval, or commercial success. Do not call trial results positive without analyzing the posted outcomes and source context.
- Keep filing period-end, filing/publication date, registry last-update date, and retrieval timestamp distinct. Apply explicit freshness rules; if CIK/NCT mapping or source evidence is missing, state that the relevant diligence is not verified.
- Inspect the research packet's unresolved source conflicts. Different sourced values for the same labeled metric, unit, and observation period must be disclosed with source provenance; do not choose a preferred value or average them. A conflict keeps the packet insufficient until reconciled. Analyst/user assumptions are not source conflicts.
- For crypto candidates, optionally enable the public read-only Binance Spot product check. It verifies exact base/quote/product identity, `TRADING` status, and explicit Spot permission. It is not account eligibility or liquidity verification. Listed equity is never treated as a Spot share; tokenized equity remains not verified by ticker-only matching and needs separately sourced contract/issuer/rights evidence.
- These research modules provide evidence, not a buy/sell decision. Separate the completed/partial market-session recap from longer-term fundamentals, catalysts, and thesis-invalidation conditions.



## Crypto protocol and token-economics evidence

When a prospective crypto asset is explicitly in scope, use its validated instrument identity and only attach protocol metrics when the caller supplies the exact DeFiLlama protocol slug and a documented token/protocol attribution basis.

- The DeFiLlama adapter may retrieve latest protocol TVL, daily fees, daily protocol revenue, and daily token-holder revenue. Keep these four concepts distinct and retain observation/retrieval timestamps.
- TVL is not revenue, market capitalization, or token-holder value capture. Protocol fees and protocol revenue are not interchangeable; token-holder revenue is a separate measure and may be unavailable.
- Missing metrics are not zero. Do not infer protocol ownership, token rights, or economic exposure from a shared ticker, brand, or protocol name.
- Token supply, unlock schedules, holder concentration, security audits, exploit history, governance quality, and regulatory analysis are not covered by this adapter. Mark these dimensions not verified unless supported by separate primary evidence.
- Keep protocol fundamentals separate from the completed/partial Binance market-session recap and any forward-looking market scenario.

## Scenario and hypothetical position-risk calculations

When the user explicitly requests a forward-looking investment scenario, the scenario engine may calculate bull/base/bear price returns and reward-to-risk only from caller-supplied hypothetical entry, invalidation, and scenario prices with written assumptions. Never invent target prices, probabilities, expected returns, or a forecast.

Hypothetical position sizing is permitted only when the user explicitly supplies available capital, risk budget, maximum allocation, entry/invalidation assumptions, and cost assumptions. The calculator is cash-only and unlevered. Do not infer that the user owns the asset or has placed an order. State that an invalidation level is not a guaranteed execution price and actual losses can exceed the estimate. If any required input is absent, do not fill it with a guessed default; report that sizing is not calculated.


## Dedicated investment opportunity PDF workflow

The closing-market PDF remains a time-specific market-session report. When the user separately requests a candidate-level pre-investment report, use the approved Local Engine job `investment.opportunity_report` rather than silently expanding the closing recap. The job requires an exact asset identity, accepts explicitly configured SEC/ClinicalTrials.gov/DeFiLlama sources, optional read-only Binance Spot product verification, and caller-supplied assumptions, and writes to the fixed `reports/opportunities` directory after the normal validation/approval gate. Never infer CIK, NCT, protocol slug, issuer ownership, or token rights. When `binance_spot_check` is enabled, verify exact base/quote product identity, trading status, and Spot permission; do not treat listed shares as Spot products or infer underlying rights from tokenized-equity listings.

The generated PDF has a SHA-256-bound evidence manifest. The `skills.audit` job checks the PDF/manifest link, rebuilds the evidence packet, and recalculates scenario and sizing arithmetic. This does not prove source-content truth or the correctness of issuer/trial/protocol attribution; disclose those remaining diligence limits.



## Crypto tokenomics evidence
For crypto candidates, use `ma.tokenomics/v1` only when source-attributed supply, price, unlock, or holder observations are available. Keep circulating, total, and maximum supply distinct; calculate market capitalization and fully diluted valuation only from same-UTC-date price and supply observations. Show known unlocks over 30/90/365 days as percentages of circulating supply, and explicitly state that unprovided schedule events may exist. Holder concentration must include a declared coverage percentage and remain partial when coverage is below 100%; wallet addresses are not automatically beneficial owners. Every observation must retain source name, HTTPS URL, source reference, and timestamp. Missing supply, unlock, or holder information must be disclosed as not supplied/not assessed, never treated as zero. This analysis does not establish token safety, governance quality, legal status, or investment suitability.

## Status
Adapted against the user-supplied original Claude skill package. U.S. market breadth, stock-level leaders/laggards, portfolio equity/PnL analytics and automated activation timing remain unavailable. Supported local transaction-history CSV activity is summarized by event and asset. Same-date opening-to-closing range scorecard is integrated when a valid same-date opening manifest exists; absence is marked not applicable. XNYS calendar/session classification and best-effort Yahoo quote snapshots are integrated.

## Version history
- 1.5.0 — 2026-11-17: Added crypto-only Binance Spot product verification and explicit tokenized-equity safeguards.
- 1.4.0 — 2026-11-17: Added optional read-only Binance Spot product verification with exact identity and status checks.
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
- 0.5.0 — 2026-11-16: Integrated XNYS holiday/early-close calendar and exact-cutoff session classification.
- 0.6.0 — 2026-11-16: Added source-attributed Yahoo Finance quote snapshots.
- 0.7.0 — 2026-11-16: Added read-only local transaction-history CSV activity summaries; account equity/PnL and automated activation remain outstanding.
