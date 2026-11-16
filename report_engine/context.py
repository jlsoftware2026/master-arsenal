"""Source-attributed macro and digital-asset news context from public RSS feeds."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

FEEDS = (
    {"kind": "news", "publisher": "CoinDesk",
     "url": "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"},
    {"kind": "news", "publisher": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"kind": "news", "publisher": "The Block", "url": "https://www.theblock.co/rss.xml"},
    {"kind": "macro", "publisher": "Federal Reserve",
     "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
    {"kind": "macro", "publisher": "Bureau of Labor Statistics",
     "url": "https://www.bls.gov/feed/bls_latest.rss"},
    {"kind": "macro", "publisher": "European Central Bank",
     "url": "https://www.ecb.europa.eu/rss/press.html"},
)


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element, names: set[str]) -> str | None:
    for child in list(element):
        if _local_name(child.tag) in names:
            return "".join(child.itertext()).strip() or None
    return None


def _published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _clean_summary(value: str | None, limit: int = 600) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]*>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def _parse_feed(payload: bytes, feed: dict[str, str], start: datetime, end: datetime,
                max_items: int) -> list[dict[str, str]]:
    if len(payload) > 2_000_000:
        raise ValueError("RSS feed exceeds the 2 MB safety limit")
    root = ET.fromstring(payload)
    entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    results = []
    for entry in entries:
        title = _child_text(entry, {"title"}) or "Untitled feed entry"
        link = _child_text(entry, {"link"})
        if not link:
            for child in list(entry):
                if _local_name(child.tag) == "link":
                    link = child.attrib.get("href")
                    if link:
                        break
        if not link or not link.startswith(("https://", "http://")):
            continue
        published_raw = _child_text(entry, {"pubdate", "published", "updated", "date"})
        published = _published(published_raw)
        if published is None or not (start <= published < end):
            continue
        summary = _clean_summary(_child_text(entry, {"description", "summary", "content"}))
        results.append({
            "title": title[:300],
            "publisher": feed["publisher"],
            "published_at_utc": published.isoformat().replace("+00:00", "Z"),
            "url": link[:2000],
            "summary": summary,
            "relevance": "Potentially relevant context; independently assess market impact.",
        })
        if len(results) >= max_items:
            break
    return results


def collect_market_context(
    window_start_utc: datetime,
    window_end_utc: datetime,
    *,
    timeout: float = 8.0,
    max_items_per_feed: int = 8,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Collect date-bounded RSS context; failures are recorded, never fabricated."""
    start = _utc(window_start_utc, "window_start_utc")
    end = _utc(window_end_utc, "window_end_utc")
    if end <= start:
        raise ValueError("window_end_utc must be later than window_start_utc")
    if timeout <= 0 or not 1 <= max_items_per_feed <= 50:
        raise ValueError("timeout must be positive and max_items_per_feed must be 1..50")
    fetch = opener or urlopen
    news, macro, sources = [], [], []
    for feed in FEEDS:
        retrieved = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            request = Request(feed["url"], headers={
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                "User-Agent": "MASTER-ARSENAL/0.3",
            })
            with fetch(request, timeout=timeout) as response:
                payload = response.read(2_000_001)
            entries = _parse_feed(payload, feed, start, end, max_items_per_feed)
            (news if feed["kind"] == "news" else macro).extend(entries)
            sources.append({
                "publisher": feed["publisher"], "feed_url": feed["url"],
                "kind": feed["kind"], "status": "ok",
                "retrieved_at_utc": retrieved, "matching_items": len(entries),
            })
        except Exception as exc:
            sources.append({
                "publisher": feed["publisher"], "feed_url": feed["url"],
                "kind": feed["kind"], "status": "unavailable",
                "retrieved_at_utc": retrieved,
                "error": f"{type(exc).__name__}: {exc}",
            })
    news.sort(key=lambda item: item["published_at_utc"], reverse=True)
    macro.sort(key=lambda item: item["published_at_utc"], reverse=True)
    def summary(items, label):
        if not items:
            return f"No date-matched {label} items were retrieved from the configured feeds."
        return "\n".join(
            f"{item['published_at_utc']} — {item['publisher']}: {item['title']}"
            for item in items
        )
    failed = [source for source in sources if source["status"] != "ok"]
    return {
        "macro_context": summary(macro, "macroeconomic"),
        "news": summary(news, "digital-asset news"),
        "macro_sources": macro,
        "news_sources": news,
        "context_sources": sources,
        "context_status": "partial" if failed else "complete",
        "context_retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "context_limitations": (
            "RSS feed coverage is not exhaustive. Publication timestamps are publisher-supplied. "
            "A headline is a candidate context item, not proof of market causation."
        ),
    }
