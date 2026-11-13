"""MASTER ARSENAL public read-only Binance data engine."""
from .client import BinanceAPIError, BinancePublicClient, PaginationMetadata
from .engine import CORE_SYMBOLS, analyze_candles, build_snapshot
from .models import Candle, ValidationIssue, utc_datetime
from .validation import interval_milliseconds, require_valid_candles, validate_candles
__version__="0.2.0"
__all__=["BinanceAPIError","BinancePublicClient","PaginationMetadata","CORE_SYMBOLS",
         "analyze_candles","build_snapshot","Candle","ValidationIssue","utc_datetime",
         "interval_milliseconds","require_valid_candles","validate_candles"]
