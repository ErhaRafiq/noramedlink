"""In-app notifications for patients, doctors and administrators.

What is told, to whom:
- Patient: appointment confirmed, moved, cancelled, reminders (24 hours, 1 hour and 5 minutes before), visit
  completed (please rate) or missed, payment received, refund requested / completed / needs attention, a new or
  cancelled prescription, a doctor opened their file or changed their health record, password changed.
- Doctor: a new, moved or cancelled appointment, the same reminders, the appointment was paid, a new rating,
  the account was approved or not, the PMDC badge was given or taken away.
- Administrator: a new doctor is waiting for review, a refund needs attention.

How it works: a notification is a row. A reminder is a row scheduled for later; the list shows a row only
once it is due, so no background job is needed. Every row can carry a `link` (the page it leads to, always
inside the app) and a `dedupe_key`, so an event that is delivered twice (a payment webhook, a retry) is told
once. Read notifications are cleared after 90 days. A notification never holds a diagnosis, a medicine, a
report's content or the reason for a visit: only who, what happened and when. Email is separate
(services/email_outbox.py); this is what the person sees inside the app.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session

from models import Appointment, Notification, Payment, User
from services.scheduling import CLINIC_TZ, as_utc

REMINDER_LEADS = (timedelta(hours=24), timedelta(hours=1), timedelta(minutes=5))
REMINDER_WORDS = {
    timedelta(hours=24): "tomorrow",
    timedelta(hours=1): "in an hour",
    timedelta(minutes=5): "in 5 minutes",
}
KEEP_READ = timedelta(days=90)

# Where each kind of notification leads (the page the person can act on).
PATIENT_APPOINTMENTS = "/doctors"
DOCTOR_APPOINTMENTS = "/dashboard/doctor#appointments"

CATEGORIES = {
    "appointments": "Appointments",
    "payments": "Payments",
    "records": "Health records",
    "account": "Account",
    "admin": "Admin",
}
_PREFIXES = (
    ("appointment_", "appointments"),
    ("review_", "appointments"),
    ("payment_", "payments"),
    ("prescription_", "records"),
    ("record_", "records"),
    ("access_", "records"),
    ("account_", "account"),
    ("doctor_", "account"),
    ("admin_", "admin"),
)


def category_of(kind: str) -> str:
    for prefix, category in _PREFIXES:
        if kind.startswith(prefix):
            return category
    return "account"


def kinds_filter(category: str):
    """SQL condition: notifications of this category."""
    return or_(*(Notification.kind.like(f"{prefix}%") for prefix, name in _PREFIXES if name == category))


def fallback_link(kind: str, role: str) -> str | None:
    """Where an older notification (no stored link) leads, by what it is about and who is reading."""
    if kind.startswith(("appointment_", "review_")):
        return DOCTOR_APPOINTMENTS if role == "doctor" else PATIENT_APPOINTMENTS
    if kind.startswith("payment_"):
        return "/payments"
    return None


def when_text(moment: datetime) -> str:
    """'Mon 12 Oct, 4:30 PM' in clinic time."""
    local = as_utc(moment).astimezone(CLINIC_TZ)
    return f"{local:%a} {local.day} {local:%b}, {local.hour % 12 or 12}:{local:%M} {'AM' if local.hour < 12 else 'PM'}"


def _dr(name: str) -> str:
    name = (name or "").strip()
    return name if name.lower().startswith(("dr ", "dr.")) else f"Dr. {name}"


def add(
    db: Session,
    user_id: int,
    kind: str,
    title: str,
    body: str,
    appointment_id: int | None = None,
    scheduled_for: datetime | None = None,
    *,
    link: str | None = None,
    dedupe_key: str | None = None,
) -> Notification | None:
    """Add one notification in the caller's transaction. With a `dedupe_key`, None when it was already told."""
    row = Notification(
        user_id=user_id,
        kind=kind,
        title=title[:180],
        body=body,
        appointment_id=appointment_id,
        scheduled_for=scheduled_for,
        link=link,
        dedupe_key=dedupe_key,
    )
    if dedupe_key is None:
        db.add(row)
        return row
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return None
    return row


# --- appointments --------------------------------------------------------------------------------------


def schedule_reminders(db: Session, appointment: Appointment, patient_name: str, doctor_name: str) -> None:
    """Reminders 24 hours, 1 hour and 5 minutes before, for both people, for the ones still in the future."""
    start, now = as_utc(appointment.date), datetime.now(UTC)
    text = when_text(start)
    for lead in REMINDER_LEADS:
        due = start - lead
        if due <= now:
            continue
        label = REMINDER_WORDS[lead]
        add(db, appointment.user_id, "appointment_reminder", f"Appointment {label}",
            f"Your appointment with {_dr(doctor_name)} is {text}.", appointment.id, due, link=PATIENT_APPOINTMENTS)  # fmt: skip
        if appointment.doctor_id:
            add(db, appointment.doctor_id, "appointment_reminder", f"Appointment {label}",
                f"You see {patient_name} {text}.", appointment.id, due, link=DOCTOR_APPOINTMENTS)  # fmt: skip


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
        f"Your appointment with {_dr(doctor_name)} is booked for {text}.", appointment.id, link=PATIENT_APPOINTMENTS)  # fmt: skip
    if appointment.doctor_id:
        add(db, appointment.doctor_id, "appointment_confirmed", "New appointment",
            f"{patient_name} booked you for {text}.", appointment.id, link=DOCTOR_APPOINTMENTS)  # fmt: skip
    schedule_reminders(db, appointment, patient_name, doctor_name)


def rescheduled(db: Session, appointment: Appointment, patient_name: str, doctor_name: str) -> None:
    clear_reminders(db, appointment.id)
    text = when_text(appointment.date)
    add(db, appointment.user_id, "appointment_rescheduled", "Appointment moved",
        f"Your appointment with {_dr(doctor_name)} is now {text}.", appointment.id, link=PATIENT_APPOINTMENTS)  # fmt: skip
    if appointment.doctor_id:
        add(db, appointment.doctor_id, "appointment_rescheduled", "Appointment moved",
            f"{patient_name} moved their appointment to {text}.", appointment.id, link=DOCTOR_APPOINTMENTS)  # fmt: skip
    schedule_reminders(db, appointment, patient_name, doctor_name)


def cancelled(db: Session, appointment: Appointment, patient_name: str, doctor_name: str, by_doctor: bool) -> None:
    clear_reminders(db, appointment.id)
    text = when_text(appointment.date)
    if by_doctor:
        add(db, appointment.user_id, "appointment_cancelled", "Appointment cancelled",
            f"{_dr(doctor_name)} cancelled your appointment on {text}.", appointment.id, link=PATIENT_APPOINTMENTS)  # fmt: skip
    elif appointment.doctor_id:
        add(db, appointment.doctor_id, "appointment_cancelled", "Appointment cancelled",
            f"{patient_name} cancelled their appointment on {text}.", appointment.id, link=DOCTOR_APPOINTMENTS)  # fmt: skip
    if not by_doctor:
        add(db, appointment.user_id, "appointment_cancelled", "Appointment cancelled",
            f"You cancelled your appointment with {_dr(doctor_name)} on {text}.", appointment.id, link=PATIENT_APPOINTMENTS)  # fmt: skip


def visit_finished(db: Session, appointment: Appointment, outcome: str) -> None:
    """The doctor marked the visit completed (ask for a rating) or missed."""
    text = when_text(appointment.date)
    if outcome == "COMPLETED":
        add(db, appointment.user_id, "appointment_completed", "How was your visit?",
            f"Your visit with {_dr(appointment.doctor_name)} on {text} is complete. Rate it to help other patients.",
            appointment.id, link=PATIENT_APPOINTMENTS, dedupe_key=f"visit-done:{appointment.id}")  # fmt: skip
    elif outcome == "NO_SHOW":
        add(db, appointment.user_id, "appointment_missed", "You missed an appointment",
            f"The doctor marked your appointment with {_dr(appointment.doctor_name)} on {text} as missed. "
            "You can book another time.", appointment.id, link=PATIENT_APPOINTMENTS, dedupe_key=f"visit-missed:{appointment.id}")  # fmt: skip


def review_received(db: Session, appointment: Appointment, rating: int) -> None:
    if appointment.doctor_id:
        add(db, appointment.doctor_id, "review_received", "You have a new rating",
            f"A patient rated their visit {rating} out of 5.", appointment.id, link="/dashboard/doctor",
            dedupe_key=f"review:{appointment.id}")  # fmt: skip


# --- payments ------------------------------------------------------------------------------------------


def _admins(db: Session) -> list[User]:
    return db.query(User).filter(func.upper(User.role) == "ADMIN", User.is_active.is_(True)).all()


def payment_received(db: Session, payment: Payment, appointment: Appointment | None) -> None:
    """Stripe confirmed the payment (told once, however many times the webhook is delivered)."""
    amount = f"{payment.currency.upper()} {payment.amount:,}"
    when = f" on {when_text(appointment.date)}" if appointment else ""
    doctor = _dr(appointment.doctor_name) if appointment else "your doctor"
    add(db, payment.user_id, "payment_received", "Payment received",
        f"We received your payment of {amount} for your appointment with {doctor}{when}.",
        payment.appointment_id, link="/payments", dedupe_key=f"payment-paid:{payment.id}")  # fmt: skip
    if appointment and appointment.doctor_id:
        person = db.get(User, appointment.user_id)
        add(db, appointment.doctor_id, "payment_received", "An appointment was paid",
            f"{person.full_name if person else 'A patient'} paid for the appointment{when}.",
            payment.appointment_id, link=DOCTOR_APPOINTMENTS, dedupe_key=f"payment-paid-doctor:{payment.id}")  # fmt: skip


def refund_completed(db: Session, payment: Payment) -> None:
    amount = f"{payment.currency.upper()} {payment.amount:,}"
    add(db, payment.user_id, "payment_refunded", "Your refund is complete",
        f"{amount} was returned to your card. Your bank may take a few days to show it.",
        payment.appointment_id, link="/payments", dedupe_key=f"refund-done:{payment.id}")  # fmt: skip


def refund_needs_attention(db: Session, payment: Payment) -> None:
    """Tell every administrator that a refund could not be requested (told once per payment and administrator)."""
    for admin in _admins(db):
        add(db, admin.id, "admin_refund_attention", "A refund needs attention",
            f"A refund could not be requested for payment {payment.reference}. Check it in Stripe and refund it by hand.",
            link="/admin", dedupe_key=f"refund-failed:{payment.id}:{admin.id}")  # fmt: skip


# --- health records and access -------------------------------------------------------------------------


def prescription_added(db: Session, patient_id: int, doctor_name: str, prescription_id: int | None = None) -> None:
    add(db, patient_id, "prescription_added", "A new prescription",
        f"{_dr(doctor_name)} wrote you a prescription. You can read it under Prescriptions.",
        link="/dashboard/patient#prescriptions",
        dedupe_key=f"prescription:{prescription_id}" if prescription_id else None)  # fmt: skip


def prescription_cancelled(db: Session, patient_id: int, doctor_name: str, prescription_id: int) -> None:
    add(db, patient_id, "prescription_cancelled", "A prescription was cancelled",
        f"{_dr(doctor_name)} cancelled a prescription. Check Prescriptions for what applies now.",
        link="/dashboard/patient#prescriptions", dedupe_key=f"prescription-cancelled:{prescription_id}")  # fmt: skip


def access_opened(db: Session, patient_id: int, doctor_name: str) -> None:
    add(db, patient_id, "access_opened", "A doctor opened your file",
        f"{_dr(doctor_name)} opened your health file with your one-time code. "
        "You can see everyone who opened it under Who has seen my record.",
        link="/dashboard/patient#access-history")  # fmt: skip


def record_changed(db: Session, patient_id: int, doctor_name: str, what: str) -> None:
    add(db, patient_id, "record_changed", "Your health record was updated",
        f"{_dr(doctor_name)} added or changed a {what} on your health record.",
        link="/dashboard/patient#health-record")  # fmt: skip


def password_changed(db: Session, user_id: int) -> None:
    add(db, user_id, "account_password", "Your password was changed",
        "You were signed out everywhere. If this was not you, reset your password now.", link="/forgot-password")  # fmt: skip


# --- doctors and administrators ------------------------------------------------------------------------


def doctor_decision(db: Session, doctor_user_id: int, approved: bool) -> None:
    if approved:
        add(db, doctor_user_id, "doctor_approved", "Your account was approved",
            "Patients can now find and book you. Set your weekly hours in your profile so they can pick a time.",
            link="/profile")  # fmt: skip
    else:
        add(db, doctor_user_id, "doctor_rejected", "Your registration was not approved",
            "An administrator did not approve your registration. Contact them if you think this is a mistake.",
            link="/profile")  # fmt: skip


def doctor_pmdc_changed(db: Session, doctor_user_id: int, verified: bool) -> None:
    if verified:
        add(db, doctor_user_id, "doctor_pmdc", "You are PMDC verified",
            "Your registration number was confirmed. Patients now see a PMDC verified badge on your card.", link="/profile")  # fmt: skip
    else:
        add(db, doctor_user_id, "doctor_pmdc", "Your PMDC verification was removed",
            "The badge is no longer shown. You can stay active. Ask an administrator if you want it checked again.",
            link="/profile")  # fmt: skip


def new_doctor_for_review(db: Session, doctor: User, specialization: str) -> None:
    for admin in _admins(db):
        add(db, admin.id, "admin_doctor_review", "A new doctor is waiting",
            f"{doctor.full_name} signed up as a doctor ({specialization}). Check the PMDC number before approving.",
            link="/admin#doctors", dedupe_key=f"doctor-review:{doctor.id}:{admin.id}")  # fmt: skip


# --- reading -------------------------------------------------------------------------------------------


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


def purge_old(db: Session) -> int:
    """Clear read notifications after 90 days (and anything over a year old). Returns how many."""
    now = datetime.now(UTC)
    deleted = (
        db.query(Notification)
        .filter(
            or_(
                (Notification.status != "UNREAD") & (Notification.created_at < now - KEEP_READ),
                Notification.created_at < now - timedelta(days=365),
            )
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
