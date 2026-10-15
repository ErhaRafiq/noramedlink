"""Profiles (Module 1): every user reads and edits their own; there is no id in any path."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, require_doctor, require_patient
from models import User
from schemas import AccountUpdate, DoctorProfileUpdate, PatientProfileUpdate, ProfileOut
from services import profiles

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileOut)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return profiles.profile_out(db, current_user)


@router.patch("/profile/account", response_model=ProfileOut)
def update_account(
    payload: AccountUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return profiles.profile_out(db, profiles.update_account(db, current_user, payload))


@router.put("/patient/profile", response_model=ProfileOut)
def update_patient_profile(
    payload: PatientProfileUpdate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)
):
    return profiles.profile_out(db, profiles.update_patient(db, current_user, payload))


@router.put("/doctor/profile", response_model=ProfileOut)
def update_doctor_profile(
    payload: DoctorProfileUpdate, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    return profiles.profile_out(db, profiles.update_doctor(db, current_user, payload))
