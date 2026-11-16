"""Best-effort, source-attributed U.S. market snapshot from public Yahoo chart data.

This is contextual market information, not a licensed execution feed. Every
quote retains its observation timestamp and source URL; unavailable symbols
are disclosed rather than inferred.
"""
from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LOCAL = ZoneInfo("America/Santo_Domingo")
SOURCE = "Yahoo Finance public chart endpoint (best effort)"
MAX_RESPONSE_BYTES = 2_000_000

INSTRUMENTS = {
    "indices": (
        ("S&P 500", "^GSPC", "index_points"),
        ("Nasdaq Composite", "^IXIC", "index_points"),
        ("Nasdaq 100", "^NDX", "index_points"),
        ("Dow Jones Industrial Average", "^DJI", "index_points"),
        ("Russell 2000", "^RUT", "index_points"),
    ),
    "volatility": (
        ("CBOE VIX", "^VIX", "index_points"),
    ),
    "futures": (
        ("E-mini S&P 500", "ES=F", "index_points"),
        ("E-mini Nasdaq 100", "NQ=F", "index_points"),
        ("E-mini Dow", "YM=F", "index_points"),
    ),
    "rates": (
        ("U.S. Treasury 10Y yield", "^TNX", "yield_percent_x10"),
    ),
    "dollar": (
        ("U.S. Dollar Index", "DX-Y.NYB", "index_points"),
    ),
    "commodities": (
        ("WTI crude oil", "CL=F", "USD_per_barrel"),
        ("Gold futures", "GC=F", "USD_per_troy_ounce"),
    ),
    "sectors": (
        ("Materials", "XLB", "ETF_USD"),
        ("Communication Services", "XLC", "ETF_USD"),
        ("Energy", "XLE", "ETF_USD"),
        ("Financials", "XLF", "ETF_USD"),
        ("Industrials", "XLI", "ETF_USD"),
        ("Technology", "XLK", "ETF_USD"),
        ("Consumer Staples", "XLP", "ETF_USD"),
        ("Real Estate", "XLRE", "ETF_USD"),
        ("Utilities", "XLU", "ETF_USD"),
        ("Health Care", "XLV", "ETF_USD"),
        ("Consumer Discretionary", "XLY", "ETF_USD"),
    ),
}


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _parse_chart_payload(
    payload: bytes,
    *,
    name: str,
    symbol: str,
    category: str,
    unit: str,
    as_of: datetime,
    retrieved_at: datetime,
    source_url: str,
) -> dict[str, Any]:
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("Yahoo chart response exceeds the 2 MB safety limit")
    document = json.loads(payload.decode("utf-8"))
    chart = document.get("chart") if isinstance(document, dict) else None
    if not isinstance(chart, dict):
        raise ValueError("Yahoo chart response has no chart object")
    if chart.get("error"):
        raise ValueError(f"Yahoo chart error: {chart['error']}")
    results = chart.get("result")
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise ValueError("Yahoo chart response contains no result")
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote_rows = ((result.get("indicators") or {}).get("quote") or [])
    closes = quote_rows[0].get("close") if quote_rows and isinstance(quote_rows[0], dict) else None
    if not isinstance(timestamps, list) or not isinstance(closes, list):
        raise ValueError("Yahoo chart response is missing timestamp/close arrays")

    observations = []
    for stamp, raw_close in zip(timestamps, closes):
        price = _number(raw_close)
        if not isinstance(stamp, int) or price is None:
            continue
        observed = datetime.fromtimestamp(stamp, timezone.utc)
        if observed <= as_of:
            observations.append((observed, price))
    if not observations:
        raise ValueError("No non-future valid quote was returned for the requested cutoff")
    observed_at, last_price = max(observations, key=lambda item: item[0])
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    previous_close = _number(meta.get("chartPreviousClose"))
    if previous_close is None:
        previous_close = _number(meta.get("previousClose"))
    if unit == "yield_percent_x10":
        last_price /= 10
        previous_close = previous_close / 10 if previous_close is not None else None
        unit = "yield_percent"
    change = last_price - previous_close if previous_close is not None else None
    change_percent = (
        change / previous_close * 100
        if change is not None and previous_close not in (0, None) else None
    )
    age_minutes = max(0.0, (as_of - observed_at).total_seconds() / 60)
    return {
        "status": "ok",
        "name": name,
        "symbol": symbol,
        "category": category,
        "unit": unit,
        "last_price": last_price,
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_percent,
        "change_basis_points": change * 100 if change is not None and unit == "yield_percent" else None,
        "observed_at_utc": observed_at.isoformat().replace("+00:00", "Z"),
        "observed_at_et": observed_at.astimezone(ET).isoformat(),
        "observed_at_local": observed_at.astimezone(LOCAL).isoformat(),
        "age_minutes_at_cutoff": round(age_minutes, 2),
        "currency": meta.get("currency"),
        "exchange_name": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "market_state": meta.get("marketState"),
        "source": SOURCE,
        "source_url": source_url,
        "retrieved_at_utc": retrieved_at.isoformat().replace("+00:00", "Z"),
    }


def _fetch_one(
    item: tuple[str, str, str],
    category: str,
    as_of: datetime,
    timeout: float,
    opener: Callable[..., Any],
) -> dict[str, Any]:
    name, symbol, unit = item
    period1 = int((as_of - timedelta(days=7)).timestamp())
    period2 = int(as_of.timestamp()) + 1
    encoded = quote(symbol, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={period1}&period2={period2}&interval=5m&includePrePost=true"
    )
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; MASTER-ARSENAL/0.5; +https://github.com/jlsoftware2026/master-arsenal)",
    })
    try:
        with opener(request, timeout=timeout) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        retrieved = datetime.now(timezone.utc)
        return _parse_chart_payload(
            payload, name=name, symbol=symbol, category=category, unit=unit,
            as_of=as_of, retrieved_at=retrieved, source_url=url,
        )
    except Exception as exc:
        return {
            "status": "unavailable",
            "name": name,
            "symbol": symbol,
            "category": category,
            "unit": unit,
            "last_price": None,
            "previous_close": None,
            "change": None,
            "change_percent": None,
            "observed_at_utc": None,
            "observed_at_et": None,
            "observed_at_local": None,
            "source": SOURCE,
            "source_url": url,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error": f"{type(exc).__name__}: {exc}",
        }


def collect_us_market_snapshot(
    as_of: datetime,
    *,
    timeout: float = 5.0,
    max_workers: int = 8,
    opener: Callable[..., Any] | None = None,
    instruments: dict[str, tuple[tuple[str, str, str], ...]] | None = None,
) -> dict[str, Any]:
    """Collect an as-of U.S. market snapshot with per-symbol provenance."""
    cutoff = _utc(as_of, "as_of")
    if timeout <= 0 or not 1 <= max_workers <= 16:
        raise ValueError("timeout must be positive and max_workers must be 1..16")
    catalog = instruments or INSTRUMENTS
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError("instruments must be a non-empty category mapping")
    fetch = opener or urlopen
    jobs = []
    for category, items in catalog.items():
        if not isinstance(category, str) or not isinstance(items, (tuple, list)):
            raise ValueError("instrument catalog has an invalid category")
        for item in items:
            if not isinstance(item, (tuple, list)) or len(item) != 3:
                raise ValueError("each instrument must be (name, symbol, unit)")
            jobs.append((tuple(item), category))

    results: dict[str, list[dict[str, Any]]] = {category: [] for category in catalog}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_one, item, category, cutoff, timeout, fetch): (item, category)
            for item, category in jobs
        }
        for future in as_completed(futures):
            item, category = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "status": "unavailable", "name": item[0], "symbol": item[1],
                    "category": category, "unit": item[2], "last_price": None,
                    "previous_close": None, "change": None, "change_percent": None,
                    "observed_at_utc": None, "source": SOURCE,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            results[category].append(result)
    for values in results.values():
        values.sort(key=lambda item: item["symbol"])

    all_results = [item for values in results.values() for item in values]
    available = [item for item in all_results if item.get("status") == "ok"]
    unavailable = [item for item in all_results if item.get("status") != "ok"]
    sectors = [
        item for item in results.get("sectors", [])
        if item.get("status") == "ok" and item.get("change_percent") is not None
    ]
    leaders = sorted(sectors, key=lambda item: item["change_percent"], reverse=True)
    return {
        "status": "unavailable" if not available else "partial",
        "instrument_snapshot_status": "unavailable" if not available else
            "complete" if not unavailable else "partial",
        "provider": SOURCE,
        "as_of_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "expected_instruments": len(all_results),
        "available_instruments": len(available),
        "unavailable_symbols": [item["symbol"] for item in unavailable],
        "groups": results,
        "sector_leaders": leaders[:3],
        "sector_laggards": leaders[-3:],
        "market_breadth": {
            "status": "not_available",
            "reason": "Advance/decline breadth and stock-level leaders/laggards are not supplied by this instrument set.",
        },
        "limitations": (
            "Quotes are best-effort observations from the public Yahoo Finance chart endpoint; the endpoint is not an official "
            "licensed execution feed and may be delayed, incomplete, rate-limited, or changed without notice. "
            "Use the observation timestamps, not retrieval time, as the quote time. Market breadth and stock-level leaders/laggards "
            "are not included. Missing symbols remain unavailable; no values are inferred."
        ),
    }
