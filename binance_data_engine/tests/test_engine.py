import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from binance_data_engine.engine import build_snapshot
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
    def test_snapshot_metadata_indicators(self):
        x=build_snapshot(FakeClient(),["BTCUSDT","ETHUSDT"],limit=250)
        self.assertEqual(set(x["symbols"]),{"BTCUSDT","ETHUSDT"})
        self.assertTrue(x["read_only"])
        self.assertIsNotNone(x["symbols"]["BTCUSDT"]["indicators"]["rsi_14"])
        self.assertEqual(x["symbols"]["BTCUSDT"]["ticker_24h"]["status"],"ok")

if __name__=="__main__": unittest.main()
