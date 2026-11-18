"""Regression tests for Dominican local calendar-day semantics."""
from datetime import date, datetime, timedelta, timezone
import unittest

from report_engine.timezone import (
    REPORT_TIMEZONE, completed_local_day, current_local_report_date,
    local_day_window, opening_reference_date,
)


class DominicanCalendarWindowTests(unittest.TestCase):
    def test_completed_day_uses_local_midnights_and_utc_conversion(self):
        window = completed_local_day(date(2026, 11, 16))
        self.assertEqual(window.start_local.isoformat(), "2026-11-16T00:00:00-04:00")
        self.assertEqual(window.end_local.isoformat(), "2026-11-17T00:00:00-04:00")
        self.assertEqual(window.start_utc.isoformat(), "2026-11-16T04:00:00+00:00")
        self.assertEqual(window.end_utc.isoformat(), "2026-11-17T04:00:00+00:00")
        self.assertFalse(window.is_partial)

    def test_partial_closing_window_ends_at_exact_local_cutoff(self):
        cutoff = datetime(2026, 11, 16, 18, 15)
        window = local_day_window(date(2026, 11, 16), cutoff)
        self.assertTrue(window.is_partial)
        self.assertEqual(window.end_local.isoformat(), "2026-11-16T18:15:00-04:00")
        self.assertEqual(window.end_utc.isoformat(), "2026-11-16T22:15:00+00:00")

    def test_aware_cutoff_is_converted_to_dominican_timezone(self):
        cutoff_utc = datetime(2026, 11, 16, 22, 15, tzinfo=timezone.utc)
        window = local_day_window(date(2026, 11, 16), cutoff_utc)
        self.assertEqual(window.end_local.isoformat(), "2026-11-16T18:15:00-04:00")

    def test_naive_cutoff_is_interpreted_as_dominican_local_time(self):
        window = local_day_window(date(2026, 11, 16), datetime(2026, 11, 16, 12, 0))
        self.assertEqual(window.end_utc.hour, 16)

    def test_intraday_default_uses_execution_time(self):
        now = datetime(2026, 11, 16, 18, 15, tzinfo=timezone(timedelta(hours=-4)))
        window = local_day_window(date(2026, 11, 16), now=now)
        self.assertTrue(window.is_partial)
        self.assertEqual(window.end_local.hour, 18)

    def test_opening_uses_previous_local_calendar_date(self):
        self.assertEqual(opening_reference_date(date(2026, 11, 16)), date(2026, 11, 15))

    def test_execution_date_is_local_not_utc(self):
        instant = datetime(2026, 11, 17, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(current_local_report_date(instant), date(2026, 11, 16))

    def test_cutoff_on_other_local_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "report_date"):
            local_day_window(date(2026, 11, 16), datetime(2026, 11, 17, 0, 1))

    def test_midnight_cutoff_is_rejected_as_empty_window(self):
        with self.assertRaisesRegex(ValueError, "later than local midnight"):
            local_day_window(date(2026, 11, 16), datetime(2026, 11, 16, 0, 0))

    def test_manifest_metadata_identifies_timezone_and_half_open_window(self):
        metadata = completed_local_day(date(2026, 11, 16)).as_dict()
        self.assertEqual(metadata["report_timezone"], REPORT_TIMEZONE)
        self.assertEqual(metadata["window_semantics"], "[start, cutoff)")
        self.assertEqual(metadata["report_date_local"], "2026-11-16")


if __name__ == "__main__":
    unittest.main()
