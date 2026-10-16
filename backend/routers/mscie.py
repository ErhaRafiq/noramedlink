"""Module 4 (MSCIE): medication-safety checks and prescribing, for doctors with an active grant.

The engine decides alerts by fixed rules and suggests ranked alternatives; the doctor decides what
to prescribe. A high-risk alert needs a written justification, which is stored with the
prescription. Patients see their confirmed prescriptions read-only.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_doctor, require_patient
from models import Prescription, User
from pagination import Page, PageParams, page_params, paginate
from rate_limit import AI_LIMIT, limiter
from schemas import (
    LabelEvidenceOut,
    MedicationCheckOut,
    MedicationCheckRequest,
    MedicineSearchOut,
    PatientPrescriptionOut,
    PrescriptionCreate,
    PrescriptionOut,
)
from services import audit
from services.dashboard_access import patient_with_active_grant
from services.mscie import names, openfda, prescribing
from services.mscie.engine import Proposed

router = APIRouter(tags=["medication-safety"])

ADVISORY = (
    "Advisory decision support for physician review, from fixed rules and a demo knowledge base (every "
    "rule cites its source). No data does not mean safe. The physician decides what to prescribe."
)


def _proposed(items) -> list[Proposed]:
    return [Proposed(i.medicine, i.dose, i.frequency, i.duration) for i in items]


@router.get("/doctor/medicines/search", response_model=list[MedicineSearchOut])
def search_medicines(q: str = Query(min_length=2, max_length=80), doctor: User = Depends(require_doctor)):
    """Generic names, aliases and Pakistani brands; misspellings are matched approximately."""
    return names.search(q)


@router.get("/doctor/medicines/{generic}/label", response_model=LabelEvidenceOut)
@limiter.limit(AI_LIMIT)
def medicine_label(request: Request, generic: str, doctor: User = Depends(require_doctor)):
    """What the FDA label says (openFDA), as supporting evidence. Never changes an alert."""
    return openfda.label_evidence(generic)


@router.post("/doctor/patients/{patient_id}/medication-check", response_model=MedicationCheckOut)
def medication_check(
    patient_id: int,
    payload: MedicationCheckRequest,
    doctor: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    return {**prescribing.check_for_patient(db, patient, _proposed(payload.items)), "note": ADVISORY}


@router.post(
    "/doctor/patients/{patient_id}/prescriptions", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED
)
def create_prescription(
    patient_id: int, payload: PrescriptionCreate, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    justifications = {o.alert_id: o.justification for o in payload.overrides}
    try:
        prescription = prescribing.confirm(
            db,
            patient,
            doctor,
            _proposed(payload.items),
            justifications,
            payload.notes,
            [{"instructions": i.instructions, "replaced_medicine": i.replaced_medicine} for i in payload.items],
        )
    except prescribing.JustificationMissing as missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": f"A written justification (at least {prescribing.MIN_JUSTIFICATION} characters) is "
                "needed for each high-risk alert before confirming.",
                "alerts": [{"id": a["id"], "title": a["title"], "severity": a["severity"]} for a in missing.alerts],
            },
        ) from missing
    audit.record(
        db, doctor, "prescription.confirm", patient_id=patient.id, target_type="prescription",
        target_id=prescription.id, detail=f"{len(prescription.items)} item(s), {len(prescription.overrides)} override(s)",
    )  # fmt: skip
    for override in prescription.overrides:
        audit.record(
            db, doctor, "safety.override", patient_id=patient.id, target_type="prescription",
            target_id=prescription.id, detail=f"{override.alert_severity} alert, written reason given",
        )  # fmt: skip
    return prescribing.to_out(prescription)


@router.get("/doctor/patients/{patient_id}/prescriptions", response_model=Page[PrescriptionOut])
def list_prescriptions(
    patient_id: int,
    params: PageParams = Depends(page_params),
    doctor: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    patient = patient_with_active_grant(db, doctor, patient_id, area="prescriptions")
    query = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
    )
    return paginate(query, params, prescribing.to_out)


@router.post("/doctor/patients/{patient_id}/prescriptions/{prescription_id}/cancel", response_model=PrescriptionOut)
def cancel_prescription(
    patient_id: int, prescription_id: int, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    patient = patient_with_active_grant(db, doctor, patient_id)
    prescription = (
        db.query(Prescription).filter(Prescription.id == prescription_id, Prescription.patient_id == patient.id).first()
    )
    if prescription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found.")
    if prescription.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the prescribing doctor can cancel it.")
    if prescription.status != "confirmed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This prescription is already cancelled.")
    cancelled = prescribing.cancel(db, prescription)
    audit.record(
        db, doctor, "prescription.cancel", patient_id=patient.id, target_type="prescription", target_id=cancelled.id
    )
    return prescribing.to_out(cancelled)


@router.get("/patient/prescriptions", response_model=Page[PatientPrescriptionOut])
def my_prescriptions(
    params: PageParams = Depends(page_params), patient: User = Depends(require_patient), db: Session = Depends(get_db)
):
    query = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
    )
    return paginate(query, params, prescribing.to_patient_out)
