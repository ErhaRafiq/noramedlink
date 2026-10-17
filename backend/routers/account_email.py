"""Email-backed account flows: forgot password (6-digit code), reset, email verification and its resend.

- Forgot password answers the same thing whether or not the address has an account, so it cannot be used to find
  out who is registered. It is limited per IP and per address, and the database limits how often one account
  gets a code (60 seconds apart, 3 an hour). The email is sent after the answer, so response time tells nothing.
- A reset needs the emailed code (10 minutes, 5 wrong tries, single use). A reset signs the account out
  everywhere (every refresh token is revoked), marks the address verified (the person just proved they read it)
  and sends a "your password was changed" notice.
- The verification link calls a POST from the page, so a mail scanner opening the link cannot use it up.
Codes and tokens are never logged or stored in the clear (services/auth_tokens.py).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from auth import hash_password
from database import get_db
from dependencies import get_current_user
from models import User
from rate_limit import EMAIL_LIMIT, enforce_account_limit, ip_key, limiter
from schemas import ForgotPasswordIn, MessageOut, ResetPasswordIn, VerifyEmailIn
from services import auth_tokens, notifications, sessions
from services.account_email import send_account_email, verification_link
from services.signup_service import normalize_email

router = APIRouter(prefix="/auth", tags=["auth"])

FORGOT_MESSAGE = "If that email has an account, we sent a 6-digit code to it. It works for 10 minutes."
BAD_CODE = "That code is not right, or it has expired. Check the latest email or ask for a new code."


def _too_many(error: auth_tokens.TooSoon | auth_tokens.TooMany) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"An email was sent a moment ago. Please wait {error.retry_after} seconds before asking again.",
        headers={"Retry-After": str(error.retry_after)},
    )


@router.post("/forgot-password", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(EMAIL_LIMIT, key_func=ip_key)
def forgot_password(
    request: Request, payload: ForgotPasswordIn, background: BackgroundTasks, db: Session = Depends(get_db)
):
    email = normalize_email(str(payload.email))
    enforce_account_limit("forgot", email, "5/hour")  # counted for every address, so it reveals nothing
    user = db.query(User).filter(User.email == email).first()
    if user is not None and user.is_active:
        try:
            code = auth_tokens.issue(db, user, auth_tokens.RESET_PASSWORD)
            db.commit()
            background.add_task(
                send_account_email, user.id, "reset_code", {"code": code, "minutes": auth_tokens.RESET_MINUTES}
            )
        except (auth_tokens.TooSoon, auth_tokens.TooMany):
            db.rollback()  # the same answer as success: asking again changes nothing and tells nothing
    return {"message": FORGOT_MESSAGE}


@router.post("/reset-password", response_model=MessageOut)
@limiter.limit("10/minute", key_func=ip_key)
def reset_password(
    request: Request, payload: ResetPasswordIn, background: BackgroundTasks, db: Session = Depends(get_db)
):
    email = normalize_email(str(payload.email))
    enforce_account_limit("reset", email, "15/hour")
    user = db.query(User).filter(User.email == email).first()
    if (
        user is None
        or not user.is_active
        or not auth_tokens.verify_code(db, user, auth_tokens.RESET_PASSWORD, payload.code)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=BAD_CODE)
    user.hashed_password = hash_password(payload.new_password)
    user.is_email_verified = True  # the code reached this inbox
    sessions.revoke_all(db, user)
    notifications.password_changed(db, user.id)
    db.commit()
    background.add_task(send_account_email, user.id, "password_changed", {})
    return {"message": "Your password was changed. Sign in with your new password."}


@router.post("/verify-email", response_model=MessageOut)
@limiter.limit("20/minute", key_func=ip_key)
def verify_email(request: Request, payload: VerifyEmailIn, db: Session = Depends(get_db)):
    user = auth_tokens.consume_link(db, auth_tokens.VERIFY_EMAIL, payload.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This link has already been used or has expired. Sign in and ask for a new one.",
        )
    if not user.is_email_verified:
        user.is_email_verified = True
        db.commit()
    return {"message": "Your email address is confirmed."}


@router.post("/resend-verification", response_model=MessageOut)
@limiter.limit(EMAIL_LIMIT)
def resend_verification(
    request: Request,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_email_verified:
        return {"message": "Your email address is already confirmed."}
    try:
        token = auth_tokens.issue(db, current_user, auth_tokens.VERIFY_EMAIL)
        db.commit()
    except (auth_tokens.TooSoon, auth_tokens.TooMany) as error:
        db.rollback()
        raise _too_many(error) from error
    background.add_task(send_account_email, current_user.id, "verify_email", {"link": verification_link(token)})
    return {"message": "We sent a new confirmation link. It works for 24 hours."}
