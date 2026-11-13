import json
import unittest
from datetime import timezone
from email.message import Message
from io import BytesIO
from binance_data_engine.client import BinanceAPIError,BinancePublicClient

def row(open_ms,close_ms,price="100"):
    return [open_ms,price,"105","95",price,"12",close_ms,"1200",5,"6","600","0"]

class FakeResponse:
    def __init__(self,payload,headers=None,status=200):
        self.payload=json.dumps(payload).encode(); self.headers=Message()
        for k,v in (headers or {}).items(): self.headers[k]=v
        self.status=status
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self): return self.payload

class ClientTests(unittest.TestCase):
    def test_malformed_kline_row_rejected(self):
        c=BinancePublicClient(opener=lambda *a,**k:FakeResponse([[0,"1","1","1","1","1"]]))
        with self.assertRaises(BinanceAPIError): c.get_klines("BTCUSDT","1m",1)
    def test_kline_parse_decimal_utc(self):
        c=BinancePublicClient(opener=lambda *a,**k:FakeResponse([row(0,59999)]))
        x=c.get_klines("btcusdt","1m",1)
        self.assertEqual(x[0].symbol,"BTCUSDT"); self.assertEqual(str(x[0].open),"100")
        self.assertEqual(x[0].open_time.tzinfo,timezone.utc)
    def test_historical_pagination_half_open(self):
        responses=iter([[row(0,59999),row(60000,119999)],[row(120000,179999)]])
        urls=[]
        def opener(req,timeout): urls.append(req.full_url); return FakeResponse(next(responses))
        c=BinancePublicClient(opener=opener)
        rows,meta=c.get_historical_klines("BTCUSDT","1m",0,180000,page_limit=2)
        self.assertEqual(len(rows),3); self.assertEqual(meta.pages,2); self.assertTrue(meta.complete)
        self.assertIn("endTime=179999",urls[0]); self.assertIn("startTime=120000",urls[1])
    def test_empty_page_complete(self):
        rows,meta=BinancePublicClient(opener=lambda *a,**k:FakeResponse([])).get_historical_klines("BTCUSDT","1m",0,60000)
        self.assertEqual(rows,[]); self.assertTrue(meta.complete)
    def test_futures_chunks_200_days(self):
        urls=[]
        def opener(req,timeout): urls.append(req.full_url); return FakeResponse([])
        c=BinancePublicClient(opener=opener)
        end=201*24*60*60*1000
        rows,meta=c.get_historical_klines("BTCUSDT","1d",0,end,market="usdm")
        self.assertEqual(meta.pages,2)
        self.assertIn("endTime=17279999999",urls[0]); self.assertIn("startTime=17280000000",urls[1])
    def test_spot_limit_max(self):
        with self.assertRaises(ValueError): BinancePublicClient().get_klines("BTCUSDT",limit=1001)
    def test_futures_limit_1500(self):
        c=BinancePublicClient(opener=lambda *a,**k:FakeResponse([]))
        self.assertEqual(c.get_klines("BTCUSDT",limit=1500,market="usdm"),[])
    def test_invalid_market(self):
        with self.assertRaises(ValueError): BinancePublicClient().get_klines("BTCUSDT",market="bad")
    def test_retry_transient_http(self):
        class Opener:
            calls=0
            def __call__(self,req,timeout):
                self.calls+=1
                if self.calls==1:
                    from urllib.error import HTTPError
                    raise HTTPError(req.full_url,503,"down",Message(),BytesIO(b'{"msg":"retry"}'))
                return FakeResponse({"serverTime":0})
        op=Opener(); sleeps=[]
        c=BinancePublicClient(opener=op,sleep=sleeps.append,backoff_seconds=.01)
        self.assertEqual(c.get_server_time().year,1970); self.assertEqual(op.calls,2); self.assertEqual(sleeps,[.01])
    def test_non_retryable_http_fails_fast(self):
        def op(req,timeout):
            from urllib.error import HTTPError
            raise HTTPError(req.full_url,400,"bad",Message(),BytesIO(b'{"msg":"bad"}'))
        with self.assertRaises(BinanceAPIError):
            BinancePublicClient(opener=op,sleep=lambda _:self.fail("retry")).get_server_time()
    def test_24h_ticker_futures_path(self):
        urls=[]
        def op(req,timeout): urls.append(req.full_url); return FakeResponse({"symbol":"BTCUSDT"})
        BinancePublicClient(opener=op).get_24h_ticker("BTCUSDT","usdm")
        self.assertIn("fapi.binance.com/fapi/v1/ticker/24hr",urls[0])

if __name__=="__main__": unittest.main()
