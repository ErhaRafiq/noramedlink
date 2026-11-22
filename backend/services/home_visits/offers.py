"""The offer window of an auto-matched request, ride-hailing style.

The best doctor is offered the request with a 2-minute window; on a decline or a timeout the next one is
offered, up to 5 doctors, then the request ends as "no doctor found". A request sent to one chosen doctor
has a longer window (10 minutes) and no next doctor. The first accept wins; the database enforces that
(batch 2), these functions only say what comes next.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from services.home_visits.matching import Ranked

AUTO = "auto"
CHOOSE = "choose"
MODES = (AUTO, CHOOSE)
MAX_OFFERS = 5
WINDOW = {AUTO: timedelta(minutes=2), CHOOSE: timedelta(minutes=10)}


def expires_at(offered_at: datetime, mode: str) -> datetime:
    return offered_at + WINDOW[mode]


def is_expired(expires: datetime, now: datetime) -> bool:
    """A window ends at its expiry moment: an answer at that instant is too late."""
    return now >= expires


def next_candidate(ranked: list[Ranked], tried: set[int]) -> Ranked | None:
    """The best doctor not yet offered, or None when 5 have been offered or nobody is left."""
    if len(tried) >= MAX_OFFERS:
        return None
    return next((r for r in ranked if r.doctor_id not in tried), None)
