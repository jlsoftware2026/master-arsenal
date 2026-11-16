"""Dominican calendar-day boundaries for MASTER ARSENAL reports.

All report windows are half-open [start, end) instants. Calendar dates are
interpreted in America/Santo_Domingo and converted to UTC only at the data
provider boundary. ZoneInfo supplies correct historical/future offset rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

REPORT_TIMEZONE = "America/Santo_Domingo"
LOCAL_TZ = ZoneInfo(REPORT_TIMEZONE)
UTC = timezone.utc


@dataclass(frozen=True)
class ReportWindow:
    report_date: date
    start_local: datetime
    end_local: datetime
    start_utc: datetime
    end_utc: datetime
    is_partial: bool

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "report_timezone": REPORT_TIMEZONE,
            "report_date_local": self.report_date.isoformat(),
            "window_start_local": self.start_local.isoformat(),
            "cutoff_local": self.end_local.isoformat(),
            "window_start_utc": self.start_utc.isoformat().replace("+00:00", "Z"),
            "cutoff_utc": self.end_utc.isoformat().replace("+00:00", "Z"),
            "window_semantics": "[start, cutoff)",
            "is_partial": self.is_partial,
        }


def _aware_local(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be a datetime")
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(LOCAL_TZ)


def local_day_window(
    report_date: date,
    cutoff_local: datetime | None = None,
    *,
    now: datetime | None = None,
) -> ReportWindow:
    """Resolve one Dominican calendar day, optionally ending at a partial cutoff."""
    if not isinstance(report_date, date) or isinstance(report_date, datetime):
        raise ValueError("report_date must be datetime.date")
    start = datetime.combine(report_date, time.min, tzinfo=LOCAL_TZ)
    if cutoff_local is None:
        cutoff = _aware_local(now or datetime.now(LOCAL_TZ), "now")
    else:
        cutoff = _aware_local(cutoff_local, "cutoff_local")
    if cutoff.date() != report_date:
        raise ValueError("cutoff_local must fall on report_date in America/Santo_Domingo")
    if cutoff <= start:
        raise ValueError("cutoff_local must be later than local midnight")
    return ReportWindow(
        report_date=report_date,
        start_local=start,
        end_local=cutoff,
        start_utc=start.astimezone(UTC),
        end_utc=cutoff.astimezone(UTC),
        is_partial=cutoff < start + timedelta(days=1),
    )


def completed_local_day(report_date: date) -> ReportWindow:
    """Resolve a completed Dominican calendar day [midnight, next midnight)."""
    if not isinstance(report_date, date) or isinstance(report_date, datetime):
        raise ValueError("report_date must be datetime.date")
    start = datetime.combine(report_date, time.min, tzinfo=LOCAL_TZ)
    end = datetime.combine(report_date + timedelta(days=1), time.min, tzinfo=LOCAL_TZ)
    return ReportWindow(
        report_date=report_date, start_local=start, end_local=end,
        start_utc=start.astimezone(UTC), end_utc=end.astimezone(UTC),
        is_partial=False,
    )


def opening_reference_date(request_date: date) -> date:
    """Opening report's Binance reference is the previous Dominican date."""
    if not isinstance(request_date, date) or isinstance(request_date, datetime):
        raise ValueError("request_date must be datetime.date")
    return request_date - timedelta(days=1)


def current_local_report_date(now: datetime | None = None) -> date:
    """Return the execution-time date in the report timezone."""
    return _aware_local(now or datetime.now(LOCAL_TZ), "now").date()
