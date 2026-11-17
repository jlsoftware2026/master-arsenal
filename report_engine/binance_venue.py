"""Read-only Binance Spot product discovery for investment-candidate venue checks."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from binance_data_engine.client import BinancePublicClient

BINANCE_SPOT_EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class BinanceSpotProductVerifier:
    """Verify exact crypto Spot products on Binance using public exchange metadata."""

    def __init__(self, client: Any | None = None):
        self.client = client or BinancePublicClient()

    def verify_spot_product(
        self,
        candidate: Mapping[str, Any],
        *,
        retrieved_at: datetime | None = None,
    ) -> dict[str, Any]:
        if not isinstance(candidate, Mapping):
            raise ValueError("candidate must be an instrument mapping")
        asset_class = candidate.get("asset_class")
        if asset_class in {"listed_equity", "tokenized_equity"}:
            reason = (
                "A listed share is not treated as a Binance Spot product."
                if asset_class == "listed_equity"
                else (
                    "A ticker-only Spot product match cannot establish the exact token contract, "
                    "issuer relationship, or rights for tokenized equity; use separately sourced venue evidence."
                )
            )
            return {"status": "not_verified", "venue": "Binance", "reason": reason}
        if asset_class != "crypto":
            raise ValueError("automatic Binance Spot verification is limited to crypto candidates")
        symbol = candidate.get("symbol")
        quote = candidate.get("quote_currency")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("candidate symbol is required")
        if not isinstance(quote, str) or not quote.strip():
            raise ValueError("candidate quote_currency is required")
        base_asset, quote_asset = symbol.strip().upper(), quote.strip().upper()
        expected_product_id = f"{base_asset}{quote_asset}"

        declared_venue = candidate.get("venue")
        if declared_venue is not None:
            if not isinstance(declared_venue, Mapping):
                raise ValueError("candidate venue must be a mapping")
            if str(declared_venue.get("name", "")).casefold() != "binance":
                raise ValueError("binance_spot_check conflicts with the candidate's declared venue")
            if str(declared_venue.get("market_type", "")).casefold() != "spot":
                raise ValueError("binance_spot_check requires market_type='spot'")
            if str(declared_venue.get("product_id", "")).upper() != expected_product_id:
                raise ValueError("declared Binance product_id does not match symbol and quote_currency")

        observed = retrieved_at or datetime.now(timezone.utc)
        observed_iso = _utc_iso(observed)
        try:
            payload = self.client.get_exchange_info("spot")
        except Exception as exc:
            return {
                "status": "not_verified",
                "venue": "Binance",
                "observed_at_utc": observed_iso,
                "source_url": BINANCE_SPOT_EXCHANGE_INFO_URL,
                "reason": f"Binance Spot product metadata could not be retrieved ({type(exc).__name__}).",
            }
        if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
            return {
                "status": "not_verified",
                "venue": "Binance",
                "observed_at_utc": observed_iso,
                "source_url": BINANCE_SPOT_EXCHANGE_INFO_URL,
                "reason": "Binance returned an unexpected exchangeInfo structure.",
            }

        matches = [
            item for item in payload["symbols"]
            if isinstance(item, dict)
            and str(item.get("symbol", "")).upper() == expected_product_id
            and str(item.get("baseAsset", "")).upper() == base_asset
            and str(item.get("quoteAsset", "")).upper() == quote_asset
        ]
        base = {
            "venue": "Binance",
            "product_id": expected_product_id,
            "market_type": "spot",
            "observed_at_utc": observed_iso,
            "source_url": BINANCE_SPOT_EXCHANGE_INFO_URL,
        }
        if not matches:
            return {
                "status": "unavailable",
                **base,
                "reason": "No exact Binance Spot product matched the supplied base and quote assets at retrieval time.",
            }
        if len(matches) != 1:
            return {
                "status": "not_verified",
                **base,
                "reason": "Binance exchangeInfo returned multiple exact product records.",
            }

        product = matches[0]
        product_status = product.get("status")
        spot_allowed = product.get("isSpotTradingAllowed")
        if product_status != "TRADING":
            return {
                "status": "unavailable",
                **base,
                "reason": f"Exact Binance Spot product exists but status is {product_status!r}, not TRADING.",
            }
        if not isinstance(spot_allowed, bool):
            return {
                "status": "not_verified",
                **base,
                "reason": "Binance did not provide a boolean isSpotTradingAllowed field.",
            }
        if not spot_allowed:
            return {
                "status": "unavailable",
                **base,
                "reason": "Exact Binance product is not enabled for Spot trading.",
            }
        return {
            "status": "verified",
            **base,
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "product_status": product_status,
            "is_spot_trading_allowed": True,
            "evidence_note": (
                "Exact base/quote product was present in Binance Spot exchangeInfo with status TRADING "
                "and isSpotTradingAllowed=true. This does not establish account eligibility or liquidity."
            ),
        }
