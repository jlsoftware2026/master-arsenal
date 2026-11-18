"""Offline tests for sourced macro/news RSS context collection."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import unittest

from report_engine.context import FEEDS, collect_market_context

START = datetime(2026, 11, 14, tzinfo=timezone.utc)
END = START + timedelta(days=1)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size=-1):
        return self.payload[:size]


class ContextTests(unittest.TestCase):
    def test_collects_only_items_inside_utc_window_and_attributes_sources(self):
        payload = b"""<?xml version="1.0"?><rss><channel>
        <item><title>Bitcoin market structure update</title><link>https://example.com/btc</link>
        <pubDate>Sat, 14 Nov 2026 12:00:00 GMT</pubDate><description>BTC market report</description></item>
        <item><title>Older story</title><link>https://example.com/old</link>
        <pubDate>Fri, 13 Nov 2026 12:00:00 GMT</pubDate></item>
        </channel></rss>"""
        def opener(request, timeout):
            return FakeResponse(payload)
        result = collect_market_context(START, END, opener=opener)
        self.assertEqual(len(result["news_sources"]), 3 * 1)
        self.assertEqual(len(result["macro_sources"]), 3 * 1)
        self.assertEqual(result["news_sources"][0]["publisher"], "CoinDesk")
        self.assertEqual(result["news_sources"][0]["published_at_utc"], "2026-11-14T12:00:00Z")
        self.assertIn("Potentially relevant context", result["news_sources"][0]["relevance"])
        self.assertEqual(result["context_status"], "complete")

    def test_unavailable_feed_is_reported_not_silently_ignored(self):
        calls = 0
        def opener(request, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("fixture offline")
            return FakeResponse(b"<rss><channel/></rss>")
        result = collect_market_context(START, END, opener=opener)
        self.assertEqual(result["context_status"], "partial")
        self.assertEqual(result["context_sources"][0]["status"], "unavailable")
        self.assertIn("fixture offline", result["context_sources"][0]["error"])

    def test_invalid_window_rejected(self):
        with self.assertRaisesRegex(ValueError, "later than"):
            collect_market_context(END, START)


if __name__ == "__main__":
    unittest.main()
