"""Tests for instrument identity and exact-product venue verification."""
from datetime import datetime, timedelta, timezone
import unittest

from report_engine.instruments import (
    build_instrument_record,
    normalize_instrument,
    validate_venue_evidence,
)

NOW = datetime(2026, 11, 17, 14, 0, tzinfo=timezone.utc)


class InstrumentIdentityTests(unittest.TestCase):
    def test_listed_equity_requires_issuer_and_exchange(self):
        record = normalize_instrument({
            "asset_class": "listed_equity", "name": "Example Corp",
            "symbol": "exm", "quote_currency": "usd",
            "issuer": "Example Corp", "exchange": "nasdaq",
        })
        self.assertEqual(record["asset_class"], "listed_equity")
        self.assertEqual(record["symbol"], "EXM")
        self.assertEqual(record["exchange"], "NASDAQ")
        self.assertIn("listed_equity|exm|usd", record["instrument_key"])

    def test_listed_equity_rejects_token_contract_fields(self):
        with self.assertRaisesRegex(ValueError, "must not declare"):
            normalize_instrument({
                "asset_class": "listed_equity", "name": "Example Corp",
                "symbol": "EXM", "quote_currency": "USD",
                "issuer": "Example Corp", "exchange": "NASDAQ",
                "network": "ethereum",
            })

    def test_tokenized_equity_requires_rights_and_distinct_issuers(self):
        record = normalize_instrument({
            "asset_class": "tokenized_equity", "name": "Example token",
            "symbol": "EXM.T", "quote_currency": "USD",
            "underlying_issuer": "Example Corp", "underlying_symbol": "EXM",
            "product_issuer": "Token Provider", "rights_summary": "Contractual exposure only",
            "redemption_terms": "No direct redemption right stated",
            "network": "Ethereum", "contract_address": "0xABCDEF",
        })
        self.assertEqual(record["asset_class"], "tokenized_equity")
        self.assertEqual(record["contract_address"], "0xabcdef")
        self.assertNotEqual(record["symbol"], record["underlying_symbol"])

    def test_crypto_identity_allows_native_asset_without_contract(self):
        record = normalize_instrument({
            "asset_class": "crypto", "name": "Bitcoin", "symbol": "btc",
            "quote_currency": "usdt", "network": "Bitcoin",
        })
        self.assertEqual(record["symbol"], "BTC")
        self.assertIsNone(record["contract_address"])

    def test_unknown_asset_class_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "asset_class"):
            normalize_instrument({
                "asset_class": "stock", "name": "Example", "symbol": "EXM",
                "quote_currency": "USD",
            })

    def test_missing_venue_evidence_is_not_verified(self):
        instrument = normalize_instrument({
            "asset_class": "crypto", "name": "Bitcoin", "symbol": "BTC",
            "quote_currency": "USDT",
            "venue": {"name": "Binance", "product_id": "BTCUSDT", "market_type": "spot"},
        })
        result = validate_venue_evidence(instrument, None, now=NOW)
        self.assertEqual(result["status"], "not_verified")


    def test_not_verified_venue_evidence_preserves_source_timestamp(self):
        candidate = {
            "asset_class": "crypto", "name": "Bitcoin", "symbol": "BTC",
            "quote_currency": "USDT",
        }
        evidence = {
            "status": "not_verified", "venue": "Binance",
            "observed_at_utc": "2026-11-17T13:30:00Z",
            "source_url": "https://api.binance.com/api/v3/exchangeInfo",
            "reason": "Binance metadata request failed.",
        }
        record = build_instrument_record(candidate, evidence, now=NOW)
        self.assertEqual(record["venue_verification"]["status"], "not_verified")
        self.assertEqual(record["venue_verification"]["observed_at_utc"], "2026-11-17T13:30:00Z")
        self.assertEqual(record["venue_verification"]["source_url"], evidence["source_url"])


    def test_exact_current_product_evidence_verifies(self):
        candidate = {
            "asset_class": "crypto", "name": "Bitcoin", "symbol": "BTC",
            "quote_currency": "USDT",
            "venue": {"name": "Binance", "product_id": "BTCUSDT", "market_type": "spot"},
        }
        evidence = {
            "status": "verified", "venue": "Binance", "product_id": "BTCUSDT",
            "market_type": "spot", "observed_at_utc": "2026-11-17T13:30:00Z",
            "source_url": "https://api.binance.com/api/v3/exchangeInfo",
            "evidence_note": "Exact symbol present with trading status verified.",
        }
        record = build_instrument_record(candidate, evidence, now=NOW)
        self.assertEqual(record["venue_verification"]["status"], "verified")
        self.assertEqual(record["venue_verification"]["product_id"], "BTCUSDT")

    def test_ticker_match_without_exact_product_match_is_not_verified(self):
        candidate = {
            "asset_class": "crypto", "name": "Bitcoin", "symbol": "BTC",
            "quote_currency": "USDT",
            "venue": {"name": "Binance", "product_id": "BTCUSDT", "market_type": "spot"},
        }
        evidence = {
            "status": "verified", "venue": "Binance", "product_id": "BTCUSD",
            "market_type": "spot", "observed_at_utc": "2026-11-17T13:30:00Z",
            "source_url": "https://api.binance.com/api/v3/exchangeInfo",
        }
        result = validate_venue_evidence(normalize_instrument(candidate), evidence, now=NOW)
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("does not match", result["reason"])

    def test_stale_evidence_does_not_verify_availability(self):
        candidate = {
            "asset_class": "crypto", "name": "Bitcoin", "symbol": "BTC",
            "quote_currency": "USDT",
            "venue": {"name": "Binance", "product_id": "BTCUSDT", "market_type": "spot"},
        }
        evidence = {
            "status": "verified", "venue": "Binance", "product_id": "BTCUSDT",
            "market_type": "spot", "observed_at_utc": "2026-11-16T13:30:00Z",
            "source_url": "https://api.binance.com/api/v3/exchangeInfo",
        }
        result = validate_venue_evidence(
            normalize_instrument(candidate), evidence, now=NOW,
            max_age=timedelta(hours=12),
        )
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("stale", result["reason"])

    def test_future_timestamp_does_not_verify_availability(self):
        candidate = {
            "asset_class": "crypto", "name": "Bitcoin", "symbol": "BTC",
            "quote_currency": "USDT",
            "venue": {"name": "Binance", "product_id": "BTCUSDT", "market_type": "spot"},
        }
        evidence = {
            "status": "verified", "venue": "Binance", "product_id": "BTCUSDT",
            "market_type": "spot", "observed_at_utc": "2026-11-17T14:01:00Z",
            "source_url": "https://api.binance.com/api/v3/exchangeInfo",
        }
        result = validate_venue_evidence(normalize_instrument(candidate), evidence, now=NOW)
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("future", result["reason"])

    def test_verified_evidence_requires_https_source(self):
        candidate = normalize_instrument({
            "asset_class": "crypto", "name": "Bitcoin", "symbol": "BTC",
            "quote_currency": "USDT",
            "venue": {"name": "Binance", "product_id": "BTCUSDT", "market_type": "spot"},
        })
        evidence = {
            "status": "verified", "venue": "Binance", "product_id": "BTCUSDT",
            "market_type": "spot", "observed_at_utc": "2026-11-17T13:30:00Z",
            "source_url": "http://example.com/products",
        }
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_venue_evidence(candidate, evidence, now=NOW)


if __name__ == "__main__":
    unittest.main()
