import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from binance_data_engine.engine import acquire_derivatives_context, build_snapshot
from binance_data_engine.models import Candle

class FakeClient:
    last_response_metadata={}
    def get_server_time(self,market): return datetime(2026,1,1,tzinfo=timezone.utc)
    def get_24h_ticker(self,symbol,market): return {"symbol":symbol,"priceChangePercent":"1"}
    def get_klines(self,symbol,interval,limit,market):
        out=[]; start=datetime(2026,1,1,tzinfo=timezone.utc)
        for i in range(250):
            t=start+timedelta(hours=i); p=Decimal(str(100+i))
            out.append(Candle(symbol,interval,t,t+timedelta(hours=1)-timedelta(milliseconds=1),
                              p,p+1,p-1,p,Decimal("10")))
        self.last_response_metadata={"http_status":200}
        return out

class EngineTests(unittest.TestCase):
    def test_btc_eth_required(self):
        with self.assertRaises(ValueError): build_snapshot(FakeClient(),["BTCUSDT"])

    def test_derivatives_context_captures_optional_futures_evidence(self):
        class FuturesClient:
            last_response_metadata = {"http_status": 200}
            def get_premium_index(self, symbol): return {"symbol": symbol}
            def get_open_interest(self, symbol): return {"symbol": symbol}
            def get_open_interest_history(self, symbol, period, limit): return [{"sumOpenInterest": "10"}]
            def get_funding_rate_history(self, symbol, limit): raise OSError("temporarily unavailable")
            def get_global_long_short_ratio(self, symbol, period, limit): return [{"longShortRatio": "1.2"}]
            def get_basis(self, pair, contract_type, period, limit): return [{"basis": "2"}]
            def get_mark_price_klines(self, symbol, interval, limit): return []
            def get_index_price_klines(self, pair, interval, limit): return []
        result = acquire_derivatives_context(FuturesClient(), "BTCUSDT", "1h")
        self.assertEqual(result["premium_index"]["status"], "ok")
        self.assertEqual(result["open_interest_current"]["status"], "ok")
        self.assertEqual(result["funding_rate_history"]["status"], "unavailable")
        self.assertIn("temporarily unavailable", result["funding_rate_history"]["error"])

    def test_snapshot_metadata_indicators(self):
        x=build_snapshot(FakeClient(),["BTCUSDT","ETHUSDT"],limit=250)
        self.assertEqual(set(x["symbols"]),{"BTCUSDT","ETHUSDT"})
        self.assertTrue(x["read_only"])
        self.assertIsNotNone(x["symbols"]["BTCUSDT"]["indicators"]["rsi_14"])
        self.assertEqual(x["symbols"]["BTCUSDT"]["ticker_24h"]["status"],"ok")

if __name__=="__main__": unittest.main()
