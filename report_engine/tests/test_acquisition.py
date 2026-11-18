"""Offline tests for the report engine's UTC-day acquisition contract."""
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from binance_data_engine.client import PaginationMetadata
from binance_data_engine.models import Candle
from report_engine.acquisition import acquire_intraday_evidence

UTC = timezone.utc
CUTOFF = datetime(2024, 5, 7, 3, 0, tzinfo=UTC)
START = datetime(2024, 5, 6, 4, 0, tzinfo=UTC)

def candles_for(symbol, omit=(), misalign=()):
    result = []
    for index in range(23):
        if index in omit:
            continue
        opened = START + timedelta(hours=index)
        if index in misalign:
            opened += timedelta(minutes=1)
        price = Decimal("100") + index
        result.append(Candle(
            symbol=symbol, interval="1h", open_time=opened,
            close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
            open=price, high=price + 1, low=price - 1, close=price,
            volume=Decimal("10"),
        ))
    return result

class FakeClient:
    def __init__(self, omit=None, misalign=None, complete=True, server_time=None,
                 metadata_mismatch=False):
        self.omit = omit or {}
        self.misalign = misalign or {}
        self.complete = complete
        self.metadata_mismatch = metadata_mismatch
        self.server_time = server_time or datetime(2024, 5, 7, 4, 0, tzinfo=UTC)
        self.last_response_metadata = {}
    def get_server_time(self, market):
        return self.server_time
    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        if end <= START:
            rows = []
            for index in range(250):
                opened = start + timedelta(hours=index)
                price = Decimal("100") + index
                rows.append(Candle(
                    symbol=symbol, interval=interval, open_time=opened,
                    close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
                    open=price, high=price + 1, low=price - 1, close=price,
                    volume=Decimal("10"),
                ))
        else:
            rows = candles_for(symbol, self.omit.get(symbol, ()), self.misalign.get(symbol, ()))
        self.last_response_metadata = {
            "http_status": 200, "retrieved_at_utc": "2024-05-07T03:01:00Z"
        }
        return rows, PaginationMetadata(
            pages=1, returned=len(rows) + int(self.metadata_mismatch), requested_start=start.isoformat(),
            requested_end=end.isoformat(), complete=self.complete,
        )
    def get_24h_ticker(self, symbol, market):
        self.last_response_metadata = {
            "http_status": 200, "retrieved_at_utc": "2024-05-07T03:02:00Z"
        }
        return {"symbol": symbol, "priceChangePercent": "1.0"}

class IntradayAcquisitionTests(unittest.TestCase):
    def acquire(self, client=None, cutoff=CUTOFF, symbols=("BTCUSDT", "ETHUSDT")):
        context = {"macro_context": "No macro items.", "news": "No news items.",
                   "macro_sources": [], "news_sources": [], "context_status": "complete",
                   "context_limitations": "Fixture context only."}
        with patch("report_engine.acquisition.collect_market_context", return_value=context):
            return acquire_intraday_evidence(client or FakeClient(), cutoff, "1h", "spot", symbols)

    def test_complete_window_and_provenance(self):
        report = self.acquire()
        self.assertEqual(report["data_status"], "partial")
        self.assertEqual(report["window_start_utc"], "2024-05-06T04:00:00Z")
        self.assertEqual(report["cutoff_utc"], "2024-05-07T03:00:00Z")
        summary = " ".join(report["executive_summary"])
        self.assertEqual(len(report["executive_summary"]), 7)
        self.assertIn("2024-05-06", summary)
        self.assertIn("2024-05-06T23:00:00-04:00", summary)
        self.assertEqual(set(report["symbols"]), {"BTCUSDT", "ETHUSDT"})
        btc = report["symbols"]["BTCUSDT"]
        self.assertEqual(btc["candle_count"], 23)
        self.assertEqual(btc["expected_candle_count"], 23)
        self.assertEqual(btc["ticker_24h"]["status"], "ok")
        self.assertEqual(btc["response_metadata"]["candles"]["http_status"], 200)
        self.assertEqual(btc["indicator_history"]["candle_count"], 250)
        self.assertIsNotNone(btc["indicators"]["ema_200"])
        self.assertEqual(len(report["provenance"]), 2)

    def test_missing_candle_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expected 23 candles, received 22"):
            self.acquire(FakeClient(omit={"BTCUSDT": (1,)}))

    def test_misaligned_candle_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "misaligned"):
            self.acquire(FakeClient(misalign={"ETHUSDT": (1,)}))

    def test_incomplete_pagination_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "pagination is incomplete or inconsistent"):
            self.acquire(FakeClient(complete=False))

    def test_pagination_count_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "pagination is incomplete or inconsistent"):
            self.acquire(FakeClient(metadata_mismatch=True))

    def test_unaligned_cutoff_is_preserved_and_final_interval_excluded(self):
        requested = CUTOFF + timedelta(minutes=30)
        report = self.acquire(cutoff=requested)
        self.assertEqual(report["cutoff_utc"], requested.isoformat().replace("+00:00", "Z"))
        self.assertEqual(report["data_cutoff_utc"], CUTOFF.isoformat().replace("+00:00", "Z"))
        self.assertEqual(report["symbols"]["BTCUSDT"]["candle_count"], 23)

    def test_future_cutoff_rejected(self):
        client = FakeClient(server_time=datetime(2024, 5, 7, 2, 59, tzinfo=UTC))
        with self.assertRaisesRegex(ValueError, "later than Binance server time"):
            self.acquire(client)

    def test_core_symbols_are_mandatory(self):
        with self.assertRaisesRegex(ValueError, "ETHUSDT"):
            self.acquire(symbols=("BTCUSDT",))

    def test_non_utc_cutoff_rejected(self):
        local = CUTOFF.replace(tzinfo=timezone(timedelta(hours=-4)))
        with self.assertRaisesRegex(ValueError, "UTC"):
            self.acquire(cutoff=local)

if __name__ == "__main__":
    unittest.main()
