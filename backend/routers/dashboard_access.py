"""Patient home data, dashboard OTPs, and doctor access by OTP.

Ported from the Next.js routes /api/dashboard, /api/dashboard/access-otp,
/api/doctor/overview, /api/doctor/access/unlock and /api/doctor/access/end. Responses
keep the same camelCase JSON so the /dashboard and /doctor-dashboard pages are unchanged.

A doctor sees a patient's medical data (vitals, records, medications) only while an
active grant exists; appointments assigned to the doctor show the patient's name.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_doctor, require_patient
from models import Appointment, EmergencyBooking, Medication, PatientReport, User, Vitals
from rate_limit import ACCESS_CODE_LIMIT, limiter
from services.dashboard_access import (
    active_grants,
    create_dashboard_otp,
    end_access,
    ensure_otp_attempts_allowed,
    grant_access_by_otp,
    record_otp_attempt,
)

router = APIRouter(tags=["dashboard-access"])


class UnlockRequest(BaseModel):
    patient_access_otp: str = Field(alias="patientAccessOtp", min_length=1, max_length=12)


class EndAccessRequest(BaseModel):
    patient_id: int = Field(alias="patientId", gt=0)


def _vitals(v: Vitals) -> dict:
    return {"id": v.id, "bloodPressure": v.blood_pressure, "sugarLevel": v.sugar_level, "createdAt": v.created_at}


@router.post("/patient/dashboard-otp")
@limiter.limit(ACCESS_CODE_LIMIT)
def issue_dashboard_otp(request: Request, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    otp = create_dashboard_otp(db, current_user)
    return {"message": "One-time dashboard OTP generated.", "otp": {"code": otp.code, "expiresAt": otp.expires_at}}


@router.post("/doctor/access/unlock")
def unlock_patient_dashboard(
    payload: UnlockRequest,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    ensure_otp_attempts_allowed(db, current_user.id)
    grant = grant_access_by_otp(db, current_user.id, payload.patient_access_otp, commit=False)
    record_otp_attempt(db, current_user.id, "unlock", grant is not None)
    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired patient dashboard OTP.")
    patient = grant.patient
    return {
        "message": f"Temporary dashboard access unlocked for {patient.full_name}.",
        "patient": {"id": patient.id, "name": patient.full_name, "email": patient.email},
        "expiresAt": grant.expires_at,
    }


@router.post("/doctor/access/end")
def end_patient_dashboard_access(
    payload: EndAccessRequest,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    end_access(db, current_user.id, payload.patient_id)
    return {"message": "Consultation session ended. Patient dashboard access is closed."}


@router.get("/doctor/overview")
def doctor_overview(current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    """Data for the /doctor-dashboard page (former /api/doctor/overview)."""
    doctor_id = current_user.id
    appointments = (
        db.query(Appointment)
        .filter(Appointment.doctor_id == doctor_id)
        .order_by(Appointment.date.desc())
        .limit(30)
        .all()
    )
    emergency_bookings = (
        db.query(EmergencyBooking)
        .filter(EmergencyBooking.doctor_id == doctor_id)
        .order_by(EmergencyBooking.created_at.desc())
        .limit(12)
        .all()
    )
    grants = active_grants(db, doctor_id)
    access_expiry = {}
    for grant in grants:
        access_expiry.setdefault(grant.patient_id, grant.expires_at)
    access_ids = list(access_expiry)

    visible_ids = {a.user_id for a in appointments} | {b.user_id for b in emergency_bookings} | set(access_ids)
    people = {u.id: u for u in db.query(User).filter(User.id.in_(visible_ids)).all()} if visible_ids else {}

    def name_of(user_id: int) -> str:
        return people[user_id].full_name if user_id in people else f"Patient #{user_id}"

    def email_of(user_id: int) -> str:
        return people[user_id].email if user_id in people else ""

    # Medical data only for patients with an active grant.
    records, medications, latest_vitals = [], [], {}
    if access_ids:
        records = (
            db.query(PatientReport)
            .filter(PatientReport.patient_id.in_(access_ids))
            .order_by(PatientReport.upload_date.desc())
            .limit(40)
            .all()
        )
        medications = (
            db.query(Medication)
            .filter(Medication.user_id.in_(access_ids))
            .order_by(Medication.created_at.desc())
            .limit(30)
            .all()
        )
        for patient_id in access_ids:
            vital = db.query(Vitals).filter(Vitals.user_id == patient_id).order_by(Vitals.created_at.desc()).first()
            if vital:
                latest_vitals[patient_id] = vital

    record_counts: dict[int, int] = {}
    for record in records:
        record_counts[record.patient_id] = record_counts.get(record.patient_id, 0) + 1

    return {
        "doctor": {
            "id": current_user.id,
            "name": current_user.full_name,
            "email": current_user.email,
            "role": "DOCTOR",
        },
        "stats": {
            "appointments": len(appointments),
            "patients": len(access_ids),
            "emergencyBookings": len(emergency_bookings),
            "medicalRecords": len(records),
            "medications": len(medications),
        },
        "appointments": [
            {
                "id": a.id,
                "doctorName": a.doctor_name,
                "userId": a.user_id,
                "date": a.date,
                "patientName": name_of(a.user_id),
                "patientEmail": email_of(a.user_id),
                "hasDashboardAccess": a.user_id in access_expiry,
                "accessExpiresAt": access_expiry.get(a.user_id),
            }
            for a in appointments
        ],
        "emergencyBookings": [
            {
                "id": b.id,
                "userId": b.user_id,
                "patientName": b.patient_name,
                "phone": b.phone,
                "address": b.address,
                "symptoms": b.symptoms,
                "status": b.status,
                "estimatedMinutes": b.estimated_minutes,
                "createdAt": b.created_at,
                "hasDashboardAccess": b.user_id in access_expiry,
                "accessExpiresAt": access_expiry.get(b.user_id),
            }
            for b in emergency_bookings
        ],
        "patients": [
            {
                "id": patient_id,
                "name": name_of(patient_id),
                "email": email_of(patient_id),
                "latestVitals": (
                    {
                        "userId": patient_id,
                        "bloodPressure": latest_vitals[patient_id].blood_pressure,
                        "sugarLevel": latest_vitals[patient_id].sugar_level,
                        "createdAt": latest_vitals[patient_id].created_at,
                    }
                    if patient_id in latest_vitals
                    else None
                ),
                "recordCount": record_counts.get(patient_id, 0),
                "appointmentCount": sum(1 for a in appointments if a.user_id == patient_id),
                "accessExpiresAt": access_expiry[patient_id],
            }
            for patient_id in access_ids
        ],
        "medicalRecords": [
            {
                "id": r.id,
                "userId": r.patient_id,
                "title": r.title,
                "fileName": r.original_file_name,
                "scanStatus": r.ocr_status,
                "extractedText": r.formatted_text or r.extracted_text,
                "department": r.department.name if r.department else "General",
                "summary": r.summary,
                "validationStatus": r.validation_status,
                "createdAt": r.upload_date,
                "patientName": name_of(r.patient_id),
            }
            for r in records
        ],
        "medications": [
            {
                "id": m.id,
                "userId": m.user_id,
                "name": m.name,
                "dosage": m.dosage,
                "status": m.status,
                "createdAt": m.created_at,
                "patientName": name_of(m.user_id),
            }
            for m in medications
        ],
    }
