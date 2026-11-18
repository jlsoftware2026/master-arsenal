"""Tests for read-only Binance Spot product verification."""
from datetime import datetime, timezone
import unittest

from report_engine.binance_venue import (
    BINANCE_SPOT_EXCHANGE_INFO_URL,
    BinanceSpotProductVerifier,
)

NOW = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)


class FakeBinanceClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def get_exchange_info(self, market):
        self.calls.append(market)
        if self.error:
            raise self.error
        return self.payload


def candidate(**overrides):
    value = {
        "asset_class": "crypto",
        "name": "Bitcoin",
        "symbol": "BTC",
        "quote_currency": "USDT",
    }
    value.update(overrides)
    return value


def product(**overrides):
    value = {
        "symbol": "BTCUSDT",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "status": "TRADING",
        "isSpotTradingAllowed": True,
    }
    value.update(overrides)
    return value


class BinanceSpotVerifierTests(unittest.TestCase):
    def test_verifies_exact_trading_spot_product(self):
        client = FakeBinanceClient({"symbols": [product()]})
        result = BinanceSpotProductVerifier(client).verify_spot_product(
            candidate(), retrieved_at=NOW
        )
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["venue"], "Binance")
        self.assertEqual(result["product_id"], "BTCUSDT")
        self.assertEqual(result["market_type"], "spot")
        self.assertEqual(result["observed_at_utc"], "2026-11-17T16:00:00Z")
        self.assertEqual(result["source_url"], BINANCE_SPOT_EXCHANGE_INFO_URL)
        self.assertEqual(client.calls, ["spot"])

    def test_tokenized_equity_requires_contract_and_rights_evidence_beyond_ticker_match(self):
        client = FakeBinanceClient({"symbols": [product(
            symbol="AAPLXUSDT", baseAsset="AAPLX"
        )]})
        result = BinanceSpotProductVerifier(client).verify_spot_product(
            candidate(
                asset_class="tokenized_equity", name="Tokenized Example Share",
                symbol="AAPLX", quote_currency="USDT",
                underlying_issuer="Example Inc", underlying_symbol="EXM",
                product_issuer="Token Provider", rights_summary="Contractual exposure",
                redemption_terms="No direct redemption",
            ),
            retrieved_at=NOW,
        )
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("exact token contract", result["reason"])
        self.assertEqual(client.calls, [])

    def test_listed_equity_is_not_misclassified_as_binance_spot(self):
        client = FakeBinanceClient({"symbols": [product()]})
        result = BinanceSpotProductVerifier(client).verify_spot_product(
            candidate(asset_class="listed_equity"), retrieved_at=NOW
        )
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("listed share", result["reason"])
        self.assertEqual(client.calls, [])

    def test_missing_exact_product_is_unavailable(self):
        client = FakeBinanceClient({"symbols": [product(symbol="BTCBUSD", quoteAsset="BUSD")]})
        result = BinanceSpotProductVerifier(client).verify_spot_product(
            candidate(), retrieved_at=NOW
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("No exact", result["reason"])

    def test_non_trading_product_is_unavailable(self):
        client = FakeBinanceClient({"symbols": [product(status="HALT") ]})
        result = BinanceSpotProductVerifier(client).verify_spot_product(
            candidate(), retrieved_at=NOW
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("not TRADING", result["reason"])

    def test_spot_permission_must_be_explicitly_true(self):
        record = product()
        record.pop("isSpotTradingAllowed")
        client = FakeBinanceClient({"symbols": [record]})
        result = BinanceSpotProductVerifier(client).verify_spot_product(
            candidate(), retrieved_at=NOW
        )
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("boolean", result["reason"])

    def test_api_failure_is_not_reported_as_product_unavailable(self):
        client = FakeBinanceClient(error=TimeoutError("network timeout"))
        result = BinanceSpotProductVerifier(client).verify_spot_product(
            candidate(), retrieved_at=NOW
        )
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("could not be retrieved", result["reason"])

    def test_malformed_exchange_info_is_not_verified(self):
        client = FakeBinanceClient({"symbols": "not-a-list"})
        result = BinanceSpotProductVerifier(client).verify_spot_product(
            candidate(), retrieved_at=NOW
        )
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("unexpected", result["reason"])

    def test_declared_product_identity_must_match_candidate(self):
        client = FakeBinanceClient({"symbols": [product()]})
        with self.assertRaisesRegex(ValueError, "does not match"):
            BinanceSpotProductVerifier(client).verify_spot_product(
                candidate(venue={
                    "name": "Binance", "product_id": "BTCBUSD", "market_type": "spot"
                }),
                retrieved_at=NOW,
            )

    def test_naive_retrieval_time_is_rejected(self):
        client = FakeBinanceClient({"symbols": [product()]})
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            BinanceSpotProductVerifier(client).verify_spot_product(
                candidate(), retrieved_at=datetime(2026, 11, 17, 16, 0)
            )


if __name__ == "__main__":
    unittest.main()
