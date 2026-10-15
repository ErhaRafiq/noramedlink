"""In-app notifications (Module 5 FE-4): appointment confirmations, changes and reminders for patients
and doctors. Reminders are rows scheduled for later; the list shows a notification only once it is due,
so no background job is needed. (Email or SMS would need a mail or SMS provider; none is configured.)
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from models import Appointment, Notification
from services.scheduling import CLINIC_TZ, as_utc

REMINDER_LEADS = (timedelta(hours=24), timedelta(hours=1))


def when_text(moment: datetime) -> str:
    """'Mon 12 Oct, 4:30 PM' in clinic time."""
    local = as_utc(moment).astimezone(CLINIC_TZ)
    return f"{local:%a} {local.day} {local:%b}, {local.hour % 12 or 12}:{local:%M} {'AM' if local.hour < 12 else 'PM'}"


def add(
    db: Session,
    user_id: int,
    kind: str,
    title: str,
    body: str,
    appointment_id: int | None = None,
    scheduled_for: datetime | None = None,
) -> Notification:
    row = Notification(
        user_id=user_id, kind=kind, title=title, body=body, appointment_id=appointment_id, scheduled_for=scheduled_for
    )
    db.add(row)
    return row


def schedule_reminders(db: Session, appointment: Appointment, patient_name: str, doctor_name: str) -> None:
    """A reminder 24 hours and 1 hour before, for both people, for the ones still in the future."""
    start, now = as_utc(appointment.date), datetime.now(UTC)
    for lead in REMINDER_LEADS:
        due = start - lead
        if due <= now:
            continue
        label = "tomorrow" if lead >= timedelta(hours=24) else "in an hour"
        text = when_text(start)
        add(db, appointment.user_id, "appointment_reminder", f"Appointment {label}",
            f"Your appointment with Dr. {doctor_name} is {text}.", appointment.id, due)  # fmt: skip
        if appointment.doctor_id:
            add(db, appointment.doctor_id, "appointment_reminder", f"Appointment {label}",
                f"You see {patient_name} {text}.", appointment.id, due)  # fmt: skip


def clear_reminders(db: Session, appointment_id: int) -> None:
    """Remove reminders that have not come due yet (the appointment moved or was cancelled)."""
    db.query(Notification).filter(
        Notification.appointment_id == appointment_id,
        Notification.kind == "appointment_reminder",
        Notification.scheduled_for > datetime.now(UTC),
    ).delete(synchronize_session=False)


def booked(db: Session, appointment: Appointment, patient_name: str, doctor_name: str) -> None:
    text = when_text(appointment.date)
    add(db, appointment.user_id, "appointment_confirmed", "Appointment confirmed",
        f"Your appointment with Dr. {doctor_name} is booked for {text}.", appointment.id)  # fmt: skip
    if appointment.doctor_id:
        add(db, appointment.doctor_id, "appointment_confirmed", "New appointment",
            f"{patient_name} booked you for {text}.", appointment.id)  # fmt: skip
    schedule_reminders(db, appointment, patient_name, doctor_name)


def rescheduled(db: Session, appointment: Appointment, patient_name: str, doctor_name: str) -> None:
    clear_reminders(db, appointment.id)
    text = when_text(appointment.date)
    add(db, appointment.user_id, "appointment_rescheduled", "Appointment moved",
        f"Your appointment with Dr. {doctor_name} is now {text}.", appointment.id)  # fmt: skip
    if appointment.doctor_id:
        add(db, appointment.doctor_id, "appointment_rescheduled", "Appointment moved",
            f"{patient_name} moved their appointment to {text}.", appointment.id)  # fmt: skip
    schedule_reminders(db, appointment, patient_name, doctor_name)


def cancelled(db: Session, appointment: Appointment, patient_name: str, doctor_name: str, by_doctor: bool) -> None:
    clear_reminders(db, appointment.id)
    text = when_text(appointment.date)
    if by_doctor:
        add(db, appointment.user_id, "appointment_cancelled", "Appointment cancelled",
            f"Dr. {doctor_name} cancelled your appointment on {text}.", appointment.id)  # fmt: skip
    elif appointment.doctor_id:
        add(db, appointment.doctor_id, "appointment_cancelled", "Appointment cancelled",
            f"{patient_name} cancelled their appointment on {text}.", appointment.id)  # fmt: skip
    if not by_doctor:
        add(db, appointment.user_id, "appointment_cancelled", "Appointment cancelled",
            f"You cancelled your appointment with Dr. {doctor_name} on {text}.", appointment.id)  # fmt: skip


def due_for(db: Session, user_id: int) -> Query:
    """Notifications the user can see now: not scheduled for later."""
    now = datetime.now(UTC)
    return db.query(Notification).filter(
        Notification.user_id == user_id, or_(Notification.scheduled_for.is_(None), Notification.scheduled_for <= now)
    )


def unread_count(db: Session, user_id: int) -> int:
    return (
        due_for(db, user_id).filter(Notification.status == "UNREAD").with_entities(func.count(Notification.id)).scalar()
        or 0
    )


def shown_at(row: Notification) -> datetime:
    return row.scheduled_for or row.created_at
