"""Body weight and height history (Module 2 / Phase 6).

The patient enters, corrects and removes their own readings. A doctor with an active access grant can read
the history and the summary, add readings, and change or remove the readings a doctor entered; a reading
entered by the other role is read-only (403). Identity comes from the token, never from a body or query.
The rules and calculations live in services/body_record.py and services/body_measurements.py.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_doctor, require_patient
from models import User
from pagination import Page, PageParams, page_params, paginate
from schemas import (
    BodyMeasurementIn,
    BodyMeasurementOut,
    BodyMeasurementUpdate,
    BodySummaryOut,
    DoctorBodySummaryOut,
    MessageOut,
)
from services import body_record, notifications
from services.dashboard_access import patient_with_active_grant
from services.profiles import age_on

router = APIRouter(tags=["body-measurements"])

WHAT = "weight or height reading"


def _history(db: Session, patient_id: int, params: PageParams) -> Page[BodyMeasurementOut]:
    page = paginate(body_record.history_query(db, patient_id), params, lambda row: row)
    return Page[BodyMeasurementOut](**{**page, "items": body_record.out_for(db, page["items"])})


# --- the patient's own history -------------------------------------------------------------------------


@router.get("/patient/body-measurements", response_model=Page[BodyMeasurementOut])
def my_history(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return _history(db, current_user.id, params)


@router.get("/patient/body-measurements/summary", response_model=BodySummaryOut)
def my_summary(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return body_record.patient_summary(db, current_user.id)


@router.post("/patient/body-measurements", response_model=BodyMeasurementOut, status_code=status.HTTP_201_CREATED)
def add_mine(payload: BodyMeasurementIn, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    row = body_record.add(db, current_user, current_user, payload)
    db.commit()
    return body_record.out_for(db, [row])[0]


@router.patch("/patient/body-measurements/{row_id}", response_model=BodyMeasurementOut)
def change_mine(
    row_id: int,
    payload: BodyMeasurementUpdate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    row = body_record.get_row(db, current_user.id, row_id)
    body_record.update(db, row, current_user, "patient", payload)
    db.commit()
    return body_record.out_for(db, [row])[0]


@router.delete("/patient/body-measurements/{row_id}", response_model=MessageOut)
def remove_mine(row_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """Hides the reading; the row is kept so the audit trail still points at something."""
    row = body_record.get_row(db, current_user.id, row_id)
    body_record.remove(db, row, current_user, "patient")
    db.commit()
    return MessageOut(message="Reading removed.")


# --- a doctor with an active grant -----------------------------------------------------------------------


@router.get("/doctor/patients/{patient_id}/body-measurements", response_model=Page[BodyMeasurementOut])
def patient_history(
    patient_id: int,
    params: PageParams = Depends(page_params),
    doctor: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    patient = patient_with_active_grant(db, doctor, patient_id, area="body measurements")
    return _history(db, patient.id, params)


@router.get("/doctor/patients/{patient_id}/body-measurements/summary", response_model=DoctorBodySummaryOut)
def patient_summary(patient_id: int, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)):
    patient = patient_with_active_grant(db, doctor, patient_id, area="body measurements")
    profile = patient.patient_profile
    return body_record.doctor_summary(db, patient, age_on(profile.date_of_birth) if profile else None)


@router.post(
    "/doctor/patients/{patient_id}/body-measurements",
    response_model=BodyMeasurementOut,
    status_code=status.HTTP_201_CREATED,
)
def add_for_patient(
    patient_id: int, payload: BodyMeasurementIn, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    row = body_record.add(db, patient, doctor, payload)
    notifications.record_changed(db, patient.id, doctor.full_name, WHAT)
    db.commit()
    return body_record.out_for(db, [row])[0]


@router.patch("/doctor/patients/{patient_id}/body-measurements/{row_id}", response_model=BodyMeasurementOut)
def change_for_patient(
    patient_id: int,
    row_id: int,
    payload: BodyMeasurementUpdate,
    doctor: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    row = body_record.get_row(db, patient.id, row_id)
    body_record.update(db, row, doctor, "doctor", payload)
    notifications.record_changed(db, patient.id, doctor.full_name, WHAT)
    db.commit()
    return body_record.out_for(db, [row])[0]


@router.delete("/doctor/patients/{patient_id}/body-measurements/{row_id}", response_model=MessageOut)
def remove_for_patient(
    patient_id: int, row_id: int, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    row = body_record.get_row(db, patient.id, row_id)
    body_record.remove(db, row, doctor, "doctor")
    notifications.record_changed(db, patient.id, doctor.full_name, WHAT)
    db.commit()
    return MessageOut(message="Reading removed.")
