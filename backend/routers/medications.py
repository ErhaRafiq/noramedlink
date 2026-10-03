"""Patient medicine schedules (medications table).

Ported from the Next.js route /api/medicines. Separate from /patient/medicines, which
is the medicine *history* (medicine_history table).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_patient
from models import Medication, User
from schemas import MedicationScheduleCreate, MedicationScheduleOut

router = APIRouter(prefix="/patient/medications", tags=["medications"])


def medication_to_out(medication: Medication) -> MedicationScheduleOut:
    return MedicationScheduleOut(
        id=medication.id,
        patient_id=medication.user_id,
        medicine_name=medication.name,
        dosage=medication.dosage,
        instructions=medication.instructions,
        start_date=medication.start_date,
        end_date=medication.end_date,
        status=medication.status,
        created_at=medication.created_at,
    )


@router.get("", response_model=list[MedicationScheduleOut])
def list_medications(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    medications = (
        db.query(Medication)
        .filter(Medication.user_id == current_user.id)
        .order_by(Medication.created_at.desc())
        .all()
    )
    return [medication_to_out(m) for m in medications]


@router.post("", response_model=MedicationScheduleOut, status_code=status.HTTP_201_CREATED)
def create_medication(
    payload: MedicationScheduleCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    if payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date cannot be before start date.")
    medication = Medication(
        user_id=current_user.id,
        name=payload.medicine_name.strip(),
        dosage=payload.dosage.strip(),
        instructions=payload.instructions.strip() if payload.instructions and payload.instructions.strip() else None,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="ACTIVE",
    )
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication_to_out(medication)
