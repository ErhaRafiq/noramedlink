"""Appointment rules (Module 5 FE-3): booking into an open slot, rescheduling, cancelling, finishing,
and reviewing. Routers check who the caller is; the rules live here.

Status: BOOKED, then COMPLETED, NO_SHOW or CANCELLED (final). Only the doctor completes a visit, and only
once it has started. A patient cancels or moves a booking only before it starts.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Appointment, AppointmentReview, User
from services import notifications, payments
from services.scheduling import SlotUnavailable, as_utc, find_open_slot

FINAL_STATUSES = {"COMPLETED", "NO_SHOW", "CANCELLED"}


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _open_slot(db: Session, doctor_id: int, start: datetime, ignore_id: int | None = None):
    try:
        return find_open_slot(db, doctor_id, start, ignore_id)
    except SlotUnavailable as error:
        raise _conflict(str(error)) from error


def _patient_is_free(db: Session, patient_id: int, start: datetime, minutes: int, ignore_id: int | None = None) -> None:
    end = start + timedelta(minutes=minutes)
    query = db.query(Appointment.date, Appointment.duration_minutes).filter(
        Appointment.user_id == patient_id,
        Appointment.status != "CANCELLED",
        Appointment.date > start - timedelta(hours=3),
        Appointment.date < end,
    )
    if ignore_id is not None:
        query = query.filter(Appointment.id != ignore_id)
    for other_start, other_minutes in query:
        if as_utc(other_start) < end and start < as_utc(other_start) + timedelta(minutes=other_minutes):
            raise _conflict("You already have an appointment at that time.")


def flush_or_conflict(db: Session) -> None:
    """Write now so the database's one-booking-per-slot rule is checked; a race loses with a clear message."""
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise _conflict("That time has just been taken. Please choose another slot.") from error


def create(
    db: Session, patient: User, doctor: User, start: datetime, mode: str, reason: str | None, notes: str | None
) -> Appointment:
    profile = doctor.doctor_profile
    modes = [m for m in (profile.consultation_modes if profile else "").split(",") if m]
    if mode not in modes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This doctor does not offer that type of consultation.",
        )
    start = as_utc(start)
    slot = _open_slot(db, doctor.id, start)
    _patient_is_free(db, patient.id, slot.start, slot.minutes)
    appointment = Appointment(
        user_id=patient.id,
        doctor_id=doctor.id,
        doctor_name=doctor.full_name,
        specialty=profile.specialization if profile else None,
        reason=reason,
        notes=notes,
        date=slot.start,
        duration_minutes=slot.minutes,
        mode=mode,
        status="BOOKED",
        payment_status="PENDING",
    )
    db.add(appointment)
    flush_or_conflict(db)
    notifications.booked(db, appointment, patient.full_name, doctor.full_name)
    return appointment


def _require_booked(appointment: Appointment) -> None:
    if appointment.status.upper() in FINAL_STATUSES:
        raise _conflict(f"This appointment is already {appointment.status.lower().replace('_', ' ')}.")


def reschedule(db: Session, appointment: Appointment, new_start: datetime, patient: User) -> Appointment:
    _require_booked(appointment)
    if as_utc(appointment.date) <= datetime.now(UTC):
        raise _conflict("This appointment has already started and can no longer be moved.")
    slot = _open_slot(db, appointment.doctor_id, as_utc(new_start), ignore_id=appointment.id)
    _patient_is_free(db, patient.id, slot.start, slot.minutes, ignore_id=appointment.id)
    appointment.date = slot.start
    appointment.duration_minutes = slot.minutes
    flush_or_conflict(db)
    notifications.rescheduled(db, appointment, patient.full_name, appointment.doctor_name)
    return appointment


def cancel(db: Session, appointment: Appointment, patient: User, by_doctor: bool) -> Appointment:
    _require_booked(appointment)
    if not by_doctor and as_utc(appointment.date) <= datetime.now(UTC):
        raise _conflict("This appointment has already started and can no longer be cancelled.")
    appointment.status = "CANCELLED"
    notifications.cancelled(db, appointment, patient.full_name, appointment.doctor_name, by_doctor)
    payments.refund_for_cancellation(db, appointment)
    return appointment


def finish(db: Session, appointment: Appointment, outcome: str) -> Appointment:
    """The doctor records that the visit happened (COMPLETED) or the patient did not come (NO_SHOW)."""
    _require_booked(appointment)
    if as_utc(appointment.date) > datetime.now(UTC):
        raise _conflict("This appointment has not started yet.")
    appointment.status = outcome
    return appointment


def create_review(db: Session, appointment: Appointment, rating: int, comment: str | None) -> AppointmentReview:
    if appointment.status.upper() != "COMPLETED":
        raise _conflict("You can rate a doctor after the appointment is completed.")
    if db.query(AppointmentReview.id).filter(AppointmentReview.appointment_id == appointment.id).first():
        raise _conflict("You have already rated this appointment.")
    review = AppointmentReview(
        appointment_id=appointment.id,
        doctor_id=appointment.doctor_id,
        patient_id=appointment.user_id,
        rating=rating,
        comment=comment,
    )
    db.add(review)
    return review


def ratings_for(db: Session, doctor_ids: list[int]) -> dict[int, tuple[float, int]]:
    """doctor id -> (average rating rounded to one decimal, number of ratings); doctors without any are absent."""
    if not doctor_ids:
        return {}
    rows = (
        db.query(AppointmentReview.doctor_id, func.avg(AppointmentReview.rating), func.count(AppointmentReview.id))
        .filter(AppointmentReview.doctor_id.in_(doctor_ids))
        .group_by(AppointmentReview.doctor_id)
        .all()
    )
    return {doctor_id: (round(float(avg), 1), count) for doctor_id, avg, count in rows}
