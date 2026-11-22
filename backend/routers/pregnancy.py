"""Pregnancy status (pregnant, not pregnant, not recorded): the patient sets their own, and a doctor with an
active access grant can set it too. There is no patient id in the patient route: identity is the token, so a
patient can only ever change their own. The rules live in services/pregnancy.py."""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_doctor, require_patient
from models import User
from schemas import PregnancyStateOut, PregnancyStatusIn
from services import notifications, pregnancy
from services.dashboard_access import patient_with_active_grant

router = APIRouter(tags=["pregnancy-status"])


@router.put("/patient/pregnancy-status", response_model=PregnancyStateOut)
def set_mine(payload: PregnancyStatusIn, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = pregnancy.set_status(db, current_user, current_user, payload.status)
    db.commit()
    return PregnancyStateOut(**asdict(pregnancy.state_for(profile)))


@router.put("/doctor/patients/{patient_id}/pregnancy-status", response_model=PregnancyStateOut)
def set_for_patient(
    patient_id: int, payload: PregnancyStatusIn, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    profile = pregnancy.set_status(db, patient, doctor, payload.status)
    notifications.record_changed(db, patient.id, doctor.full_name, "pregnancy status")
    db.commit()
    return PregnancyStateOut(**asdict(pregnancy.state_for(profile)))
