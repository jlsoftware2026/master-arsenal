"""NYSE calendar classification regression tests."""
from datetime import datetime, timezone
import unittest

from report_engine.us_market_calendar import classify_us_equity_session


class USMarketCalendarTests(unittest.TestCase):
    def test_regular_session_uses_dst_aware_utc_open(self):
        # Monday after the 2026 spring DST transition: 09:30 EDT = 13:30 UTC.
        result = classify_us_equity_session(datetime(2026, 3, 9, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["session_state"], "regular")
        self.assertEqual(result["session_open_utc"], "2026-03-09T13:30:00+00:00")
        self.assertEqual(result["session_open_et"], "2026-03-09T09:30:00-04:00")

    def test_standard_time_open_is_1430_utc(self):
        result = classify_us_equity_session(datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(result["session_state"], "regular")
        self.assertEqual(result["session_open_utc"], "2026-11-16T14:30:00+00:00")
        self.assertEqual(result["session_open_et"], "2026-11-16T09:30:00-05:00")

    def test_thanksgiving_is_closed_and_points_to_next_session(self):
        result = classify_us_equity_session(datetime(2026, 11, 26, 17, 0, tzinfo=timezone.utc))
        self.assertEqual(result["session_state"], "closed")
        self.assertFalse(result["is_session_date"])
        self.assertEqual(result["last_completed_session_date"], "2026-11-25")
        self.assertEqual(result["next_session_date"], "2026-11-27")

    def test_day_after_thanksgiving_early_close(self):
        result = classify_us_equity_session(datetime(2026, 11, 27, 18, 30, tzinfo=timezone.utc))
        self.assertEqual(result["session_state"], "postmarket")
        self.assertTrue(result["early_close"])
        self.assertEqual(result["session_close_et"], "2026-11-27T13:00:00-05:00")

    def test_weekend_uses_last_completed_cash_session(self):
        result = classify_us_equity_session(datetime(2026, 11, 28, 16, 0, tzinfo=timezone.utc))
        self.assertEqual(result["session_state"], "closed")
        self.assertEqual(result["last_completed_session_date"], "2026-11-27")
        self.assertEqual(result["next_session_date"], "2026-11-30")

    def test_naive_datetime_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            classify_us_equity_session(datetime(2026, 11, 16, 10, 0))


if __name__ == "__main__":
    unittest.main()
