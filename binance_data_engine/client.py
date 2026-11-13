"""Public read-only Binance REST client with bounded retries and pagination."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .models import Candle, decimal_value, utc_datetime

SPOT_BASE_URL = "https://data-api.binance.vision"
USDM_BASE_URL = "https://fapi.binance.com"

class BinanceAPIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status, self.payload = status, payload

@dataclass(frozen=True, slots=True)
class PaginationMetadata:
    pages: int
    returned: int
    requested_start: str
    requested_end: str
    complete: bool
    def to_dict(self):
        return {"pages": self.pages, "returned": self.returned,
                "requested_start": self.requested_start, "requested_end": self.requested_end,
                "complete": self.complete}

class BinancePublicClient:
    """Public market data only. No API-key, account, or trading methods."""
    def __init__(self, timeout: float = 15.0, retries: int = 3, backoff_seconds: float = 0.5,
                 opener=None, sleep=None, user_agent: str = "MASTER-ARSENAL/0.2"):
        if timeout <= 0 or retries < 0 or backoff_seconds < 0:
            raise ValueError("timeout must be positive; retries/backoff cannot be negative")
        self.timeout, self.retries, self.backoff_seconds = timeout, retries, backoff_seconds
        self._opener, self._sleep = opener or urlopen, sleep or time.sleep
        self.user_agent = user_agent
        self.last_response_metadata: dict[str, Any] = {}

    @staticmethod
    def _base(market: str) -> str:
        if market == "spot": return SPOT_BASE_URL
        if market == "usdm": return USDM_BASE_URL
        raise ValueError("market must be 'spot' or 'usdm'")

    @staticmethod
    def _retry_after(headers) -> float | None:
        raw = headers.get("Retry-After") if headers else None
        if not raw: return None
        try: return max(0.0, float(raw))
        except (TypeError, ValueError):
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                return max(0.0, (dt-datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError): return None

    def _request_json(self, market: str, path: str, params: dict[str, Any] | None = None):
        query = urlencode({k:v for k,v in (params or {}).items() if v is not None})
        url = self._base(market) + path + (f"?{query}" if query else "")
        last_error = None
        for attempt in range(self.retries + 1):
            request = Request(url, headers={"Accept":"application/json", "User-Agent":self.user_agent})
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    raw, headers = response.read(), response.headers
                    status = getattr(response, "status", 200)
                self.last_response_metadata = {
                    "http_status": status,
                    "used_weight_1m": headers.get("X-MBX-USED-WEIGHT-1M"),
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
                }
                try: payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise BinanceAPIError(f"Invalid JSON returned for {path}") from exc
                if isinstance(payload, dict) and "code" in payload and int(payload.get("code",0)) < 0:
                    raise BinanceAPIError(f"Binance API error: {payload.get('msg',payload)}", status, payload)
                return payload
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                try: payload = json.loads(body)
                except json.JSONDecodeError: payload = body
                last_error = BinanceAPIError(f"HTTP {exc.code} from Binance: {payload}", exc.code, payload)
                retryable = exc.code in (418,429) or 500 <= exc.code <= 599
                if not retryable or attempt >= self.retries: raise last_error from exc
                delay = self._retry_after(exc.headers)
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise BinanceAPIError(f"Network failure contacting Binance: {exc}") from exc
                delay = None
            if delay is None: delay = self.backoff_seconds * (2 ** attempt)
            self._sleep(delay)
        raise BinanceAPIError(f"Binance request failed: {last_error}")

    def get_server_time(self, market: str = "spot") -> datetime:
        path = "/api/v3/time" if market == "spot" else "/fapi/v1/time"
        return utc_datetime(int(self._request_json(market,path)["serverTime"]))

    def get_exchange_info(self, market: str = "spot"):
        path = "/api/v3/exchangeInfo" if market == "spot" else "/fapi/v1/exchangeInfo"
        return self._request_json(market,path)

    @staticmethod
    def _to_milliseconds(value: datetime | int) -> int:
        return value if isinstance(value,int) else int(utc_datetime(value).timestamp()*1000)

    def _parse_klines(self, symbol: str, interval: str, rows: list[list[Any]]) -> list[Candle]:
        candles = []
        for row in rows:
            if len(row) < 12: raise BinanceAPIError("Malformed kline row: expected 12 fields", payload=row)
            candles.append(Candle(
                symbol=symbol.upper(), interval=interval, open_time=utc_datetime(int(row[0])),
                close_time=utc_datetime(int(row[6])) if len(row)>6 else utc_datetime(int(row[0])),
                open=decimal_value(row[1]), high=decimal_value(row[2]), low=decimal_value(row[3]),
                close=decimal_value(row[4]), volume=decimal_value(row[5]),
                quote_volume=decimal_value(row[7]) if len(row)>7 else None,
                trades=int(row[8]) if len(row)>8 else None,
                taker_buy_base_volume=decimal_value(row[9]) if len(row)>9 else None,
                taker_buy_quote_volume=decimal_value(row[10]) if len(row)>10 else None))
        return candles

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 500,
                   market: str = "spot", start_time: datetime | int | None = None,
                   end_time: datetime | int | None = None) -> list[Candle]:
        maximum = 1000 if market == "spot" else 1500
        if not 1 <= limit <= maximum: raise ValueError(f"limit must be 1..{maximum} for {market}")
        path = "/api/v3/klines" if market == "spot" else "/fapi/v1/klines"
        params = {"symbol":symbol.upper(),"interval":interval,"limit":limit}
        if start_time is not None: params["startTime"] = self._to_milliseconds(start_time)
        if end_time is not None: params["endTime"] = self._to_milliseconds(end_time)
        rows = self._request_json(market,path,params)
        if not isinstance(rows,list): raise BinanceAPIError("Unexpected kline response type",payload=rows)
        return self._parse_klines(symbol,interval,rows)

    def get_historical_klines(self, symbol: str, interval: str, start_time: datetime | int,
                              end_time: datetime | int, market: str = "spot",
                              page_limit: int = 1000, max_pages: int = 1000):
        maximum = 1000 if market == "spot" else 1500
        if not 1 <= page_limit <= maximum: raise ValueError(f"page_limit must be 1..{maximum} for {market}")
        start_ms,end_ms = self._to_milliseconds(start_time),self._to_milliseconds(end_time)
        if end_ms <= start_ms: raise ValueError("end_time must be later than start_time")
        if max_pages < 1: raise ValueError("max_pages must be >= 1")
        cursor, pages, complete = start_ms, 0, False
        collected: dict[int,Candle] = {}
        # USD-M Futures historical kline requests are limited to a 200-day window.
        max_window = 200*24*60*60*1000 if market == "usdm" else end_ms-start_ms
        while cursor < end_ms and pages < max_pages:
            page_end = min(end_ms,cursor+max_window)
            rows = self.get_klines(symbol,interval,page_limit,market,cursor,page_end-1)
            pages += 1
            if not rows:
                cursor = page_end
                if cursor >= end_ms: complete = True
                continue
            for candle in rows:
                opened = self._to_milliseconds(candle.open_time)
                if start_ms <= opened < end_ms: collected[opened] = candle
            next_cursor = self._to_milliseconds(rows[-1].close_time)+1
            if next_cursor <= cursor:
                raise BinanceAPIError("Kline pagination made no forward progress")
            cursor = page_end if len(rows)<page_limit else next_cursor
            if cursor >= end_ms: complete = True
        metadata = PaginationMetadata(pages,len(collected),
            utc_datetime(start_ms).isoformat().replace("+00:00","Z"),
            utc_datetime(end_ms).isoformat().replace("+00:00","Z"),complete)
        return [collected[k] for k in sorted(collected)], metadata

    def get_24h_ticker(self, symbol: str | None = None, market: str = "spot"):
        path = "/api/v3/ticker/24hr" if market == "spot" else "/fapi/v1/ticker/24hr"
        return self._request_json(market,path,{"symbol":symbol.upper() if symbol else None})

    def get_premium_index(self, symbol: str | None = None):
        return self._request_json("usdm","/fapi/v1/premiumIndex",{"symbol":symbol.upper() if symbol else None})

    def get_open_interest(self, symbol: str):
        return self._request_json("usdm","/fapi/v1/openInterest",{"symbol":symbol.upper()})

    def get_open_interest_history(self, symbol: str, period: str = "1h", limit: int = 30):
        if not 1 <= limit <= 500: raise ValueError("open interest history limit must be 1..500")
        return self._request_json("usdm","/futures/data/openInterestHist",{"symbol":symbol.upper(),"period":period,"limit":limit})

    def get_funding_rate_history(self, symbol: str, limit: int = 1000,
                                 start_time: datetime | int | None = None,
                                 end_time: datetime | int | None = None):
        if not 1 <= limit <= 1000: raise ValueError("funding history limit must be 1..1000")
        return self._request_json("usdm","/fapi/v1/fundingRate",{
            "symbol":symbol.upper(),"limit":limit,
            "startTime":self._to_milliseconds(start_time) if start_time is not None else None,
            "endTime":self._to_milliseconds(end_time) if end_time is not None else None})

    def get_global_long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 30):
        if not 1 <= limit <= 500: raise ValueError("long/short ratio limit must be 1..500")
        return self._request_json("usdm","/futures/data/globalLongShortAccountRatio",
                                  {"symbol":symbol.upper(),"period":period,"limit":limit})

    def get_basis(self, pair: str, contract_type: str = "PERPETUAL", period: str = "1h", limit: int = 30):
        if not 1 <= limit <= 500: raise ValueError("basis limit must be 1..500")
        return self._request_json("usdm","/futures/data/basis",
                                  {"pair":pair.upper(),"contractType":contract_type,"period":period,"limit":limit})

    def get_mark_price_klines(self, symbol: str, interval: str = "1h", limit: int = 500):
        if not 1 <= limit <= 1500: raise ValueError("limit must be 1..1500")
        return self._request_json("usdm","/fapi/v1/markPriceKlines",
                                  {"symbol":symbol.upper(),"interval":interval,"limit":limit})

    def get_index_price_klines(self, pair: str, interval: str = "1h", limit: int = 500):
        if not 1 <= limit <= 1500: raise ValueError("limit must be 1..1500")
        return self._request_json("usdm","/fapi/v1/indexPriceKlines",
                                  {"pair":pair.upper(),"interval":interval,"limit":limit})
