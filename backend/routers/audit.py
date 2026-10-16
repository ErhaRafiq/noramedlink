"""The audit log: the admin's filterable view, and each patient's own access history (FR-8.3, FR-14.3).

Rows are written by services/audit.py from the places that read or change records. Nothing here can
change or delete a row. A patient sees only who accessed their own record, never other patients' rows.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_admin, require_patient
from models import AuditLog, User
from pagination import Page, PageParams, page_params, paginate
from schemas import AccessHistoryOut, AuditLogOut
from services.audit import ACTIONS

router = APIRouter(tags=["audit"])


def _names(db: Session, ids: set[int | None]) -> dict[int, str]:
    wanted = {i for i in ids if i is not None}
    return {u.id: u.full_name for u in db.query(User).filter(User.id.in_(wanted))} if wanted else {}


@router.get("/api/admin/audit-log/actions", response_model=dict[str, str])
def audit_actions(_: User = Depends(require_admin)):
    """Every action the log records, with how it is worded, for the filter."""
    return ACTIONS


@router.get("/api/admin/audit-log", response_model=Page[AuditLogOut])
def audit_log(
    action: str | None = Query(default=None, max_length=60),
    actor_role: Literal["patient", "doctor", "admin"] | None = None,
    subject: int | None = Query(
        default=None, ge=1, description="Only rows about this patient (a filter, not an identity)."
    ),
    params: PageParams = Depends(page_params),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if action is not None and action not in ACTIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown action.")
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if actor_role:
        query = query.filter(AuditLog.actor_role == actor_role)
    if subject:
        query = query.filter(AuditLog.patient_id == subject)
    page = paginate(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()), params, lambda row: row)
    names = _names(db, {r.actor_id for r in page["items"]} | {r.patient_id for r in page["items"]})
    items = [
        AuditLogOut(
            id=r.id,
            action=r.action,
            action_label=ACTIONS.get(r.action, r.action),
            actor_id=r.actor_id,
            actor_name=names.get(r.actor_id),
            actor_role=r.actor_role,
            patient_id=r.patient_id,
            patient_name=names.get(r.patient_id),
            target_type=r.target_type,
            target_id=r.target_id,
            detail=r.detail,
            created_at=r.created_at,
        )
        for r in page["items"]
    ]
    return {**page, "items": items}


@router.get("/patient/access-history", response_model=Page[AccessHistoryOut])
def access_history(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Who else (doctors, administrators) viewed or changed this patient's record, newest first."""
    query = db.query(AuditLog).filter(AuditLog.patient_id == current_user.id, AuditLog.actor_role != "patient")
    page = paginate(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()), params, lambda row: row)
    names = _names(db, {r.actor_id for r in page["items"]})
    items = [
        AccessHistoryOut(
            id=r.id,
            action=r.action,
            action_label=ACTIONS.get(r.action, r.action),
            actor_name=names.get(r.actor_id),
            actor_role=r.actor_role,
            detail=r.detail,
            created_at=r.created_at,
        )
        for r in page["items"]
    ]
    return {**page, "items": items}
