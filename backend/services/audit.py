"""The audit log (FR-8.3, FR-14.3): who viewed or changed whose record, and when.

Rows hold no medical text: `detail` is a short system label ("clinical summary", "2 items, 1 override"),
never a diagnosis, medicine name or what a patient typed. Writing a row commits (a viewed page that
only reads still leaves its trace). Repeated views by the same doctor of the same area are logged once
per window, so a refreshing dashboard does not flood the log.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from models import AuditLog, User

# action -> what a person reads (patients see their own access history; admins filter by action)
ACTIONS = {
    "record.view": "viewed the patient's record",
    "file.view": "opened an uploaded report",
    "access.code_issued": "created a one-time access code",
    "access.grant": "was given access to the record",
    "access.end": "ended access to the record",
    "health_entry.add": "added to the health record",
    "health_entry.update": "changed the health record",
    "health_entry.remove": "removed from the health record",
    "prescription.confirm": "confirmed a prescription",
    "prescription.cancel": "cancelled a prescription",
    "safety.override": "overrode a medication safety alert",
    "admin.doctor_approve": "approved a doctor",
    "admin.doctor_reject": "rejected a doctor",
    "admin.pmdc_check": "checked a doctor on the PMDC register",
    "admin.pmdc_manual": "decided a doctor's PMDC verification by hand",
}
VIEW_WINDOW = timedelta(minutes=10)


def patient_wording(label: str) -> str:
    """The same label as the patient reads it: "viewed the patient's record" becomes "viewed your record"."""
    for old, new in (
        ("the health record", "your health record"),
        ("the patient's record", "your record"),
        ("the record", "your record"),
    ):
        label = label.replace(old, new)
    return label


def record(
    db: Session,
    actor: User,
    action: str,
    *,
    patient_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: str = "",
    once_per: timedelta | None = None,
    commit: bool = True,
) -> AuditLog | None:
    """Add one audit row (None when the same row was already written inside `once_per`)."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown audit action: {action}")
    detail = detail[:300]
    if once_per is not None:
        since = datetime.now(UTC) - once_per
        same = db.query(AuditLog.id).filter(
            AuditLog.actor_id == actor.id,
            AuditLog.action == action,
            AuditLog.patient_id == patient_id,
            AuditLog.target_id == target_id,
            AuditLog.detail == detail,
            AuditLog.created_at >= since,
        )
        if same.first() is not None:
            return None
    row = AuditLog(
        actor_id=actor.id,
        actor_role=actor.role.lower(),
        action=action,
        target_type=target_type,
        target_id=target_id,
        patient_id=patient_id,
        detail=detail,
    )
    db.add(row)
    if commit:
        db.commit()
    return row
