from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_admin
from models import Appointment, DoctorProfile, MedicalDocument, PatientReport, User


router = APIRouter(prefix="/api/admin", tags=["admin"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def today_bounds() -> tuple[datetime, datetime]:
    now = utc_now()
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "fullName": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role.lower(),
        "isActive": user.is_active,
        "isEmailVerified": user.is_email_verified,
        "isIdentityVerified": user.is_identity_verified,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
    }


def pending_doctor_out(profile: DoctorProfile) -> dict:
    return {
        "id": profile.id,
        "userId": profile.user_id,
        "fullName": profile.user.full_name if profile.user else "",
        "email": profile.user.email if profile.user else "",
        "phone": profile.user.phone if profile.user else "",
        "pmdcNumber": profile.pmdc_number,
        "specialization": profile.specialization,
        "hospitalName": profile.hospital_name,
        "verificationStatus": profile.verification_status,
        "createdAt": profile.created_at,
    }


@router.get("/dashboard-stats")
def dashboard_stats(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    today_start, today_end = today_bounds()
    reports_uploaded = db.query(PatientReport.id).count() + db.query(MedicalDocument.id).count()

    return {
        "totalUsers": db.query(User.id).count(),
        "activeDoctors": (
            db.query(DoctorProfile.id)
            .filter(func.lower(DoctorProfile.verification_status).in_(["approved", "verified"]))
            .count()
        ),
        "reportsUploaded": reports_uploaded,
        "appointmentsToday": (
            db.query(Appointment.id)
            .filter(Appointment.date >= today_start, Appointment.date < today_end)
            .count()
        ),
        "pendingDoctors": (
            db.query(DoctorProfile.id)
            .filter(func.lower(DoctorProfile.verification_status) == "pending")
            .count()
        ),
    }


@router.get("/users")
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [user_out(user) for user in users]


@router.get("/doctors/pending")
def pending_doctors(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    doctors = (
        db.query(DoctorProfile)
        .join(User, DoctorProfile.user_id == User.id)
        .filter(func.lower(DoctorProfile.verification_status) == "pending")
        .order_by(DoctorProfile.created_at.desc())
        .all()
    )
    return [pending_doctor_out(profile) for profile in doctors]


def update_doctor_status(doctor_profile_id: int, next_status: str, db: Session) -> dict:
    profile = db.get(DoctorProfile, doctor_profile_id)
    if not profile:
        profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == doctor_profile_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")

    profile.verification_status = next_status
    if profile.user:
        profile.user.is_identity_verified = next_status == "approved"
    db.commit()
    db.refresh(profile)
    return pending_doctor_out(profile)


@router.patch("/doctors/{doctor_id}/approve")
def approve_doctor(
    doctor_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_doctor_status(doctor_id, "approved", db)


@router.patch("/doctors/{doctor_id}/reject")
def reject_doctor(
    doctor_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_doctor_status(doctor_id, "rejected", db)


@router.get("/recent-activity")
def recent_activity(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    activities: list[dict] = []

    for user in db.query(User).order_by(User.created_at.desc()).limit(5).all():
        activities.append(
            {
                "id": f"user-{user.id}",
                "type": "user",
                "title": f"{user.full_name} registered",
                "description": f"{user.role.lower()} account",
                "createdAt": user.created_at,
            }
        )

    for report in db.query(PatientReport).order_by(PatientReport.upload_date.desc()).limit(5).all():
        activities.append(
            {
                "id": f"report-{report.id}",
                "type": "report",
                "title": report.title,
                "description": "Patient report uploaded",
                "createdAt": report.upload_date,
            }
        )

    for appointment in db.query(Appointment).order_by(Appointment.created_at.desc()).limit(5).all():
        activities.append(
            {
                "id": f"appointment-{appointment.id}",
                "type": "appointment",
                "title": appointment.doctor_name,
                "description": appointment.status,
                "createdAt": appointment.created_at,
            }
        )

    return sorted(activities, key=lambda item: item["createdAt"], reverse=True)[:10]
