"""Command-line entry point."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .client import BinanceAPIError, BinancePublicClient
from .engine import CORE_SYMBOLS, build_snapshot

def build_parser():
    parser=argparse.ArgumentParser(prog="ma-binance",description="MASTER ARSENAL read-only Binance engine")
    sub=parser.add_subparsers(dest="command",required=True)
    snap=sub.add_parser("snapshot",help="fetch a market snapshot")
    snap.add_argument("--symbols",nargs="+",default=list(CORE_SYMBOLS))
    snap.add_argument("--interval",default="1h")
    snap.add_argument("--limit",type=int,default=250)
    snap.add_argument("--market",choices=("spot","usdm"),default="spot")
    snap.add_argument("--no-derivatives",action="store_true")
    snap.add_argument("--output",type=Path,default=Path("snapshot.json"))
    return parser

def main(argv=None):
    args=build_parser().parse_args(argv)
    try:
        payload=build_snapshot(BinancePublicClient(),args.symbols,args.interval,args.limit,args.market,
                               include_derivatives=not args.no_derivatives)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
        print(f"Snapshot written: {args.output} ({len(payload['symbols'])} symbols)")
        return 0
    except (BinanceAPIError,OSError,ValueError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
