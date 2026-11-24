"""The loop started with the server that settles home visit offers nobody answered in time.

Like the email worker it is a loop in main.py, not a cron job. Reading a visit settles it too, so this only
makes sure a request moves on (next doctor, or the end) even when nobody is looking at it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from database import SessionLocal
from services import clock
from services.home_visits import workflow

log = logging.getLogger("nora.home_visits")
INTERVAL_SECONDS = 10


def tick() -> int:
    with SessionLocal() as db:
        try:
            return workflow.advance_due(db, clock.now())
        except Exception:
            db.rollback()
            log.exception("The home visit worker hit an error; it will try again")
            return 0


async def run(stop: asyncio.Event) -> None:
    while not stop.is_set():
        await asyncio.to_thread(tick)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=INTERVAL_SECONDS)
