"""Doctor availability and bookable slots (Module 5 FE-2, Module 1 FE-3).

A doctor publishes weekly windows (for example Monday 09:00 to 13:00, 30-minute slots). Patients book
one of the slots cut from those windows. A slot is open only if it is in the future (with a short lead
time), within the booking horizon, and not already taken by a live appointment of that doctor.

Times are stored in UTC. Windows and days are in clinic time: Pakistan is UTC+5 all year (no daylight
saving), so a fixed offset is exact and needs no time-zone database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from itertools import pairwise

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Appointment, DoctorAvailability

CLINIC_TZ = timezone(timedelta(hours=5))
CLINIC_TZ_NAME = "Asia/Karachi"
LEAD_MINUTES = 30  # a slot sooner than this from now cannot be booked
HORIZON_DAYS = 30  # how far ahead booking is open
SLOT_CHOICES = (10, 15, 20, 30, 45, 60)
MAX_WINDOWS_PER_DAY = 4


@dataclass(frozen=True)
class Slot:
    start: datetime  # UTC
    end: datetime  # UTC
    available: bool

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


class SlotUnavailable(Exception):
    """The requested time is not an open slot for this doctor."""


def now_utc() -> datetime:
    return datetime.now(UTC)


def clinic_date(moment: datetime) -> date:
    return moment.astimezone(CLINIC_TZ).date()


def _at(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock, tzinfo=CLINIC_TZ).astimezone(UTC)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _overlaps(start: datetime, end: datetime, taken: list[tuple[datetime, int]]) -> bool:
    return any(
        start < as_utc(t_start) + timedelta(minutes=minutes) and as_utc(t_start) < end for t_start, minutes in taken
    )


def day_slots(
    windows: list[DoctorAvailability], day: date, taken: list[tuple[datetime, int]], now: datetime
) -> list[Slot]:
    """Every slot of one clinic day, each marked open or not."""
    earliest = now + timedelta(minutes=LEAD_MINUTES)
    latest = now + timedelta(days=HORIZON_DAYS)
    slots: list[Slot] = []
    for window in sorted((w for w in windows if w.weekday == day.weekday()), key=lambda w: w.start_time):
        cursor, close = _at(day, window.start_time), _at(day, window.end_time)
        step = timedelta(minutes=window.slot_minutes)
        while cursor + step <= close:
            end = cursor + step
            open_ = earliest <= cursor <= latest and not _overlaps(cursor, end, taken)
            slots.append(Slot(cursor, end, open_))
            cursor = end
    return slots


def _live(db: Session, doctor_ids: list[int], start: datetime, end: datetime, ignore_id: int | None = None):
    query = db.query(Appointment.doctor_id, Appointment.date, Appointment.duration_minutes).filter(
        Appointment.doctor_id.in_(doctor_ids),
        Appointment.status != "CANCELLED",
        Appointment.date >= start - timedelta(hours=3),
        Appointment.date < end,
    )
    if ignore_id is not None:
        query = query.filter(Appointment.id != ignore_id)
    return query.all()


def windows_of(db: Session, doctor_ids: list[int]) -> dict[int, list[DoctorAvailability]]:
    grouped: dict[int, list[DoctorAvailability]] = {doctor_id: [] for doctor_id in doctor_ids}
    for row in db.query(DoctorAvailability).filter(DoctorAvailability.doctor_id.in_(doctor_ids)):
        grouped[row.doctor_id].append(row)
    return grouped


def slots_range(
    db: Session, doctor_id: int, first_day: date, days: int, now: datetime | None = None, ignore_id: int | None = None
) -> list[tuple[date, list[Slot]]]:
    now = now or now_utc()
    windows = windows_of(db, [doctor_id])[doctor_id]
    start = _at(first_day, time(0, 0))
    end = start + timedelta(days=days)
    taken = [(when, minutes) for _, when, minutes in _live(db, [doctor_id], start, end, ignore_id)]
    return [
        (first_day + timedelta(days=n), day_slots(windows, first_day + timedelta(days=n), taken, now))
        for n in range(days)
    ]


def find_open_slot(db: Session, doctor_id: int, start: datetime, ignore_id: int | None = None) -> Slot:
    """The open slot beginning exactly at `start`, or SlotUnavailable."""
    start = as_utc(start)
    day = clinic_date(start)
    for _, slots in slots_range(db, doctor_id, day, 1, ignore_id=ignore_id):
        for slot in slots:
            if slot.start == start:
                if slot.available:
                    return slot
                raise SlotUnavailable("That time has just been taken or is too soon. Please choose another slot.")
    raise SlotUnavailable("The doctor does not see patients at that time. Please choose one of the listed slots.")


def directory_availability(
    db: Session, doctor_ids: list[int], now: datetime | None = None, look_ahead_days: int = 14
) -> dict[int, tuple[bool, datetime | None]]:
    """For each doctor: is a slot open today (clinic time), and the first open slot in the next days."""
    now = now or now_utc()
    if not doctor_ids:
        return {}
    windows = windows_of(db, doctor_ids)
    today = clinic_date(now)
    start = _at(today, time(0, 0))
    end = start + timedelta(days=look_ahead_days)
    taken: dict[int, list[tuple[datetime, int]]] = {doctor_id: [] for doctor_id in doctor_ids}
    for doctor_id, when, minutes in _live(db, doctor_ids, start, end):
        taken[doctor_id].append((when, minutes))
    result: dict[int, tuple[bool, datetime | None]] = {}
    for doctor_id in doctor_ids:
        open_today, first_open = False, None
        for n in range(look_ahead_days):
            day = today + timedelta(days=n)
            free = [s for s in day_slots(windows[doctor_id], day, taken[doctor_id], now) if s.available]
            if free:
                open_today, first_open = n == 0, free[0].start
                break
        result[doctor_id] = (open_today, first_open)
    return result


# --- weekly schedule ----------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowInput:
    weekday: int
    start_time: time
    end_time: time
    slot_minutes: int


def validate_windows(windows: list[WindowInput]) -> None:
    by_day: dict[int, list[WindowInput]] = {}
    for window in windows:
        if not 0 <= window.weekday <= 6:
            raise ValueError("Weekday must be 0 (Monday) to 6 (Sunday).")
        if window.slot_minutes not in SLOT_CHOICES:
            raise ValueError(f"Appointments must be {', '.join(map(str, SLOT_CHOICES))} minutes long.")
        if window.end_time <= window.start_time:
            raise ValueError("Each window must end after it starts.")
        minutes = (
            (window.end_time.hour - window.start_time.hour) * 60 + window.end_time.minute - window.start_time.minute
        )
        if minutes < window.slot_minutes:
            raise ValueError("Each window must be long enough for at least one appointment.")
        by_day.setdefault(window.weekday, []).append(window)
    for day_windows in by_day.values():
        if len(day_windows) > MAX_WINDOWS_PER_DAY:
            raise ValueError(f"At most {MAX_WINDOWS_PER_DAY} windows a day.")
        ordered = sorted(day_windows, key=lambda w: w.start_time)
        for earlier, later in pairwise(ordered):
            if later.start_time < earlier.end_time:
                raise ValueError("Windows on the same day must not overlap.")


def save_windows(db: Session, doctor_id: int, windows: list[WindowInput]) -> list[DoctorAvailability]:
    """Replace the doctor's weekly schedule. Appointments already booked are never touched."""
    try:
        validate_windows(windows)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    db.query(DoctorAvailability).filter(DoctorAvailability.doctor_id == doctor_id).delete()
    rows = [
        DoctorAvailability(
            doctor_id=doctor_id,
            weekday=w.weekday,
            start_time=w.start_time.replace(second=0, microsecond=0),
            end_time=w.end_time.replace(second=0, microsecond=0),
            slot_minutes=w.slot_minutes,
        )
        for w in windows
    ]
    db.add_all(rows)
    db.commit()
    return sorted(rows, key=lambda r: (r.weekday, r.start_time))
