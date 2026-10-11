"""Scheduled medicine doses (medicine_reminders) and their history (reminder_logs).

Ported from the Next.js routes reminders/create, reminders/today,
reminders/[id]/mark-taken and reminders/[id]/skip. Separate from /reminders, the
free-text reminders used by /dashboard.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_patient
from models import Medication, MedicineReminder, Notification, ReminderLog, User
from routers.medications import medication_to_out
from schemas import MedicineReminderCreate, MedicineReminderOut

router = APIRouter(prefix="/patient/medicine-reminders", tags=["medicine-reminders"])

DUE_WINDOW = timedelta(minutes=30)


def display_status(reminder_time: datetime, taken_at: datetime | None, skipped_at: datetime | None, now: datetime) -> str:
    """TAKEN / SKIPPED win; otherwise UPCOMING before the time, DUE_NOW for 30 minutes
    after it, then MISSED (same rules as the former lib/patient-reminders.ts)."""
    if taken_at:
        return "TAKEN"
    if skipped_at:
        return "SKIPPED"
    if reminder_time.tzinfo is None:  # SQLite returns naive datetimes (stored as UTC)
        reminder_time = reminder_time.replace(tzinfo=UTC)
    elapsed = now - reminder_time
    if elapsed >= DUE_WINDOW:
        return "MISSED"
    if elapsed >= timedelta(0):
        return "DUE_NOW"
    return "UPCOMING"


def reminder_to_out(reminder: MedicineReminder) -> MedicineReminderOut:
    return MedicineReminderOut(
        id=reminder.id,
        medication_id=reminder.medication_id,
        patient_id=reminder.patient_id,
        reminder_time=reminder.reminder_time,
        frequency=reminder.frequency,
        status=reminder.status,
        taken_at=reminder.taken_at,
        skipped_at=reminder.skipped_at,
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
        medication=medication_to_out(reminder.medication) if reminder.medication else None,
    )


def _own_reminder(db: Session, reminder_id: int, user: User) -> MedicineReminder:
    reminder = (
        db.query(MedicineReminder)
        .filter(MedicineReminder.id == reminder_id, MedicineReminder.patient_id == user.id)
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")
    return reminder


@router.post("", response_model=MedicineReminderOut, status_code=status.HTTP_201_CREATED)
def create_medicine_reminder(
    payload: MedicineReminderCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    medication = (
        db.query(Medication)
        .filter(Medication.id == payload.medication_id, Medication.user_id == current_user.id)
        .first()
    )
    if not medication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found.")

    reminder_time = payload.reminder_time
    if reminder_time.tzinfo is None:
        reminder_time = reminder_time.astimezone()  # naive input = server local time, as before
    initial_status = display_status(reminder_time, None, None, datetime.now(UTC))

    reminder = MedicineReminder(
        medication_id=medication.id,
        patient_id=current_user.id,
        reminder_time=reminder_time,
        frequency=payload.frequency.strip(),
        status=initial_status,
    )
    db.add(reminder)
    db.flush()
    db.add(ReminderLog(reminder_id=reminder.id, patient_id=current_user.id, scheduled_for=reminder_time, status=initial_status))
    # notifications.reminder_id points at the free-text reminders table, so it is left
    # empty here (the Next route wrongly stored the medicine reminder's id in it).
    db.add(
        Notification(
            user_id=current_user.id,
            title="Medicine reminder scheduled",
            body=f"{medication.name} reminder set for {reminder_time.isoformat()}",
            status="SCHEDULED",
            scheduled_for=reminder_time,
        )
    )
    db.commit()
    db.refresh(reminder)
    return reminder_to_out(reminder)


@router.get("/today", response_model=list[MedicineReminderOut])
def todays_medicine_reminders(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    now = datetime.now(UTC)
    local_now = now.astimezone()  # "today" is the server's local day, as before
    start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    reminders = (
        db.query(MedicineReminder)
        .filter(
            MedicineReminder.patient_id == current_user.id,
            MedicineReminder.reminder_time >= start_of_day,
            MedicineReminder.reminder_time < end_of_day,
        )
        .order_by(MedicineReminder.reminder_time.asc())
        .all()
    )
    changed = False
    for reminder in reminders:
        current = display_status(reminder.reminder_time, reminder.taken_at, reminder.skipped_at, now)
        if current != reminder.status:
            reminder.status = current
            changed = True
    if changed:
        db.commit()
        for reminder in reminders:
            db.refresh(reminder)
    return [reminder_to_out(r) for r in reminders]


def _record(db: Session, reminder: MedicineReminder, user: User, new_status: str) -> MedicineReminderOut:
    now = datetime.now(UTC)
    reminder.status = new_status
    if new_status == "TAKEN":
        reminder.taken_at = now
    else:
        reminder.skipped_at = now
    db.add(
        ReminderLog(
            reminder_id=reminder.id,
            patient_id=user.id,
            scheduled_for=reminder.reminder_time,
            status=new_status,
            taken_at=reminder.taken_at if new_status == "TAKEN" else None,
        )
    )
    db.commit()
    db.refresh(reminder)
    return reminder_to_out(reminder)


@router.patch("/{reminder_id}/mark-taken", response_model=MedicineReminderOut)
def mark_taken(reminder_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return _record(db, _own_reminder(db, reminder_id, current_user), current_user, "TAKEN")


@router.patch("/{reminder_id}/skip", response_model=MedicineReminderOut)
def skip(reminder_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return _record(db, _own_reminder(db, reminder_id, current_user), current_user, "SKIPPED")
