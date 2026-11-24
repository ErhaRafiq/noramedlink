"""Is a doctor available for a home visit now? Read from the weekly hours they already set (clinic time).

"now": today's hours cover this moment. "soon": a window starts within the next 2 hours. Otherwise "none".
Hours are the doctor's own; an appointment already booked in the hours is not looked at here.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, time, timedelta

from services import clock
from services.home_visits.matching import AVAILABLE_NOW, AVAILABLE_SOON, UNAVAILABLE

SOON = timedelta(hours=2)


def availability_state(windows: Iterable[tuple[int, time, time]], now: datetime) -> str:
    """`windows` are (weekday 0=Monday, start, end) in clinic time; `now` is any aware moment."""
    local = now.astimezone(clock.zone())
    here = local.time().replace(second=0, microsecond=0)
    state = UNAVAILABLE
    for weekday, start, end in windows:
        if weekday != local.weekday():
            continue
        if start <= here < end:
            return AVAILABLE_NOW
        if here < start and datetime.combine(local.date(), start) - datetime.combine(local.date(), here) <= SOON:
            state = AVAILABLE_SOON
    return state
