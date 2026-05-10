from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Notification, NotificationToken, Reminder, User
from schemas import (
    NotificationTokenOut,
    NotificationTokenUpsert,
    ReminderCreate,
    ReminderOut,
    ReminderUpdate,
)


router = APIRouter(prefix="/reminders", tags=["reminders"])


def reminder_to_out(reminder: Reminder) -> ReminderOut:
    return ReminderOut(
        id=reminder.id,
        user_id=reminder.user_id,
        title=reminder.title,
        due_at=reminder.due_at,
        status=reminder.status,
        fcm_token=reminder.fcm_token,
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
    )


def token_to_out(token: NotificationToken) -> NotificationTokenOut:
    return NotificationTokenOut(
        id=token.id,
        user_id=token.user_id,
        token=token.token,
        platform=token.platform,
        last_seen_at=token.last_seen_at,
        created_at=token.created_at,
        updated_at=token.updated_at,
    )


@router.get("", response_model=list[ReminderOut])
def list_reminders(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reminders = (
        db.query(Reminder)
        .filter(Reminder.user_id == current_user.id)
        .order_by(Reminder.due_at.asc())
        .limit(200)
        .all()
    )
    return [reminder_to_out(reminder) for reminder in reminders]


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
def create_reminder(payload: ReminderCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reminder = Reminder(
        user_id=current_user.id,
        title=payload.title.strip(),
        due_at=payload.due_at,
        status="UPCOMING",
        fcm_token=payload.fcm_token.strip() if payload.fcm_token else None,
    )
    db.add(reminder)
    db.flush()
    db.add(
        Notification(
            user_id=current_user.id,
            reminder_id=reminder.id,
            title=reminder.title,
            body=f"Reminder scheduled for {reminder.due_at.isoformat()}",
            status="SCHEDULED",
            scheduled_for=reminder.due_at,
        )
    )
    db.commit()
    db.refresh(reminder)
    return reminder_to_out(reminder)


@router.put("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: int,
    payload: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == current_user.id).first()
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")

    if payload.title is not None:
        reminder.title = payload.title.strip()
    if payload.due_at is not None:
        reminder.due_at = payload.due_at
    if payload.status is not None:
        reminder.status = payload.status.strip().upper()
    if payload.fcm_token is not None:
        reminder.fcm_token = payload.fcm_token.strip() or None

    db.commit()
    db.refresh(reminder)
    return reminder_to_out(reminder)


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == current_user.id).first()
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")

    db.delete(reminder)
    db.commit()
    return {"message": "Reminder deleted successfully."}


@router.post("/fcm-token", response_model=NotificationTokenOut)
def upsert_fcm_token(
    payload: NotificationTokenUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    token = db.query(NotificationToken).filter(NotificationToken.token == payload.token.strip()).first()
    if token:
        token.user_id = current_user.id
        token.platform = payload.platform.strip() or "web"
        token.last_seen_at = now
    else:
        token = NotificationToken(
            user_id=current_user.id,
            token=payload.token.strip(),
            platform=payload.platform.strip() or "web",
            last_seen_at=now,
        )
        db.add(token)

    db.commit()
    db.refresh(token)
    return token_to_out(token)
