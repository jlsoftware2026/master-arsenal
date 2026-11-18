"""NYSE cash-session calendar and Dominican-local session classification.

The XNYS calendar supplies U.S. equity holidays and early closes. All
comparisons are performed in UTC; display timestamps retain explicit ET and
America/Santo_Domingo conversions. Calendar failures fail closed as
unavailable rather than guessing from weekdays or fixed UTC offsets.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

REPORT_TZ = ZoneInfo("America/Santo_Domingo")
EASTERN_TZ = ZoneInfo("America/New_York")
CALENDAR_NAME = "XNYS"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("as_of must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _stamp(value: Any) -> datetime:
    """Normalize exchange_calendars UTC timestamps to aware Python datetimes."""
    result = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    if not isinstance(result, datetime):
        raise ValueError("Exchange calendar returned an invalid session timestamp")
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _session_label(value: Any) -> str:
    return value.date().isoformat() if hasattr(value, "date") else str(value)[:10]


def classify_us_equity_session(
    as_of: datetime | None = None,
    *,
    calendar: Any | None = None,
) -> dict[str, Any]:
    """Classify XNYS premarket/regular/postmarket/closed at an exact instant.

    The returned schedule is for the NYSE cash session (also the standard
    reference calendar for U.S. listed-equity cash hours). It does not claim
    that every constituent/security is individually tradable.
    """
    instant = _utc(as_of or datetime.now(timezone.utc))
    eastern = instant.astimezone(EASTERN_TZ)
    local = instant.astimezone(REPORT_TZ)
    day = eastern.date()

    try:
        if calendar is None:
            import exchange_calendars as xcals
            calendar = xcals.get_calendar(CALENDAR_NAME)

        is_session = bool(calendar.is_session(day.isoformat()))
        if is_session:
            session = calendar.date_to_session(day.isoformat(), direction="none")
            opened = _stamp(calendar.session_open(session))
            closed = _stamp(calendar.session_close(session))
            if instant < opened:
                state = "premarket"
                last_session = calendar.previous_session(session)
                next_session = session
            elif instant < closed:
                state = "regular"
                last_session = calendar.previous_session(session)
                next_session = calendar.next_session(session)
            else:
                state = "postmarket"
                last_session = session
                next_session = calendar.next_session(session)
        else:
            state = "closed"
            previous = calendar.date_to_session(day.isoformat(), direction="previous")
            following = calendar.date_to_session(day.isoformat(), direction="next")
            last_session = previous
            next_session = following
            opened = closed = None

        last_date = _session_label(last_session)
        next_date = _session_label(next_session)
        last_open = _stamp(calendar.session_open(last_session))
        last_close = _stamp(calendar.session_close(last_session))
        next_open = _stamp(calendar.session_open(next_session))
        if opened is not None and closed is not None:
            early_close = closed.astimezone(EASTERN_TZ).time().replace(tzinfo=None) < time(16, 0)
        else:
            early_close = False

        return {
            "status": "ok",
            "calendar": CALENDAR_NAME,
            "calendar_source": "exchange_calendars",
            "as_of_utc": instant.isoformat().replace("+00:00", "Z"),
            "as_of_et": eastern.isoformat(),
            "as_of_local": local.isoformat(),
            "session_state": state,
            "is_session_date": is_session,
            "session_date_et": day.isoformat() if is_session else None,
            "session_open_utc": opened.isoformat().replace("+00:00", "Z") if opened else None,
            "session_close_utc": closed.isoformat().replace("+00:00", "Z") if closed else None,
            "session_open_et": opened.astimezone(EASTERN_TZ).isoformat() if opened else None,
            "session_close_et": closed.astimezone(EASTERN_TZ).isoformat() if closed else None,
            "session_open_local": opened.astimezone(REPORT_TZ).isoformat() if opened else None,
            "session_close_local": closed.astimezone(REPORT_TZ).isoformat() if closed else None,
            "early_close": early_close,
            "last_completed_session_date": last_date,
            "last_completed_session_close_utc": last_close.isoformat().replace("+00:00", "Z"),
            "last_completed_session_close_et": last_close.astimezone(EASTERN_TZ).isoformat(),
            "next_session_date": next_date,
            "next_session_open_utc": next_open.isoformat().replace("+00:00", "Z"),
            "next_session_open_et": next_open.astimezone(EASTERN_TZ).isoformat(),
            "limitations": (
                "XNYS is used as the U.S. equity cash-session reference calendar. "
                "It does not provide index prices, futures, VIX, breadth, sector data, "
                "or security-specific halts."
            ),
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "calendar": CALENDAR_NAME,
            "calendar_source": "exchange_calendars",
            "as_of_utc": instant.isoformat().replace("+00:00", "Z"),
            "as_of_et": eastern.isoformat(),
            "as_of_local": local.isoformat(),
            "session_state": "not_available",
            "is_session_date": None,
            "session_date_et": None,
            "session_open_utc": None,
            "session_close_utc": None,
            "session_open_et": None,
            "session_close_et": None,
            "session_open_local": None,
            "session_close_local": None,
            "early_close": None,
            "last_completed_session_date": None,
            "last_completed_session_close_utc": None,
            "last_completed_session_close_et": None,
            "next_session_date": None,
            "next_session_open_utc": None,
            "next_session_open_et": None,
            "error": f"{type(exc).__name__}: {exc}",
            "limitations": "The exchange calendar could not be verified; no session state is inferred.",
        }
