"""Signup, login and the current user (/auth and /api/auth). Helpers live in services/signup_service.py."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import verify_password
from database import get_db
from dependencies import get_current_user
from models import User
from rate_limit import LOGIN_LIMIT, SIGNUP_LIMIT, enforce_account_limit, ip_key, limiter
from schemas import LoginRequest, MessageOut, RefreshRequest, SignupRequest, TokenResponse, UserOut
from services import sessions
from services.signup_service import (
    build_token_response,
    create_user,
    doctor_pmdc,
    ensure_unique_identity,
    normalize_email,
    normalize_signup_payload,
    user_to_out,
    validate_role_specific_fields,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(SIGNUP_LIMIT, key_func=ip_key)
def signup(request: Request, payload: SignupRequest, db: Session = Depends(get_db)):
    email, phone = normalize_signup_payload(payload)
    validate_role_specific_fields(payload)
    ensure_unique_identity(db, email, phone, doctor_pmdc(payload))

    try:
        user = create_user(payload, email, phone, db)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc

    return build_token_response(db, user)


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
    return build_token_response(db, user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return user_to_out(current_user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(LOGIN_LIMIT, key_func=ip_key)
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """A new access token and refresh token for a valid refresh token (which is then used up)."""
    try:
        user, access, refresh_token = sessions.refresh_session(db, payload.refresh_token)
    except sessions.SessionError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in again.") from None
    return TokenResponse(access_token=access, refresh_token=refresh_token, user=user_to_out(user))


@router.post("/logout", response_model=MessageOut)
@limiter.limit(LOGIN_LIMIT, key_func=ip_key)
def logout(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """End this sign-in session everywhere (its refresh token's whole family)."""
    sessions.end_session(db, payload.refresh_token)
    return {"message": "Signed out."}
