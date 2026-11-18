# DeFiLlama protocol metrics adapter

## Provider and access model

The adapter in `report_engine/defillama.py` uses DeFiLlama's public free API at `https://api.llama.fi`, which the provider documents as requiring no API key for the selected endpoints.

It uses only:

- `/protocol/{slug}` for protocol metadata and TVL history.
- `/summary/fees/{slug}?dataType=dailyFees`
- `/summary/fees/{slug}?dataType=dailyRevenue`
- `/summary/fees/{slug}?dataType=dailyHoldersRevenue`

The adapter does not call paid API endpoints or the free yield endpoints that DeFiLlama retired in November 2026.

## Extracted metrics

- Latest valid protocol TVL observation from the protocol's TVL series.
- Latest daily fees series observation.
- Latest daily protocol revenue series observation.
- Latest daily token-holder revenue series observation.

Each metric retains the exact endpoint URL, source series reference, Unix observation timestamp converted to UTC, and retrieval timestamp. Fees, protocol revenue, and token-holder revenue remain separate metrics.

## Identity and attribution

The caller supplies an exact DeFiLlama protocol slug, instrument key, and an explicit `attribution_basis`. The adapter does not map a ticker to a protocol, infer that a token controls a protocol, or assume that protocol TVL/fees accrue to token holders. Its returned attribution status is explicitly caller-supplied and not independently verified.

## Interpretation limits

- TVL is not protocol revenue, token market capitalization, or token-holder value capture.
- Protocol fees, protocol revenue, and token-holder revenue are different economic measures.
- DeFiLlama aggregates third-party/on-chain sources and applies methodology and coverage choices. Analysts must inspect methodology and compare with primary protocol disclosures where material.
- Missing metrics are not zero. A metric may be absent because the provider does not cover the protocol or does not publish that series.
- The adapter does not provide token supply, unlock schedules, holder concentration, smart-contract audits, exploit history, governance quality, or regulatory analysis.
- Protocol-level data does not prove issuer ownership, token rights, or economic exposure.

## Verification

Offline tests use deterministic fixtures and an injected transport. They cover slug validation, exact protocol identity, TVL/fees/revenue extraction, missing metric behavior, and attribution safeguards. They do not certify live API availability or the methodology of any individual protocol.
