# Binance Spot product verification

## Purpose and boundary

`report_engine/binance_venue.py` provides an optional, public read-only check of whether an exact crypto or tokenized-equity product is present and enabled for Spot trading on Binance. It uses the existing `BinancePublicClient.get_exchange_info("spot")` adapter and the public `/api/v3/exchangeInfo` endpoint. No API key, private account endpoint, balance access, or order endpoint is used.

The opportunity job opts in with:

`binance_spot_check: true`

This option is mutually exclusive with caller-supplied `venue_evidence`. The candidate's exact base symbol and quote currency are matched against the response's `symbol`, `baseAsset`, and `quoteAsset`. A product is verified only when exactly one record matches, `status == "TRADING"`, and `isSpotTradingAllowed == true`.

## Outcomes

- `verified`: exact product metadata matches and Spot trading is enabled. The report records the product ID, base/quote assets, exchange status, observation timestamp, and source URL.
- `unavailable`: the exact product is absent, not in `TRADING` status, or Spot trading is explicitly disabled at retrieval time.
- `not_verified`: request failure, malformed response, ambiguous records, missing Spot-permission metadata, or an asset class that must not be represented as a Binance Spot product.

A failed metadata request is not interpreted as proof that the product is unlisted. The check does not establish the user's account eligibility, jurisdictional access, order-book depth, liquidity, custody, suitability, or investment merit.

## Asset-class controls

- Listed equity is not checked as if a stock share were a Binance Spot product. The resolver returns `not_verified` with an explicit explanation.
- Tokenized equity checks the token product symbol, not the underlying listed share. A verified token listing does not establish ownership, voting, dividend, redemption, or other rights in the underlying issuer.
- Crypto checks the exact candidate base asset and quote currency. A matching ticker alone is insufficient.

## Testing

Offline fixtures cover exact product matches, tokenized-equity separation, listed-share rejection, missing products, non-trading products, missing Spot-permission fields, API failures, malformed responses, conflicting declared venue identity, and timezone-aware retrieval timestamps. Offline CI does not certify live Binance availability.
