import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from binance_data_engine.models import Candle,utc_datetime
from binance_data_engine.validation import validate_candles

def candle(minute,high=105):
    t=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=minute)
    return Candle("BTCUSDT","1m",t,t+timedelta(minutes=1)-timedelta(milliseconds=1),
                  Decimal("100"),Decimal(str(high)),Decimal("95"),Decimal("102"),Decimal("10"))

class ModelValidationTests(unittest.TestCase):
    def test_naive_datetime_normalized(self):
        self.assertEqual(utc_datetime(datetime(2026,1,1)).utcoffset(),timedelta(0))
    def test_unix_milliseconds_normalized(self):
        self.assertEqual(utc_datetime(0),datetime(1970,1,1,tzinfo=timezone.utc))
    def test_valid_candles(self):
        self.assertFalse([x for x in validate_candles([candle(0),candle(1)],"1m") if x.severity=="error"])
    def test_invalid_ohlc(self):
        self.assertIn("invalid_high",[x.code for x in validate_candles([candle(0,99)],"1m")])
    def test_duplicate_time(self):
        self.assertIn("non_increasing_time",[x.code for x in validate_candles([candle(0),candle(0)],"1m")])
    def test_non_utc_offset_rejected(self):
        t=datetime(2026,1,1,tzinfo=timezone(timedelta(hours=2)))
        c=Candle("BTCUSDT","1m",t,t+timedelta(minutes=1)-timedelta(milliseconds=1),
                 Decimal("100"),Decimal("105"),Decimal("95"),Decimal("102"),Decimal("10"))
        self.assertIn("non_utc_timestamp",[x.code for x in validate_candles([c],"1m")])
    def test_cadence_gap(self):
        self.assertIn("cadence_gap",[x.code for x in validate_candles([candle(0),candle(3)],"1m")])

if __name__=="__main__": unittest.main()
