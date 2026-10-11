"""Account helpers for signup and login: normalisation, uniqueness checks, signup
OTP limits, creating the user and profile, and building auth responses.
"""

import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth import create_access_token, hash_password
from config import settings
from models import DoctorProfile, PatientProfile, SignupOtp, User
from schemas import (
    SignupOtpRequest,
    TokenResponse,
    UserOut,
)

OTP_EXPIRY_MINUTES = settings.otp_expiry_minutes


OTP_RATE_LIMIT_WINDOW_MINUTES = 15


OTP_MAX_REQUESTS_PER_WINDOW = 3


OTP_RESEND_COOLDOWN_SECONDS = 60


OTP_MAX_VERIFY_ATTEMPTS = 5


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    return " ".join(phone.strip().split())


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


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


def build_token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id), {"email": user.email, "role": user.role.lower()}),
        user=user_to_out(user),
    )


def ensure_unique_email(db: Session, email: str) -> None:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )


def ensure_unique_identity(db: Session, email: str, phone: str) -> None:
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


def validate_role_specific_fields(payload: SignupOtpRequest) -> None:
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


def enforce_otp_rate_limit(db: Session, email: str, phone: str) -> None:
    now = utc_now()
    window_start = now - timedelta(minutes=OTP_RATE_LIMIT_WINDOW_MINUTES)
    recent_requests = (
        db.query(SignupOtp)
        .filter(
            or_(SignupOtp.email == email, SignupOtp.phone == phone),
            SignupOtp.created_at >= window_start,
        )
        .order_by(SignupOtp.created_at.desc())
        .all()
    )

    if len(recent_requests) >= OTP_MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait before requesting another code.",
        )

    if recent_requests and as_utc(recent_requests[0].created_at) > now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another OTP.",
        )


def create_user_from_verified_signup(payload: SignupOtpRequest, email: str, phone: str, db: Session) -> User:
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


def normalize_signup_payload(payload: SignupOtpRequest) -> tuple[str, str]:
    return normalize_email(str(payload.email)), normalize_phone(payload.phone)


def signup_payload_json(payload: SignupOtpRequest) -> dict:
    return {
        "role": payload.role,
        "full_name": payload.full_name.strip(),
        "email": normalize_email(str(payload.email)),
        "phone": normalize_phone(payload.phone),
        "cnic": (payload.cnic or "").strip() or None,
        "date_of_birth": payload.date_of_birth.isoformat() if payload.date_of_birth else None,
        "gender": (payload.gender or "").strip() or None,
        "pmdc_number": (payload.pmdc_number or "").strip() or None,
        "specialization": (payload.specialization or "").strip() or None,
        "hospital_name": (payload.hospital_name or "").strip() or None,
    }
