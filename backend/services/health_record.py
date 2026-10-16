"""Structured allergies, diagnoses and long-term conditions (Module 2).

The patient edits their own list; a doctor with an active access grant can add and change entries too.
The medication-safety check reads the active entries (services/mscie/context.py). Nothing is deleted:
"removed" hides an entry from the lists, "resolved" keeps it as history.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import PatientHealthEntry, User
from schemas import HealthEntryOut
from services import knowledge

MAX_ENTRIES = 100


def recognised(kind: str, name: str) -> bool:
    """Whether the medication check knows this word (so the patient is told when it cannot use an entry)."""
    key = " ".join(name.lower().split())
    if kind == "allergy":
        return knowledge.resolve_medication(key) is not None or key in knowledge.allergy_classes()
    return bool(knowledge.find_conditions(name))


def canonical_condition(name: str) -> str:
    found = knowledge.find_conditions(name)
    return found[0].info.name if found else name


def to_out(entry: PatientHealthEntry, added_by: dict[int, str]) -> HealthEntryOut:
    return HealthEntryOut(
        id=entry.id,
        kind=entry.kind,
        name=entry.name,
        note=entry.note,
        severity=entry.severity,
        since=entry.since,
        status=entry.status,
        added_by_role=entry.added_by_role,
        added_by_name=added_by.get(entry.added_by_id) if entry.added_by_role == "doctor" else None,
        recognised=recognised(entry.kind, entry.name),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _names(db: Session, entries: list[PatientHealthEntry]) -> dict[int, str]:
    ids = {e.added_by_id for e in entries if e.added_by_id and e.added_by_role == "doctor"}
    return {u.id: u.full_name for u in db.query(User).filter(User.id.in_(ids))} if ids else {}


def out_for(db: Session, entries: list[PatientHealthEntry]) -> list[HealthEntryOut]:
    names = _names(db, entries)
    return [to_out(e, names) for e in entries]


def list_entries(db: Session, patient_id: int) -> list[HealthEntryOut]:
    entries = (
        db.query(PatientHealthEntry)
        .filter(PatientHealthEntry.patient_id == patient_id, PatientHealthEntry.status != "removed")
        .order_by(PatientHealthEntry.kind, PatientHealthEntry.status, PatientHealthEntry.name)
        .all()
    )
    return out_for(db, entries)


def active_entries(db: Session, patient_id: int) -> list[PatientHealthEntry]:
    return (
        db.query(PatientHealthEntry)
        .filter(PatientHealthEntry.patient_id == patient_id, PatientHealthEntry.status == "active")
        .order_by(PatientHealthEntry.id)
        .all()
    )


def get_entry(db: Session, patient_id: int, entry_id: int) -> PatientHealthEntry:
    entry = (
        db.query(PatientHealthEntry)
        .filter(
            PatientHealthEntry.id == entry_id,
            PatientHealthEntry.patient_id == patient_id,
            PatientHealthEntry.status != "removed",
        )
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found.")
    return entry


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _check_duplicate(db: Session, patient_id: int, kind: str, name: str, ignore_id: int | None = None) -> None:
    query = db.query(PatientHealthEntry).filter(
        PatientHealthEntry.patient_id == patient_id,
        PatientHealthEntry.kind == kind,
        PatientHealthEntry.status == "active",
    )
    if ignore_id is not None:
        query = query.filter(PatientHealthEntry.id != ignore_id)
    if any(e.name.lower() == name.lower() for e in query):
        raise _conflict("This is already on the list.")


def create(
    db: Session,
    patient_id: int,
    author: User,
    *,
    kind: str,
    name: str,
    note: str | None,
    severity: str | None,
    since: date | None,
) -> PatientHealthEntry:
    count = (
        db.query(PatientHealthEntry.id)
        .filter(PatientHealthEntry.patient_id == patient_id, PatientHealthEntry.status != "removed")
        .count()
    )
    if count >= MAX_ENTRIES:
        raise _conflict(f"The list is full ({MAX_ENTRIES} entries). Remove one that is no longer needed.")
    _check_duplicate(db, patient_id, kind, name)
    entry = PatientHealthEntry(
        patient_id=patient_id,
        kind=kind,
        name=name,
        note=note,
        severity=severity if kind == "allergy" else None,
        since=since,
        status="active",
        added_by_id=author.id,
        added_by_role=author.role.lower(),
    )
    db.add(entry)
    db.flush()
    return entry


def update(db: Session, entry: PatientHealthEntry, changes: dict) -> PatientHealthEntry:
    """Apply only the fields that were sent."""
    if changes.get("name") is not None:
        _check_duplicate(db, entry.patient_id, entry.kind, changes["name"], ignore_id=entry.id)
        entry.name = changes["name"]
    for field in ("note", "since"):
        if field in changes:
            setattr(entry, field, changes[field])
    if "severity" in changes:
        if entry.kind != "allergy" and changes["severity"] is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only allergies have a severity."
            )
        entry.severity = changes["severity"]
    if changes.get("status") is not None:
        if changes["status"] == "active":
            _check_duplicate(db, entry.patient_id, entry.kind, entry.name, ignore_id=entry.id)
        entry.status = changes["status"]
    db.flush()
    return entry
