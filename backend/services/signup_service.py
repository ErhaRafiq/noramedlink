"""Account helpers for signup and login: normalisation, uniqueness checks, creating the
user and profile, and building auth responses.
"""

import re
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import hash_password
from config import settings
from models import DoctorProfile, PatientProfile, User
from schemas import SignupRequest, TokenResponse, UserOut
from services.sessions import start_session


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    return " ".join(phone.strip().split())


def utc_now() -> datetime:
    return datetime.now(UTC)


def admin_invite_code() -> str:
    return settings.admin_invite_code


def user_to_out(user: User) -> UserOut:
    verification_status = "pending"
    normalized_role = user.role.lower()
    if normalized_role == "patient" and user.patient_profile:
        verification_status = user.patient_profile.verification_status
    if normalized_role == "doctor" and user.doctor_profile:
        verification_status = user.doctor_profile.verification_status
    if normalized_role == "admin":
        verification_status = "verified" if user.is_email_verified else "pending"

    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=normalized_role,
        phone=user.phone,
        is_email_verified=user.is_email_verified,
        is_identity_verified=user.is_identity_verified,
        verification_status=verification_status,
    )


def build_token_response(db: Session, user: User) -> TokenResponse:
    """Start a sign-in session for the user: an access token and a refresh token."""
    access, refresh = start_session(db, user)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh, user=user_to_out(user))


def normalize_pmdc(value: str) -> str:
    """PMDC/PMC numbers compare without case or spaces: "PMC 12345" == "pmc12345"."""
    return re.sub(r"\s+", "", value or "").lower()


def pmdc_matches(value: str):
    """SQL condition: a doctor profile whose PMDC/PMC number equals `value` once normalised."""
    return func.lower(func.replace(DoctorProfile.pmdc_number, " ", "")) == normalize_pmdc(value)


def ensure_unique_pmdc(db: Session, pmdc_number: str) -> None:
    if db.query(DoctorProfile.id).filter(pmdc_matches(pmdc_number)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This PMDC/PMC registration number is already registered.",
        )


def ensure_unique_identity(db: Session, email: str, phone: str, pmdc_number: str | None = None) -> None:
    """Email and phone are unique per account; a doctor's PMDC/PMC number is unique too."""
    existing_email = db.query(User.id).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    existing_phone = db.query(User.id).filter(User.phone == phone).first()
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already registered",
        )

    if pmdc_number and pmdc_number.strip():
        ensure_unique_pmdc(db, pmdc_number)


def doctor_pmdc(payload: SignupRequest) -> str | None:
    return payload.pmdc_number if payload.role == "doctor" else None


def validate_role_specific_fields(payload: SignupRequest) -> None:
    role = payload.role
    if role == "patient":
        cnic = (payload.cnic or "").strip()
        if not cnic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="CNIC number is required for patient signup."
            )
        if not re.fullmatch(r"(?:\d{5}-\d{7}-\d|\d{13})", cnic):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CNIC must be 13 digits or formatted like 12345-1234567-1.",
            )
        if not payload.date_of_birth or not (payload.gender or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date of birth and gender are required for patient signup.",
            )
        return

    if role == "doctor":
        if not (payload.pmdc_number or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PMDC/PMC registration number is required for doctor signup.",
            )
        if not (payload.specialization or "").strip() or not (payload.hospital_name or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specialization and hospital/clinic name are required for doctor signup.",
            )
        return

    submitted_code = (payload.admin_invite_code or "").strip()
    if not submitted_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin invite code is required")

    configured_code = admin_invite_code()
    if not configured_code or submitted_code != configured_code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin invite code")


def create_user(payload: SignupRequest, email: str, phone: str, db: Session) -> User:
    role = payload.role.upper()
    is_admin = role == "ADMIN"
    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role=role,
        phone=phone,
        is_email_verified=True,
        is_identity_verified=is_admin,
    )
    db.add(user)
    db.flush()

    if payload.role == "patient":
        db.add(
            PatientProfile(
                user_id=user.id,
                cnic=(payload.cnic or "").strip(),
                date_of_birth=payload.date_of_birth,
                gender=(payload.gender or "").strip(),
                verification_status="pending",
            )
        )
    elif payload.role == "doctor":
        db.add(
            DoctorProfile(
                user_id=user.id,
                pmdc_number=(payload.pmdc_number or "").strip(),
                specialization=(payload.specialization or "").strip(),
                hospital_name=(payload.hospital_name or "").strip(),
                verification_status="pending",
            )
        )

    return user


def normalize_signup_payload(payload: SignupRequest) -> tuple[str, str]:
    return normalize_email(str(payload.email)), normalize_phone(payload.phone)
