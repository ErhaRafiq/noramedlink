"""Signup, login and the current user (/auth and /api/auth).

Helpers live in services/signup_service.py. /request-otp and /verify-otp-signup are the
OTP signup flow. The Next.js routes /api/auth/request-otp and /api/auth/verify-otp-signup
answer 410, but these endpoints stay reachable through the /api/backend proxy.
"""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import hash_password, verify_password
from database import get_db
from dependencies import get_current_user
from models import DoctorProfile, PatientProfile, SignupOtp, User
from rate_limit import LOGIN_LIMIT, SIGNUP_LIMIT, enforce_account_limit, ip_key, limiter
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
from services.signup_service import (
    OTP_EXPIRY_MINUTES,
    OTP_MAX_VERIFY_ATTEMPTS,
    as_utc,
    build_token_response,
    create_user_from_verified_signup,
    enforce_otp_rate_limit,
    ensure_unique_identity,
    normalize_email,
    normalize_phone,
    normalize_signup_payload,
    signup_payload_json,
    user_to_out,
    utc_now,
    validate_role_specific_fields,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(SIGNUP_LIMIT, key_func=ip_key)
def signup(request: Request, payload: SignupOtpRequest, db: Session = Depends(get_db)):
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
@limiter.limit(SIGNUP_LIMIT, key_func=ip_key)
def request_signup_otp(request: Request, payload: SignupOtpRequest, db: Session = Depends(get_db)):
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

    return {
        "message": "OTP sent successfully. Please check your email.",
        "expires_in_seconds": OTP_EXPIRY_MINUTES * 60,
    }


@router.post("/verify-otp-signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(SIGNUP_LIMIT, key_func=ip_key)
def verify_otp_signup(request: Request, payload: VerifySignupOtpRequest, db: Session = Depends(get_db)):
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
@limiter.limit(SIGNUP_LIMIT, key_func=ip_key)
def signup_patient(request: Request, payload: PatientSignupRequest, db: Session = Depends(get_db)):
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
@limiter.limit(SIGNUP_LIMIT, key_func=ip_key)
def signup_doctor(request: Request, payload: DoctorSignupRequest, db: Session = Depends(get_db)):
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
@limiter.limit(LOGIN_LIMIT, key_func=ip_key)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    email = normalize_email(str(payload.email))
    # Per-account limit on top of the per-IP one: slows password guessing for one account.
    enforce_account_limit("login", email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return build_token_response(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return user_to_out(current_user)
