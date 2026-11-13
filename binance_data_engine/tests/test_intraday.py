"""Offline tests for strict UTC-day Binance acquisition."""
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from binance_data_engine.client import PaginationMetadata
from binance_data_engine.intraday import acquire_intraday_day
from binance_data_engine.models import Candle

UTC = timezone.utc
DAY = date(2026, 11, 13)
START = datetime(2026, 11, 13, 0, 0, tzinfo=UTC)
CUTOFF = datetime(2026, 11, 13, 3, 0, tzinfo=UTC)

def make_candles(symbol, count=3, omit=()):
    rows = []
    for index in range(count):
        if index in omit:
            continue
        opened = START + timedelta(hours=index)
        price = Decimal("100") + index
        rows.append(Candle(
            symbol=symbol, interval="1h", open_time=opened,
            close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
            open=price, high=price + 1, low=price - 1, close=price,
            volume=Decimal("10"),
        ))
    return rows

class FakeClient:
    def __init__(self, omit=None, incomplete=False, server_time=None):
        self.omit = omit or {}
        self.incomplete = incomplete
        self.server_time = server_time or datetime(2026, 11, 13, 4, 0, tzinfo=UTC)
        self.last_response_metadata = {}
    def get_server_time(self, market):
        return self.server_time
    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        rows = make_candles(symbol, omit=self.omit.get(symbol, ()))
        self.last_response_metadata = {"http_status": 200, "retrieved_at_utc": "2026-11-13T03:01:00Z"}
        metadata = PaginationMetadata(
            pages=1, returned=len(rows), requested_start=start.isoformat(),
            requested_end=end.isoformat(), complete=not self.incomplete,
        )
        return rows, metadata
    def get_24h_ticker(self, symbol, market):
        self.last_response_metadata = {"http_status": 200, "retrieved_at_utc": "2026-11-13T03:02:00Z"}
        return {"symbol": symbol, "priceChangePercent": "1.0"}

class IntradayAcquisitionTests(unittest.TestCase):
    def acquire(self, client=None, **kwargs):
        return acquire_intraday_day(
            client or FakeClient(), DAY, CUTOFF, interval="1h",
            symbols=("BTCUSDT", "ETHUSDT"), **kwargs
        )

    def test_returns_complete_btc_eth_evidence(self):
        report = self.acquire()
        self.assertEqual(report["data_status"], "complete")
        self.assertEqual(report["window_start_utc"], "2026-11-13T00:00:00Z")
        self.assertEqual(report["cutoff_utc"], "2026-11-13T03:00:00Z")
        self.assertEqual(set(report["symbols"]), {"BTCUSDT", "ETHUSDT"})
        self.assertEqual(report["symbols"]["BTCUSDT"]["candle_count"], 3)
        self.assertEqual(report["symbols"]["BTCUSDT"]["pagination"]["returned"], 3)
        self.assertEqual(report["symbols"]["BTCUSDT"]["ticker_24h"]["status"], "ok")
        self.assertEqual(len(report["provenance"]), 2)

    def test_missing_candle_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.acquire(FakeClient(omit={"BTCUSDT": (1,)}))

    def test_incomplete_pagination_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pagination did not complete"):
            self.acquire(FakeClient(incomplete=True))

    def test_unaligned_cutoff_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "align"):
            acquire_intraday_day(
                FakeClient(), DAY, CUTOFF + timedelta(minutes=30), "1h",
                symbols=("BTCUSDT", "ETHUSDT")
            )

    def test_future_cutoff_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "later than Binance server time"):
            self.acquire(FakeClient(server_time=datetime(2026, 11, 13, 2, 59, tzinfo=UTC)))

    def test_missing_core_symbol_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ETHUSDT"):
            acquire_intraday_day(FakeClient(), DAY, CUTOFF, "1h", symbols=("BTCUSDT",))

    def test_wrong_date_or_non_utc_cutoff_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "report_date"):
            acquire_intraday_day(FakeClient(), date(2026, 11, 12), CUTOFF, "1h",
                                 symbols=("BTCUSDT", "ETHUSDT"))
        with self.assertRaisesRegex(ValueError, "UTC"):
            acquire_intraday_day(
                FakeClient(), DAY, datetime(2026, 11, 13, 3, 0,
                                            tzinfo=timezone(timedelta(hours=-4))),
                "1h", symbols=("BTCUSDT", "ETHUSDT")
            )

if __name__ == "__main__":
    unittest.main()
