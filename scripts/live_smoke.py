"""Opt-in live smoke test for public Binance endpoints; read-only and low volume."""
from __future__ import annotations
import argparse
import sys
from binance_data_engine import BinancePublicClient, validate_candles

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--market",choices=("spot","usdm","both"),default="both")
    args=parser.parse_args()
    markets=("spot","usdm") if args.market=="both" else (args.market,)
    client=BinancePublicClient(timeout=10,retries=1)
    failures=[]
    for market in markets:
        try:
            server=client.get_server_time(market)
            print(f"{market}: server time OK {server.isoformat()}")
            for symbol in ("BTCUSDT","ETHUSDT"):
                candles=client.get_klines(symbol,"1h",5,market)
                if len(candles)!=5:
                    raise RuntimeError(f"{market} {symbol}: expected 5 candles, received {len(candles)}")
                errors=[x for x in validate_candles(candles,"1h") if x.severity=="error"]
                if errors:
                    raise RuntimeError(f"{market} {symbol}: invalid candle data: {errors}")
                ticker=client.get_24h_ticker(symbol,market)
                print(f"{market} {symbol}: 5 candles and 24h ticker OK; latest close={candles[-1].close}")
            if market=="usdm":
                for symbol in ("BTCUSDT","ETHUSDT"):
                    client.get_premium_index(symbol)
                    client.get_open_interest(symbol)
                    print(f"{market} {symbol}: premium index and current open interest OK")
        except Exception as exc:
            failures.append(f"{market}: {type(exc).__name__}: {exc}")
    if failures:
        print("LIVE SMOKE TEST FAILED:")
        for item in failures: print(f"- {item}")
        return 1
    print("LIVE SMOKE TEST PASSED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
