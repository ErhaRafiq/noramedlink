import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import create_access_token, hash_password, verify_password
from database import get_db
from dependencies import get_current_user
from models import DoctorProfile, PatientProfile, SignupOtp, User
from schemas import (
    DoctorSignupRequest,
    LoginRequest,
    PatientSignupRequest,
    SignupOtpRequest,
    TokenResponse,
    UserOut,
    VerifySignupOtpRequest,
)
from services.otp_delivery_service import OtpDeliveryError, send_email_otp, send_sms_otp


router = APIRouter(prefix="/auth", tags=["auth"])

OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
OTP_RATE_LIMIT_WINDOW_MINUTES = 15
OTP_MAX_REQUESTS_PER_WINDOW = 3
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_VERIFY_ATTEMPTS = 5


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    return " ".join(phone.strip().split())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def admin_invite_code() -> str:
    return (
        os.getenv("ADMIN_INVITE_CODE", "").strip()
        or os.getenv("ADMIN_SIGNUP_CODE", "").strip()
    )


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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CNIC number is required for patient signup.")
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


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupOtpRequest, db: Session = Depends(get_db)):
    email, phone = normalize_signup_payload(payload)
    validate_role_specific_fields(payload)
    ensure_unique_identity(db, email, phone)

    try:
        user = create_user_from_verified_signup(payload, email, phone, db)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc

    return build_token_response(user)


@router.post("/request-otp")
def request_signup_otp(payload: SignupOtpRequest, db: Session = Depends(get_db)):
    email, phone = normalize_signup_payload(payload)
    validate_role_specific_fields(payload)
    ensure_unique_identity(db, email, phone)
    enforce_otp_rate_limit(db, email, phone)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    otp_record = SignupOtp(
        email=email,
        phone=phone,
        role=payload.role,
        otp_hash=hash_password(otp),
        expires_at=utc_now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
        attempts=0,
        verified=False,
        payload_json=signup_payload_json(payload),
    )
    db.add(otp_record)

    try:
        send_email_otp(email, otp)
        send_sms_otp(phone, otp)
        db.commit()
    except OtpDeliveryError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    message = (
        "OTP sent successfully. Please check backend terminal in development mode."
        if os.getenv("OTP_DEV_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
        else "OTP sent successfully. Please check your email."
    )
    return {
        "message": message,
        "expires_in_seconds": OTP_EXPIRY_MINUTES * 60,
    }


@router.post("/verify-otp-signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def verify_otp_signup(payload: VerifySignupOtpRequest, db: Session = Depends(get_db)):
    email, phone = normalize_signup_payload(payload)
    validate_role_specific_fields(payload)
    ensure_unique_identity(db, email, phone)

    otp_record = (
        db.query(SignupOtp)
        .filter(
            SignupOtp.email == email,
            SignupOtp.phone == phone,
            SignupOtp.role == payload.role,
            SignupOtp.verified.is_(False),
        )
        .order_by(SignupOtp.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP.")

    if otp_record.attempts >= OTP_MAX_VERIFY_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP verification attempts. Please request a new code.",
        )

    if as_utc(otp_record.expires_at) <= utc_now():
        otp_record.attempts += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expired OTP. Please request a new code.")

    if not verify_password(payload.otp, otp_record.otp_hash):
        otp_record.attempts += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP.")

    otp_record.verified = True
    try:
        user = create_user_from_verified_signup(payload, email, phone, db)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc

    return build_token_response(user)


@router.post("/signup/patient", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup_patient(payload: PatientSignupRequest, db: Session = Depends(get_db)):
    email = normalize_email(str(payload.email))
    phone = normalize_phone(payload.phone)
    ensure_unique_identity(db, email, phone)

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role="PATIENT",
        phone=phone,
        is_email_verified=False,
        is_identity_verified=False,
    )
    db.add(user)
    db.flush()

    profile = PatientProfile(
        user_id=user.id,
        cnic=payload.cnic.strip(),
        date_of_birth=payload.date_of_birth,
        gender=payload.gender.strip(),
        verification_status="pending",
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return build_token_response(user)


@router.post("/signup/doctor", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup_doctor(payload: DoctorSignupRequest, db: Session = Depends(get_db)):
    email = normalize_email(str(payload.email))
    phone = normalize_phone(payload.phone)
    ensure_unique_identity(db, email, phone)

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role="DOCTOR",
        phone=phone,
        is_email_verified=False,
        is_identity_verified=False,
    )
    db.add(user)
    db.flush()

    profile = DoctorProfile(
        user_id=user.id,
        pmdc_number=payload.pmdc_number.strip(),
        specialization=payload.specialization.strip(),
        hospital_name=payload.hospital_name.strip(),
        verification_status="pending",
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return build_token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == normalize_email(str(payload.email))).first()
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return build_token_response(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return user_to_out(current_user)
