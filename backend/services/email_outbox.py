"""Appointment emails: queued with the booking, sent by a small worker, and the 5-minute reminders.

Why not a cron job: the reminder time is known the moment an appointment is booked, so a row is written then,
with the time it is due. A loop inside the server (started in main.py) sends the rows that are due, within
seconds. Nothing scans appointments, every email has a unique key so it goes once, and a move or a
cancellation withdraws a reminder that has not gone yet. The loop needs the server awake at that moment; on a
free host that sleeps, an uptime monitor pinging the site every 5 minutes keeps it awake (docs/email.md).

Rules that keep the number of emails small and each one useful:
- Only a verified address with an active account gets an email.
- A reminder is not queued when the booking is less than 15 minutes ahead (the confirmation just went), and it
  is dropped if it could not be sent within 3 minutes of its time, or if the appointment is no longer booked
  for that time. Each person can switch reminders off in their profile.
- The same email is never queued twice (the unique `dedupe_key`).
- Nothing is sent when no Resend key is set; the rows simply wait and are cleared after 30 days.
No email holds the reason for a visit, a diagnosis or a code (see email_templates.py).
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from models import Appointment, EmailOutbox, User
from services import email_client, notifications
from services.email_templates import render
from services.notifications import when_text  # 'Mon 12 Oct, 4:30 PM' in clinic time, as in the in-app notices
from services.scheduling import as_utc

log = logging.getLogger("nora.email")

RETRY_DELAYS = (30, 120, 600)  # seconds before the 2nd, 3rd and 4th try
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1
REMINDER_GRACE = timedelta(minutes=3)
NO_REMINDER_IF_SOONER_THAN = timedelta(minutes=15)
KEEP_ROWS = timedelta(days=30)
WORKER_INTERVAL_SECONDS = 20
SEND_PAUSE_SECONDS = 0.6  # Resend allows 2 requests a second


def _now() -> datetime:
    return datetime.now(UTC)


def eligible(user: User | None) -> bool:
    return bool(user and user.is_active and user.is_email_verified and user.email)


def enqueue(
    db: Session,
    *,
    user: User | None,
    kind: str,
    context: dict,
    dedupe_key: str,
    appointment_id: int | None = None,
    send_after: datetime | None = None,
    expires_at: datetime | None = None,
) -> EmailOutbox | None:
    """Queue one email in the caller's transaction. None when the person is not eligible or it is already queued."""
    if not eligible(user):
        return None
    row = EmailOutbox(
        user_id=user.id, to_address=user.email, kind=kind, context=context, dedupe_key=dedupe_key[:160],
        appointment_id=appointment_id, send_after=send_after or _now(), expires_at=expires_at,
    )  # fmt: skip
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return None  # the same email is already queued: it goes once
    return row


# --- what each appointment event queues -----------------------------------------------------------------


def _context(appointment: Appointment, patient: User, doctor: User, audience: str, recipient: User) -> dict:
    return {
        "audience": audience,
        "recipient_name": recipient.full_name,
        "patient_name": patient.full_name,
        "doctor_name": doctor.full_name,
        "when_text": when_text(appointment.date),
        "start_iso": as_utc(appointment.date).isoformat(),
        "mode": appointment.mode,
        "appointment_id": appointment.id,
    }


def _people(
    db: Session, appointment: Appointment, patient: User | None, doctor: User | None
) -> tuple[User, User] | None:
    patient = patient or db.get(User, appointment.user_id)
    doctor = doctor or (db.get(User, appointment.doctor_id) if appointment.doctor_id else None)
    return (patient, doctor) if patient and doctor else None


def _both(db: Session, appointment, patient, doctor, kind: str, key: str, extra: dict | None = None) -> None:
    for audience, recipient in (("patient", patient), ("doctor", doctor)):
        context = {**_context(appointment, patient, doctor, audience, recipient), **(extra or {})}
        enqueue(
            db,
            user=recipient,
            kind=kind,
            context=context,
            dedupe_key=f"{kind}:{key}:{recipient.id}",
            appointment_id=appointment.id,
        )
    wake()


def schedule_reminders(db: Session, appointment: Appointment, patient: User, doctor: User) -> None:
    """A reminder for each person who wants one, due `email_reminder_minutes` before the start."""
    start = as_utc(appointment.date)
    due = start - timedelta(minutes=settings.email_reminder_minutes)
    if start - _now() < NO_REMINDER_IF_SOONER_THAN:
        return
    for audience, recipient in (("patient", patient), ("doctor", doctor)):
        if not recipient.email_reminders:
            continue
        context = {
            **_context(appointment, patient, doctor, audience, recipient),
            "minutes": settings.email_reminder_minutes,
        }
        enqueue(
            db, user=recipient, kind="appointment_reminder", context=context, appointment_id=appointment.id,
            dedupe_key=f"appointment_reminder:{appointment.id}:{recipient.id}:{start:%Y%m%dT%H%M}",
            send_after=due, expires_at=due + REMINDER_GRACE,
        )  # fmt: skip


def withdraw_reminders(db: Session, appointment_id: int) -> None:
    """The appointment moved or was cancelled: reminders that have not gone yet are no longer true."""
    db.query(EmailOutbox).filter(
        EmailOutbox.appointment_id == appointment_id,
        EmailOutbox.kind == "appointment_reminder",
        EmailOutbox.status == "pending",
    ).update({EmailOutbox.status: "cancelled"}, synchronize_session=False)


def appointment_booked(
    db: Session, appointment: Appointment, patient: User | None = None, doctor: User | None = None
) -> None:
    people = _people(db, appointment, patient, doctor)
    if people:
        _both(db, appointment, *people, kind="appointment_booked", key=str(appointment.id))
        schedule_reminders(db, appointment, *people)


def appointment_moved(db: Session, appointment: Appointment, old_start: datetime, patient: User | None = None) -> None:
    people = _people(db, appointment, patient, None)
    withdraw_reminders(db, appointment.id)
    if people:
        _both(db, appointment, *people, kind="appointment_moved", key=f"{appointment.id}:{as_utc(appointment.date):%Y%m%dT%H%M}",
              extra={"old_when_text": when_text(old_start)})  # fmt: skip
        schedule_reminders(db, appointment, *people)


def appointment_cancelled(db: Session, appointment: Appointment, by_doctor: bool, patient: User | None = None) -> None:
    people = _people(db, appointment, patient, None)
    withdraw_reminders(db, appointment.id)
    if people:
        _both(db, appointment, *people, kind="appointment_cancelled", key=str(appointment.id),
              extra={"cancelled_by": "doctor" if by_doctor else "patient"})  # fmt: skip


# --- sending ---------------------------------------------------------------------------------------------

_loop: asyncio.AbstractEventLoop | None = None
_wake: asyncio.Event | None = None


def wake() -> None:
    """Ask the worker to look now (safe from any thread); without a worker the rows wait for the next run."""
    if _loop is not None and _wake is not None:
        _loop.call_soon_threadsafe(_wake.set)


def _stale_reminder(db: Session, row: EmailOutbox) -> bool:
    appointment = db.get(Appointment, row.appointment_id) if row.appointment_id else None
    if appointment is None or appointment.status.upper() != "BOOKED":
        return True
    return as_utc(appointment.date).isoformat() != (row.context or {}).get("start_iso")


def dispatch_due(
    db: Session,
    *,
    limit: int = 10,
    sender: Callable[..., str] = email_client.send,
    pause: float = SEND_PAUSE_SECONDS,
) -> int:
    """Send the emails that are due. Returns how many went. Each row is committed on its own, so a crash loses
    at most one send; the idempotency key stops that one going twice."""
    now = _now()
    rows = (
        db.query(EmailOutbox)
        .filter(EmailOutbox.status == "pending", EmailOutbox.send_after <= now)
        .order_by(EmailOutbox.send_after)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .all()
    )
    sent = 0
    for row in rows:
        if row.expires_at is not None and as_utc(row.expires_at) <= _now():
            row.status = "expired"  # a reminder that could not go in time is dropped, not sent late
        elif row.kind == "appointment_reminder" and _stale_reminder(db, row):
            row.status = "cancelled"
        else:
            try:
                rendered = render(row.kind, {**(row.context or {})})
                row.provider_id = sender(
                    to=row.to_address, subject=rendered.subject, html=rendered.html, text=rendered.text,
                    idempotency_key=row.dedupe_key, kind=row.kind,
                )  # fmt: skip
                row.status, row.sent_at, row.last_error = "sent", _now(), None
                sent += 1
            except email_client.EmailDisabled:
                db.rollback()
                return sent  # no provider: leave everything waiting
            except email_client.EmailError as error:
                row.attempts += 1
                row.last_error = str(error)[:200]
                if not error.retryable or row.attempts >= MAX_ATTEMPTS:
                    row.status = "failed"
                else:
                    row.send_after = _now() + timedelta(
                        seconds=RETRY_DELAYS[min(row.attempts - 1, len(RETRY_DELAYS) - 1)]
                    )
            except Exception:  # a template bug must not stop the other emails
                log.exception("Email %s could not be built", row.kind)
                row.status, row.last_error = "failed", "template error"
        db.commit()
        if pause and row.status == "sent":
            time.sleep(pause)
    return sent


def purge_old(db: Session) -> int:
    deleted = (
        db.query(EmailOutbox).filter(EmailOutbox.created_at < _now() - KEEP_ROWS).delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def _tick(purge: bool) -> None:
    with SessionLocal() as db:
        try:
            dispatch_due(db)
            if purge:
                purge_old(db)
                notifications.purge_old(db)
        except Exception:
            db.rollback()
            log.exception("The email worker hit an error; it will try again")


async def run_worker(stop: asyncio.Event) -> None:
    """The loop started with the server: send what is due every 20 seconds, or at once when woken."""
    global _loop, _wake
    _loop, _wake = asyncio.get_running_loop(), asyncio.Event()
    ticks = 0
    while not stop.is_set():
        if email_client.is_configured():
            await asyncio.to_thread(_tick, ticks % 180 == 0)
        ticks += 1
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_wake.wait(), timeout=WORKER_INTERVAL_SECONDS)
        _wake.clear()
    _loop = _wake = None
