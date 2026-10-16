"""Structured allergies, diagnoses and long-term conditions (Module 2).

A patient manages their own list. A doctor with an active access grant can read it and add or change
entries (never remove them). Every change and every doctor's view is written to the audit log; the log
holds the kind of entry, never its name. The rules live in services/health_record.py.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, require_doctor, require_patient
from models import User
from schemas import HealthEntryIn, HealthEntryOut, HealthEntryUpdate, HealthOptionsOut, MessageOut
from services import audit, health_record, knowledge
from services.dashboard_access import patient_with_active_grant
from services.knowledge.tables import records

router = APIRouter(tags=["health-record"])


def _changes(payload: HealthEntryUpdate) -> dict:
    return payload.model_dump(exclude_unset=True)


@router.get("/health-record/options", response_model=HealthOptionsOut)
def options(_: User = Depends(get_current_user)):
    """Names the medication check understands, offered as suggestions (any other word can still be saved)."""
    allergies = set(knowledge.allergy_classes()) | {row["generic"] for row in records("medicines")}
    return HealthOptionsOut(
        allergies=sorted(allergies),
        conditions=sorted({row["name"] for row in records("conditions")}),
    )


# --- the patient's own list ----------------------------------------------------------------------


@router.get("/patient/health-record", response_model=list[HealthEntryOut])
def my_health_record(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return health_record.list_entries(db, current_user.id)


@router.post("/patient/health-record", response_model=HealthEntryOut, status_code=status.HTTP_201_CREATED)
def add_my_entry(payload: HealthEntryIn, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    entry = health_record.create(db, current_user.id, current_user, **payload.model_dump())
    audit.record(
        db, current_user, "health_entry.add", patient_id=current_user.id, target_type="health_entry",
        target_id=entry.id, detail=health_record.kind_label(entry.kind), commit=False,
    )  # fmt: skip
    db.commit()
    return health_record.out_for(db, [entry])[0]


@router.patch("/patient/health-record/{entry_id}", response_model=HealthEntryOut)
def change_my_entry(
    entry_id: int,
    payload: HealthEntryUpdate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    entry = health_record.get_entry(db, current_user.id, entry_id)
    health_record.update(db, entry, _changes(payload))
    audit.record(
        db, current_user, "health_entry.update", patient_id=current_user.id, target_type="health_entry",
        target_id=entry.id, detail=health_record.kind_label(entry.kind), commit=False,
    )  # fmt: skip
    db.commit()
    return health_record.out_for(db, [entry])[0]


@router.delete("/patient/health-record/{entry_id}", response_model=MessageOut)
def remove_my_entry(entry_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """Hides the entry from the list; the row is kept so the audit trail still points at something."""
    entry = health_record.get_entry(db, current_user.id, entry_id)
    entry.status = "removed"
    audit.record(
        db, current_user, "health_entry.remove", patient_id=current_user.id, target_type="health_entry",
        target_id=entry.id, detail=health_record.kind_label(entry.kind), commit=False,
    )  # fmt: skip
    db.commit()
    return MessageOut(message="Removed from your health record.")


# --- a doctor with an active grant ---------------------------------------------------------------


@router.get("/doctor/patients/{patient_id}/health-record", response_model=list[HealthEntryOut])
def patient_health_record(patient_id: int, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)):
    patient = patient_with_active_grant(db, doctor, patient_id, area="health record")
    return health_record.list_entries(db, patient.id)


@router.post(
    "/doctor/patients/{patient_id}/health-record", response_model=HealthEntryOut, status_code=status.HTTP_201_CREATED
)
def add_patient_entry(
    patient_id: int, payload: HealthEntryIn, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    entry = health_record.create(db, patient.id, doctor, **payload.model_dump())
    audit.record(
        db, doctor, "health_entry.add", patient_id=patient.id, target_type="health_entry",
        target_id=entry.id, detail=health_record.kind_label(entry.kind), commit=False,
    )  # fmt: skip
    db.commit()
    return health_record.out_for(db, [entry])[0]


@router.patch("/doctor/patients/{patient_id}/health-record/{entry_id}", response_model=HealthEntryOut)
def change_patient_entry(
    patient_id: int,
    entry_id: int,
    payload: HealthEntryUpdate,
    doctor: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    entry = health_record.get_entry(db, patient.id, entry_id)
    health_record.update(db, entry, _changes(payload))
    audit.record(
        db, doctor, "health_entry.update", patient_id=patient.id, target_type="health_entry",
        target_id=entry.id, detail=health_record.kind_label(entry.kind), commit=False,
    )  # fmt: skip
    db.commit()
    return health_record.out_for(db, [entry])[0]
