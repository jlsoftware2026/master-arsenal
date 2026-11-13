"""Orchestration for reproducible Binance market snapshots."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .client import BinancePublicClient
from .indicators import atr, bollinger, ema, macd, rsi, sma
from .validation import validate_candles

CORE_SYMBOLS = ("BTCUSDT", "ETHUSDT")

def _last(values):
    return values[-1] if values else None

def _capture(client, operation):
    try:
        value = operation()
        return {"status":"ok","data":value,"response_metadata":dict(client.last_response_metadata)}
    except Exception as exc:
        return {"status":"unavailable","error":f"{type(exc).__name__}: {exc}",
                "response_metadata":dict(client.last_response_metadata)}

def analyze_candles(candles) -> dict[str, Any]:
    closes=[x.close for x in candles]
    highs=[x.high for x in candles]
    lows=[x.low for x in candles]
    volumes=[x.volume for x in candles]
    m=macd(closes)
    bands=bollinger(closes)
    return {"ema_20":_last(ema(closes,20)),"ema_50":_last(ema(closes,50)),
            "ema_200":_last(ema(closes,200)),"rsi_14":_last(rsi(closes,14)),
            "macd":{k:_last(v) for k,v in m.items()},"atr_14":_last(atr(highs,lows,closes,14)),
            "bollinger_20":{k:_last(v) for k,v in bands.items()},
            "volume_sma_20":_last(sma(volumes,20)),
            "warmup_note":"Null means insufficient candles for the indicator warm-up."}

def build_snapshot(client: BinancePublicClient, symbols=CORE_SYMBOLS, interval: str="1h",
                   limit: int=250, market: str="spot", include_derivatives: bool=True):
    requested=[s.upper() for s in symbols]
    missing=[s for s in CORE_SYMBOLS if s not in requested]
    if missing: raise ValueError("Core symbols are mandatory and missing: "+", ".join(missing))
    if len(set(requested)) != len(requested): raise ValueError("symbols must be unique")
    server_time=client.get_server_time(market)
    result={"schema_version":"1.0","market":market,"interval":interval,"requested_limit":limit,
            "generated_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "binance_server_time_utc":server_time.isoformat().replace("+00:00","Z"),
            "source":"Binance public REST API","read_only":True,"symbols":{}}
    for symbol in requested:
        candles=client.get_klines(symbol,interval,limit,market)
        issues=validate_candles(candles,interval)
        result["symbols"][symbol]={
            "candles":[c.to_dict() for c in candles],"candle_count":len(candles),
            "first_open_time_utc":candles[0].open_time.isoformat().replace("+00:00","Z") if candles else None,
            "last_close_time_utc":candles[-1].close_time.isoformat().replace("+00:00","Z") if candles else None,
            "validation":[x.to_dict() for x in issues],"indicators":analyze_candles(candles),
            "response_metadata":dict(client.last_response_metadata),
            "ticker_24h":_capture(client,lambda:client.get_24h_ticker(symbol,market))}
        if include_derivatives and market=="usdm":
            pair=symbol.removesuffix("USDT")+"USDT"
            result["symbols"][symbol]["derivatives"]={
                "premium_index":_capture(client,lambda:client.get_premium_index(symbol)),
                "open_interest_current":_capture(client,lambda:client.get_open_interest(symbol)),
                "open_interest_history_1h":_capture(client,lambda:client.get_open_interest_history(symbol,"1h",30)),
                "funding_rate_history":_capture(client,lambda:client.get_funding_rate_history(symbol,100)),
                "global_long_short_account_ratio_1h":_capture(client,lambda:client.get_global_long_short_ratio(symbol,"1h",30)),
                "basis_1h":_capture(client,lambda:client.get_basis(pair,"PERPETUAL","1h",30)),
                "mark_price_klines":_capture(client,lambda:client.get_mark_price_klines(symbol,interval,min(limit,1500))),
                "index_price_klines":_capture(client,lambda:client.get_index_price_klines(pair,interval,min(limit,1500)))}
    return result
