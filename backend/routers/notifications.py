"""The signed-in user's own notifications. Nobody sees anyone else's: another person's notification looks the
same as one that does not exist. The rules and the events live in services/notifications.py.

- `GET /notifications` lists what is due now, newest first, with filters (unread only, one category) and paging.
- `GET /notifications/unread-count` is the cheap call the bell makes every half minute.
- A notification is read one at a time or all at once, and can be dismissed (deleted: it is the user's own).
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Notification, User
from pagination import PageParams, page_params
from schemas import MessageOut, NotificationOut, NotificationPage, UnreadCountOut
from services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


def to_out(row: Notification, role: str) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        kind=row.kind,
        title=row.title,
        body=row.body,
        appointment_id=row.appointment_id,
        category=notifications.category_of(row.kind),
        link=row.link or notifications.fallback_link(row.kind, role),
        read=row.status != "UNREAD",
        read_at=row.read_at,
        at=notifications.shown_at(row),
    )


def _own(db: Session, user: User, notification_id: int) -> Notification:
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user.id or (row.scheduled_for and row.scheduled_for > datetime.now(UTC)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    return row


@router.get("", response_model=NotificationPage)
def list_notifications(
    unread_only: bool = False,
    category: Literal["appointments", "payments", "records", "account", "admin"] | None = None,
    params: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Notifications that are due now, newest first, with the unread count (of everything, not just this filter)."""
    query = notifications.due_for(db, current_user.id)
    if unread_only:
        query = query.filter(Notification.status == "UNREAD")
    if category:
        query = query.filter(notifications.kinds_filter(category))
    total = query.count()
    rows = (
        query.order_by(
            Notification.scheduled_for.desc().nullslast(), Notification.created_at.desc(), Notification.id.desc()
        )
        .offset(params.offset)
        .limit(params.limit)
        .all()
    )
    role = current_user.role.lower()
    return NotificationPage(
        items=[to_out(r, role) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
        unread=notifications.unread_count(db, current_user.id),
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return UnreadCountOut(unread=notifications.unread_count(db, current_user.id))


@router.post("/read-all", response_model=MessageOut)
def read_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifications.due_for(db, current_user.id).filter(Notification.status == "UNREAD").update(
        {"status": "READ", "read_at": datetime.now(UTC)}, synchronize_session=False
    )
    db.commit()
    return MessageOut(message="All notifications marked as read.")


@router.post("/{notification_id}/read", response_model=MessageOut)
def read_one(notification_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _own(db, current_user, notification_id)
    if row.status == "UNREAD":
        row.status, row.read_at = "READ", datetime.now(UTC)
        db.commit()
    return MessageOut(message="Marked as read.")


@router.delete("/{notification_id}", response_model=MessageOut)
def dismiss(notification_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _own(db, current_user, notification_id)
    db.delete(row)
    db.commit()
    return MessageOut(message="Notification removed.")
