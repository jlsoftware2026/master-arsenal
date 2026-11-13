"""Offline tests for the report engine's UTC-day acquisition contract."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from binance_data_engine.client import PaginationMetadata
from binance_data_engine.models import Candle
from report_engine.acquisition import acquire_intraday_evidence

UTC = timezone.utc
CUTOFF = datetime(2024, 5, 7, 3, 0, tzinfo=UTC)
START = CUTOFF.replace(hour=0)

def candles_for(symbol, omit=(), misalign=()):
    result = []
    for index in range(3):
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
    def __init__(self, omit=None, misalign=None, complete=True, server_time=None):
        self.omit = omit or {}
        self.misalign = misalign or {}
        self.complete = complete
        self.server_time = server_time or datetime(2024, 5, 7, 4, 0, tzinfo=UTC)
        self.last_response_metadata = {}
    def get_server_time(self, market):
        return self.server_time
    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        rows = candles_for(symbol, self.omit.get(symbol, ()), self.misalign.get(symbol, ()))
        self.last_response_metadata = {
            "http_status": 200, "retrieved_at_utc": "2024-05-07T03:01:00Z"
        }
        return rows, PaginationMetadata(
            pages=1, returned=len(rows), requested_start=start.isoformat(),
            requested_end=end.isoformat(), complete=self.complete,
        )
    def get_24h_ticker(self, symbol, market):
        self.last_response_metadata = {
            "http_status": 200, "retrieved_at_utc": "2024-05-07T03:02:00Z"
        }
        return {"symbol": symbol, "priceChangePercent": "1.0"}

class IntradayAcquisitionTests(unittest.TestCase):
    def acquire(self, client=None, cutoff=CUTOFF, symbols=("BTCUSDT", "ETHUSDT")):
        return acquire_intraday_evidence(client or FakeClient(), cutoff, "1h", "spot", symbols)

    def test_complete_window_and_provenance(self):
        report = self.acquire()
        self.assertEqual(report["data_status"], "complete")
        self.assertEqual(report["window_start_utc"], "2024-05-07T00:00:00Z")
        self.assertEqual(report["cutoff_utc"], "2024-05-07T03:00:00Z")
        self.assertEqual(set(report["symbols"]), {"BTCUSDT", "ETHUSDT"})
        btc = report["symbols"]["BTCUSDT"]
        self.assertEqual(btc["candle_count"], 3)
        self.assertEqual(btc["expected_candle_count"], 3)
        self.assertEqual(btc["ticker_24h"]["status"], "ok")
        self.assertEqual(btc["response_metadata"]["http_status"], 200)
        self.assertEqual(len(report["provenance"]), 2)

    def test_missing_candle_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expected 3 candles, received 2"):
            self.acquire(FakeClient(omit={"BTCUSDT": (1,)}))

    def test_misaligned_candle_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "misaligned"):
            self.acquire(FakeClient(misalign={"ETHUSDT": (1,)}))

    def test_incomplete_pagination_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "pagination did not complete"):
            self.acquire(FakeClient(complete=False))

    def test_cutoff_must_align_to_interval(self):
        with self.assertRaisesRegex(ValueError, "align exactly"):
            self.acquire(cutoff=CUTOFF + timedelta(minutes=30))

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
