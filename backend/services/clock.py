"""The app's local date.

Timestamps stay in UTC. Date-only values (the date a pregnancy status was set, "today" for how old a weight is,
for a date that cannot be in the future, and for ages in years and months) use the patient's local calendar in
`settings.app_timezone` (APP_TIMEZONE, default Asia/Karachi). Just after midnight in Pakistan it is still the
previous day in UTC, and a patient must not be told yesterday's date. Tests move the clock by replacing `now`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import cache
from zoneinfo import ZoneInfo

from config import settings


@cache
def _zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def zone() -> ZoneInfo:
    return _zone(settings.app_timezone)


def now() -> datetime:
    """The current moment, timezone-aware UTC."""
    return datetime.now(UTC)


def today(at: datetime | None = None) -> date:
    """The local calendar date at `at` (default: now)."""
    moment = at or now()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(zone()).date()


def local_date(moment: datetime | date | None) -> date | None:
    """The local calendar date of a stored timestamp (a naive one is read as UTC); a plain date is kept."""
    if moment is None:
        return None
    if isinstance(moment, datetime):
        return today(moment)
    return moment
