# MASTER ARSENAL — Investment Opportunity Analysis

## Purpose

MASTER ARSENAL is intended to support research and decisions before capital is committed, not merely to report on an existing portfolio. A zero-transaction or pre-investment account is a valid operating state. Market research, candidate screening, scenario calculations, and risk analysis must work without transaction-history exports or private account access.

The system is decision support, not an autonomous trader or a guarantee of returns. The user combines sector knowledge with source-backed research and explicit uncertainty to decide whether an opportunity merits further consideration.

## Separate the two analytical domains

### 1. Opportunity research (works before the first transaction)

- Build and maintain a research watchlist based on the user's sectors of interest and candidate assets.
- Identify the exact instrument, asset class, issuer/protocol, ticker or contract, quote currency, and venue.
- Evaluate fundamentals and sector dynamics independently from short-term market timing.
- Analyze price, volume, liquidity, volatility, momentum, and market structure using timestamped data.
- Construct bullish, base, and bearish scenarios with assumptions, catalysts, risks, and thesis-invalidation conditions.
- Calculate scenario returns and hypothetical position/risk sizing only from explicit, traceable inputs.
- End with a qualified assessment: potential candidate for further diligence, wait for confirmation, insufficient evidence, or avoid for now.

### 2. Portfolio accounting (only after account activity exists)

- Import user-provided exports only when available and authorized.
- Reconcile balances, positions, fees, funding, realized/unrealized PnL, and external cash flows only when the required records exist.
- Never infer account equity, holdings, cost basis, or returns from public market candles or transaction activity alone.
- Missing exports mean personal account data is unavailable. They do not prove the account has a zero balance.
- If the user explicitly declares a pre-investment state, mark personal performance as not applicable and account balances/positions as not supplied. Do not require a CSV to generate opportunity research.

## Instrument identity and venue checks

Every candidate must be classified as one of:

- **Listed equity:** ordinary shares or another explicitly identified exchange-listed security.
- **Tokenized equity:** a tokenized product whose legal/economic rights may differ from owning the underlying share. Verify issuer, structure, redemption/transfer rights, jurisdiction, and current venue availability.
- **Cryptocurrency/token:** identify the asset, network, contract where relevant, quote pair, and market venue.

Never assume that a listed stock is tradable on Binance, or that a tokenized stock is equivalent to the underlying share. Verify current availability and product status at the time of analysis. If the requested asset is not available on Binance, say so and keep any broader research clearly separate from venue availability.

## Research dimensions

### Equities

- Business model, products, customers, competitive position, management, and industry structure.
- Revenue growth, margins, profitability, cash flow, debt, liquidity, dilution, and capital allocation.
- Valuation using suitable methods and peer comparisons; disclose limitations and avoid false precision.
- Sector-specific evidence. For medicine/biotechnology: clinical stage, trial endpoints, regulatory milestones, patent/IP position, safety signals, commercialization, and financing/runway. For medical devices: approvals, reimbursement, adoption, manufacturing, and competition. For technology: product differentiation, customer concentration, recurring revenue, infrastructure costs, competition, and regulatory exposure.
- Catalysts, risks, and thesis-invalidation conditions.

### Cryptocurrencies

- Protocol purpose, utility, adoption, developer/community activity, security history, governance, and competitive position.
- Token supply, emissions, unlock schedule, concentration, incentives, and value-capture mechanism.
- Network/protocol usage and revenue metrics where reliable and relevant.
- Exchange liquidity, market depth, custody/bridge risks, smart-contract risk, regulatory exposure, and token-specific risks.
- Catalysts and thesis-invalidation conditions.

### Market and technical context

- Trend, relative strength, volume, volatility, momentum, support/resistance, and market structure.
- For crypto, distinguish spot and derivatives evidence; funding, open interest, basis, and positioning are contextual signals, not proof of direction.
- For equities, distinguish regular-session prices, premarket/after-hours quotes, delayed data, and official exchange closes.
- Keep observation time, source, currency, venue, and time zone attached to every material value.

## Scenario and calculation policy

- Bullish, base, and bearish cases must state the assumptions that produce each outcome.
- Use explicit scenario prices/financial assumptions only when sourced or clearly identified as analyst/user assumptions.
- Calculate percentage upside/downside and reward-to-risk only when entry, target, and invalidation assumptions are supplied and internally consistent.
- Do not invent target prices, scenario probabilities, expected returns, or confidence scores.
- If probabilities cannot be supported, present qualitative scenarios rather than a fabricated expected value.
- Separate long-term investment thesis from short-term entry timing.
- Hypothetical position sizing must disclose the assumed capital, risk budget, and loss-at-invalidation; it must not imply that the user has placed an order.

## Standard conclusion taxonomy

1. **Potential candidate for further diligence:** evidence is sufficiently positive to justify deeper research; not an instruction to buy.
2. **Wait for confirmation:** thesis may be attractive, but valuation, catalyst, market structure, or data coverage is not yet adequate.
3. **Insufficient evidence:** critical inputs are missing, stale, contradictory, or unverifiable.
4. **Avoid for now:** risk, valuation, fundamentals, tokenomics, or instrument structure is not adequately compensated by the plausible upside.

Every conclusion must explain the strongest supporting evidence, the strongest counterargument, key uncertainties, and what would change the assessment.

## Data quality and source hierarchy

Prefer regulatory filings, issuer disclosures, audited financial statements, official clinical-trial/regulatory sources, protocol documentation, exchange market data, and reputable timestamped market-data providers. Secondary research and news may add context but must not replace primary evidence for material claims. Record source URLs, publication/observation timestamps, retrieval timestamps, and any delays or coverage gaps. If a data provider is unavailable, do not silently substitute an unrelated instrument or stale quote.

## Zero-transaction acceptance criteria

- The three operational market reports and the skills audit can run without a transaction-history CSV.
- A declared pre-investment state is represented distinctly from an active account with missing exports.
- Personal account balances, positions, PnL, and returns are labeled not supplied/not applicable as appropriate; no zero balance is fabricated.
- Asset research, watchlist screening, fundamental/sector analysis, and hypothetical scenario calculations do not depend on personal transaction history.
- Every candidate has an exact instrument/venue identity and source-backed evidence.
- A candidate conclusion includes bull/base/bear cases, risks, invalidation conditions, data freshness, and uncertainty.
- No orders, account actions, credential collection, or autonomous execution are introduced.

## Delivery sequence

1. Preserve the current PDF/report pipeline and its read-only constraints.
2. Add the pre-investment account state and opportunity-research data contract.
3. Implement instrument identity/venue verification and a source-attributed candidate data model.
4. Add equity fundamentals and crypto tokenomics adapters with explicit provider/coverage limitations.
5. Add reproducible scenario and hypothetical position-sizing calculations with fixture tests.
6. Integrate opportunity analysis into the four PDF skills and the independent audit.
7. Validate the full cross-platform CI matrix before considering Phase 3 complete.

## Current scope boundary

The current Phase 3 implementation is a market-report/PDF foundation with Binance public market acquisition, limited U.S. market snapshots, and a privacy-conscious local transaction-history importer. It is not yet a complete equity/crypto fundamental research engine, a portfolio-accounting system, or a personalized recommendation engine. The steps above are the next implementation work; no live trading or account access is required.
