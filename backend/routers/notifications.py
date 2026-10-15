"""The signed-in user's own notifications (Module 5 FE-4). Nobody sees anyone else's."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Notification, User
from pagination import PageParams, page_params
from schemas import MessageOut, NotificationOut, NotificationPage
from services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


def to_out(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        kind=row.kind,
        title=row.title,
        body=row.body,
        appointment_id=row.appointment_id,
        read=row.status != "UNREAD",
        at=notifications.shown_at(row),
    )


@router.get("", response_model=NotificationPage)
def list_notifications(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Notifications that are due now, newest first, with the unread count."""
    query = notifications.due_for(db, current_user.id)
    total = query.count()
    rows = (
        query.order_by(
            Notification.scheduled_for.desc().nullslast(), Notification.created_at.desc(), Notification.id.desc()
        )
        .offset(params.offset)
        .limit(params.limit)
        .all()
    )
    return NotificationPage(
        items=[to_out(r) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
        unread=notifications.unread_count(db, current_user.id),
    )


@router.post("/read-all", response_model=MessageOut)
def read_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifications.due_for(db, current_user.id).filter(Notification.status == "UNREAD").update(
        {"status": "READ"}, synchronize_session=False
    )
    db.commit()
    return MessageOut(message="All notifications marked as read.")


@router.post("/{notification_id}/read", response_model=MessageOut)
def read_one(notification_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(Notification, notification_id)
    # Someone else's notification looks the same as one that does not exist.
    if row is None or row.user_id != current_user.id or (row.scheduled_for and row.scheduled_for > datetime.now(UTC)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    row.status = "READ"
    db.commit()
    return MessageOut(message="Marked as read.")
