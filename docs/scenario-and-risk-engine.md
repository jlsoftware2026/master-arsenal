# Scenario and hypothetical risk-sizing engine

## Price scenarios

`report_engine/scenarios.py` implements deterministic long-only price scenario calculations from explicit caller-supplied assumptions:

- Reference entry price and invalidation price.
- Bull, base, and bear case prices.
- A rationale for each case and for thesis invalidation.
- Quote currency, analysis horizon, exact instrument key, and timezone-aware as-of timestamp.

The engine validates positive finite prices, requires invalidation below entry, and enforces bull ≥ base ≥ bear ordering. It calculates each scenario's simple price return, downside to invalidation, and bull/base reward-to-risk ratios.

It does not generate target prices, scenario probabilities, expected returns, forecasts, or trade instructions. Price-distance reward-to-risk excludes fees, taxes, slippage, liquidity, gap risk, and execution constraints. Scenario values are hypothetical inputs, not observed positions or orders.

## Cash-only hypothetical position sizing

`report_engine/position_sizing.py` calculates a maximum cash-only hypothetical size from explicit caller inputs:

- Exact instrument key and as-of timestamp.
- Available capital and quote currency.
- Entry and invalidation prices, with a rationale for each.
- Risk budget percentage and maximum capital allocation percentage.
- Entry/exit fee and slippage assumptions in basis points.

It computes risk per unit including the supplied fee/slippage assumptions, then caps units by both the risk budget and allocation ceiling. It uses no leverage and submits no order.

The result is an arithmetic planning estimate, not a recommended position. A stop/invalidation price is not guaranteed to execute; gaps, spread, liquidity, taxes, market impact, funding, custody costs, and exchange lot-size rules can change actual outcomes.

## Safeguards

- No probability or expected return is inferred.
- No entry, stop, capital amount, risk budget, or allocation cap is selected by the engine.
- No actual portfolio position is created or implied.
- Missing inputs fail validation rather than receiving silent defaults (except fee/slippage, which default to zero and are clearly recorded).
- The scenario calculator is long-only; the position-size calculator is cash-only and unlevered.

## Verification

Offline tests cover return arithmetic, reward-to-risk, ordering, invalid/zero/non-finite prices, explicit rationales, timestamp validation, precision handling, capital/risk caps, fees, slippage, and no-order semantics.
