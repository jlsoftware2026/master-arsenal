import unittest
from binance_data_engine.indicators import atr,bollinger,ema,macd,rsi,sma

class IndicatorTests(unittest.TestCase):
    def test_ema_seed_and_warmup(self):
        x=ema([1,2,3,4,5],3)
        self.assertEqual(x[:2],[None,None]); self.assertAlmostEqual(x[2],2.0)
    def test_rsi_rising(self):
        x=rsi(list(range(20)),14)
        self.assertIsNone(x[13]); self.assertAlmostEqual(x[14],100.0)
    def test_macd_outputs(self):
        x=macd(list(range(80)))
        self.assertEqual(set(x),{"macd","signal","histogram"}); self.assertIsNotNone(x["histogram"][-1])
    def test_atr_wilder_smoothing(self):
        x=atr([10,12,13,15],[8,9,10,12],[9,11,12,14],2)
        self.assertIsNone(x[0]); self.assertIsNotNone(x[-1])
    def test_bollinger_sma_warmup(self):
        self.assertIsNone(sma([1,2,3],4)[-1])
        self.assertIsNone(bollinger([1,2,3],4)["middle"][-1])

if __name__=="__main__": unittest.main()
