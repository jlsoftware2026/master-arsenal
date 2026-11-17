# Instrument identity and venue verification contract

## Purpose

Every investment candidate must have an unambiguous identity before fundamental research, market analysis, scenario calculations, or venue-availability claims are attached to it. A ticker symbol alone is not a unique instrument identifier.

The implementation lives in `report_engine/instruments.py` and is intentionally deterministic and network-free. It validates candidate identity and supplied venue evidence; it does not itself query an exchange or claim that a product is currently listed.

## Supported asset classes

### Listed equity

Required fields: `asset_class`, `name`, `symbol`, `quote_currency`, `issuer`, and `exchange`.

Optional `security_type` defaults to `common_stock`. Listed equities cannot declare a token network or contract address.

### Tokenized equity

Required fields: `asset_class`, `name`, `symbol`, `quote_currency`, `underlying_issuer`, `underlying_symbol`, `product_issuer`, `rights_summary`, and `redemption_terms`.

Network and contract address are optional. The tokenized product is a distinct instrument from the underlying listed security. The identity record preserves both the product issuer and underlying issuer, plus the stated rights/redemption terms; it does not infer ownership, voting, dividends, or redemption rights.

### Cryptocurrency/token

Required fields: `asset_class`, `name`, `symbol`, and `quote_currency`.

Network, contract address, and protocol are optional to support native assets as well as contract-based tokens. Where a network and contract are supplied, the contract is normalized to lowercase.

## Venue identity

A candidate may declare a venue object with exact `name`, `product_id`, and `market_type`. The product identifier is venue-specific; it is not inferred from the ticker.

The venue evidence validator accepts three states:

- `verified`: requires an HTTPS source URL, timezone-aware observation timestamp, venue name, exact product ID, and market type. Evidence must match the candidate's declared venue identity and be no older than the configured maximum age (24 hours by default).
- `unavailable`: requires an HTTPS source URL, timestamp, and reason.
- `not_verified`: indicates missing or insufficient evidence. It is the default when no evidence is supplied.

Future-dated, stale, or mismatched evidence is downgraded to `not_verified`. A matching ticker without an exact venue/product/market-type match is not sufficient.

## Current implementation boundary

This is a validation contract, not a live exchange adapter. A later provider adapter must retrieve the venue's authoritative product metadata, retain the exact source URL and observation timestamp, and pass the evidence into this validator. Until that adapter exists and has been exercised, reports must say venue availability is **not verified**. They must not treat this validator's ability to validate supplied evidence as proof that a venue was queried.

## Safety and analytical boundaries

- Listed equity, tokenized equity, and crypto remain separate asset classes.
- No private account access, credential storage, order placement, or trading is introduced.
- Venue availability does not imply suitability, liquidity, legal eligibility, or investment merit.
- Instrument identity is necessary but not sufficient for an investment conclusion.
