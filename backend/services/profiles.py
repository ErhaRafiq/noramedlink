"""Profile management (Module 1, FE-2 and FE-3): building the profile a user sees, and saving edits.

Identity is the verified token's user. Specialization and the PMDC number belong to the admin's
verification and are never changed here; the CNIC is shown masked.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Appointment, DoctorProfile, PatientProfile, PatientReport, Payment, Prescription, User
from schemas import (
    AccountOut,
    AccountUpdate,
    ActivityOut,
    DoctorProfileOut,
    DoctorProfileUpdate,
    PatientProfileOut,
    PatientProfileUpdate,
    ProfileOut,
)


def age_on(born: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def mask_cnic(cnic: str) -> str:
    digits = "".join(ch for ch in cnic if ch.isdigit())
    return f"*****-*******-{digits[-1]}" if digits else "Not recorded"


def split_list(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def patient_out(profile: PatientProfile) -> PatientProfileOut:
    return PatientProfileOut(
        date_of_birth=profile.date_of_birth,
        age=age_on(profile.date_of_birth),
        gender=profile.gender,
        cnic_masked=mask_cnic(profile.cnic),
        city=profile.city,
        address=profile.address,
        blood_group=profile.blood_group,
        emergency_contact_name=profile.emergency_contact_name,
        emergency_contact_phone=profile.emergency_contact_phone,
    )


def doctor_out(profile: DoctorProfile) -> DoctorProfileOut:
    return DoctorProfileOut(
        pmdc_number=profile.pmdc_number,
        specialization=profile.specialization,
        verification_status=profile.verification_status,
        hospital_name=profile.hospital_name,
        city=profile.city,
        qualifications=profile.qualifications,
        experience_years=profile.experience_years,
        bio=profile.bio,
        languages=split_list(profile.languages),
        consultation_modes=split_list(profile.consultation_modes),
        consultation_fee=profile.consultation_fee,
        pmdc_verified=profile.pmdc_verified,
        pmdc_outcome=profile.pmdc_outcome,
        pmdc_checked_at=profile.pmdc_checked_at,
    )


def _count(db: Session, model, *conditions) -> int:
    return db.query(func.count(model.id)).filter(*conditions).scalar() or 0


def activity_for(db: Session, user: User) -> ActivityOut:
    """Counts of what is linked to this user; every query is filtered by the user's own id."""
    if user.patient_profile:
        return ActivityOut(
            reports=_count(db, PatientReport, PatientReport.patient_id == user.id),
            appointments=_count(db, Appointment, Appointment.user_id == user.id),
            prescriptions=_count(
                db, Prescription, Prescription.patient_id == user.id, Prescription.status == "confirmed"
            ),
            payments=_count(db, Payment, Payment.user_id == user.id),
        )
    if user.doctor_profile:
        paid = (
            db.query(func.count(Payment.id))
            .join(Appointment, Appointment.id == Payment.appointment_id)
            .filter(Appointment.doctor_id == user.id, Payment.status == "PAID")
            .scalar()
        )
        return ActivityOut(
            appointments=_count(db, Appointment, Appointment.doctor_id == user.id),
            prescriptions=_count(
                db, Prescription, Prescription.doctor_id == user.id, Prescription.status == "confirmed"
            ),
            payments=paid or 0,
        )
    return ActivityOut()


def profile_out(db: Session, user: User) -> ProfileOut:
    return ProfileOut(
        account=AccountOut(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            role=user.role.lower(),
            created_at=user.created_at,
            email_verified=user.is_email_verified,
            email_reminders=user.email_reminders,
        ),
        patient=patient_out(user.patient_profile) if user.patient_profile else None,
        doctor=doctor_out(user.doctor_profile) if user.doctor_profile else None,
        activity=activity_for(db, user),
    )


def update_account(db: Session, user: User, payload: AccountUpdate) -> User:
    taken = db.query(User.id).filter(User.phone == payload.phone, User.id != user.id).first()
    if taken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That phone number is already registered.")
    user.full_name = payload.full_name
    user.phone = payload.phone
    if payload.email_reminders is not None:
        user.email_reminders = payload.email_reminders
    db.commit()
    db.refresh(user)
    return user


def update_patient(db: Session, user: User, payload: PatientProfileUpdate) -> User:
    profile = user.patient_profile
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(user)
    return user


def update_doctor(db: Session, user: User, payload: DoctorProfileUpdate) -> User:
    profile = user.doctor_profile
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")
    data = payload.model_dump()
    data["languages"] = ", ".join(data["languages"]) or None
    data["consultation_modes"] = ",".join(data["consultation_modes"])
    for field, value in data.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(user)
    return user
