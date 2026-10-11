"""Patient-consented doctor access to a patient's dashboard.

A patient issues a one-time 6-digit OTP (valid 15 minutes). A doctor who enters it
gets a 2-hour grant; the doctor can end it early. Ported from lib/patient-access.ts.
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import DashboardOtpAttempt, PatientDashboardAccess, PatientDashboardOtp, User

logger = logging.getLogger("nora.dashboard_access")

OTP_LIFETIME = timedelta(minutes=15)
CONSULTATION_LIFETIME = timedelta(hours=2)

# Brute-force protection: 6-digit codes, so failed redemptions are limited per account.
MAX_FAILED_ATTEMPTS = 5
ATTEMPT_WINDOW = timedelta(minutes=15)


def ensure_otp_attempts_allowed(db: Session, actor_id: int) -> None:
    """Raise 429 if the account has MAX_FAILED_ATTEMPTS failed OTP attempts in the window."""
    since = _now() - ATTEMPT_WINDOW
    failures = (
        db.query(DashboardOtpAttempt)
        .filter(
            DashboardOtpAttempt.actor_id == actor_id,
            DashboardOtpAttempt.succeeded.is_(False),
            DashboardOtpAttempt.created_at > since,
        )
        .order_by(DashboardOtpAttempt.created_at.asc())
        .all()
    )
    if len(failures) >= MAX_FAILED_ATTEMPTS:
        oldest = failures[0].created_at
        if oldest.tzinfo is None:  # SQLite returns naive datetimes (stored as UTC)
            oldest = oldest.replace(tzinfo=UTC)
        retry_after = max(60, int((oldest + ATTEMPT_WINDOW - _now()).total_seconds()))
        logger.warning(
            "Dashboard OTP attempts blocked for user %s (%s failures in 15 minutes)", actor_id, len(failures)
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many incorrect OTP attempts. Please wait {max(1, retry_after // 60)} minutes "
                "and ask the patient for a new code."
            ),
            headers={"Retry-After": str(retry_after)},
        )


def record_otp_attempt(db: Session, actor_id: int, context: str, succeeded: bool, commit: bool = True) -> None:
    """Log an OTP redemption attempt (never the code). Failures also go to the server log."""
    db.add(DashboardOtpAttempt(actor_id=actor_id, context=context, succeeded=succeeded))
    if not succeeded:
        logger.warning("Failed dashboard OTP attempt by user %s (%s)", actor_id, context)
    if commit:
        db.commit()


@dataclass
class Grant:
    patient: User
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


def create_dashboard_otp(db: Session, patient: User) -> PatientDashboardOtp:
    """Invalidate the patient's unused codes and issue a new one."""
    now = _now()
    (
        db.query(PatientDashboardOtp)
        .filter(
            PatientDashboardOtp.patient_id == patient.id,
            PatientDashboardOtp.used_at.is_(None),
            PatientDashboardOtp.expires_at > now,
        )
        .update({PatientDashboardOtp.used_at: now}, synchronize_session=False)
    )
    db.commit()

    for _ in range(5):
        otp = PatientDashboardOtp(
            patient_id=patient.id,
            code=f"{100000 + secrets.randbelow(900000)}",
            expires_at=now + OTP_LIFETIME,
        )
        db.add(otp)
        try:
            db.commit()
        except IntegrityError:  # the code is unique; retry on a collision
            db.rollback()
            continue
        db.refresh(otp)
        return otp
    raise RuntimeError("Unable to create a dashboard OTP.")


def grant_access_by_otp(
    db: Session,
    doctor_id: int,
    otp_code: str,
    expected_patient_id: int | None = None,
    commit: bool = True,
) -> Grant | None:
    """Redeem a valid, unused OTP: mark it used and start (or renew) a 2-hour grant."""
    now = _now()
    query = db.query(PatientDashboardOtp).filter(
        PatientDashboardOtp.code == otp_code.strip(),
        PatientDashboardOtp.used_at.is_(None),
        PatientDashboardOtp.expires_at > now,
    )
    if expected_patient_id is not None:
        query = query.filter(PatientDashboardOtp.patient_id == expected_patient_id)
    otp = query.first()
    if not otp:
        return None

    patient = db.get(User, otp.patient_id)
    if not patient or patient.role.lower() != "patient":
        return None

    otp.used_at = now
    expires_at = now + CONSULTATION_LIFETIME
    access = (
        db.query(PatientDashboardAccess)
        .filter(PatientDashboardAccess.doctor_id == doctor_id, PatientDashboardAccess.patient_id == patient.id)
        .first()
    )
    if access:
        access.status = "ACTIVE"
        access.expires_at = expires_at
        access.ended_at = None
    else:
        db.add(
            PatientDashboardAccess(doctor_id=doctor_id, patient_id=patient.id, status="ACTIVE", expires_at=expires_at)
        )
    if commit:
        db.commit()
    return Grant(patient=patient, expires_at=expires_at)


def active_grants(db: Session, doctor_id: int) -> list[PatientDashboardAccess]:
    """Grants that are ACTIVE, not ended and not expired."""
    now = _now()
    return (
        db.query(PatientDashboardAccess)
        .filter(
            PatientDashboardAccess.doctor_id == doctor_id,
            func.upper(PatientDashboardAccess.status) == "ACTIVE",
            PatientDashboardAccess.ended_at.is_(None),
            or_(PatientDashboardAccess.expires_at.is_(None), PatientDashboardAccess.expires_at > now),
        )
        .order_by(PatientDashboardAccess.created_at.desc())
        .all()
    )


def has_active_grant(db: Session, doctor_id: int, patient_id: int) -> bool:
    return any(grant.patient_id == patient_id for grant in active_grants(db, doctor_id))


def end_access(db: Session, doctor_id: int, patient_id: int) -> None:
    """End the signed-in doctor's own active grant for the patient (no-op otherwise)."""
    (
        db.query(PatientDashboardAccess)
        .filter(
            PatientDashboardAccess.doctor_id == doctor_id,
            PatientDashboardAccess.patient_id == patient_id,
            func.upper(PatientDashboardAccess.status) == "ACTIVE",
        )
        .update(
            {PatientDashboardAccess.status: "ENDED", PatientDashboardAccess.ended_at: _now()}, synchronize_session=False
        )
    )
    db.commit()
