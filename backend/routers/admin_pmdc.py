"""Admin: doctors with their PMDC verification status, the check against the PMDC register, and a decision by hand.

An administrator triggers every check (approval also tries one, best effort). A check never blocks approval:
a doctor can be active without being PMDC verified, and a verified one gets a badge. The rules live in
services/pmdc.py; the register is asked only for the registration number.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_admin
from models import DoctorProfile, User
from pagination import Page, PageParams, page_params, paginate
from rate_limit import PMDC_LIMIT, limiter
from schemas import AdminDoctorOut, PmdcManualIn, PmdcStatusOut
from services import audit, notifications, pmdc

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _profile(db: Session, profile_id: int) -> DoctorProfile:
    profile = db.get(DoctorProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")
    return profile


def _names(db: Session, profiles: list[DoctorProfile]) -> dict[int, str]:
    ids = {p.pmdc_checked_by_id for p in profiles if p.pmdc_checked_by_id}
    return {u.id: u.full_name for u in db.query(User).filter(User.id.in_(ids))} if ids else {}


def doctor_out(profile: DoctorProfile, names: dict[int, str]) -> AdminDoctorOut:
    user = profile.user
    return AdminDoctorOut(
        id=profile.id,
        user_id=profile.user_id,
        full_name=user.full_name if user else "",
        email=user.email if user else "",
        phone=user.phone if user else "",
        specialization=profile.specialization,
        hospital_name=profile.hospital_name,
        verification_status=profile.verification_status.lower(),
        created_at=profile.created_at,
        pmdc=pmdc.status_out(profile, names),
    )


@router.get("/doctors", response_model=Page[AdminDoctorOut])
def list_doctors(
    approval: Literal["pending", "approved", "rejected"] | None = None,
    pmdc_status: Literal["verified", "unverified"] | None = Query(default=None, alias="pmdc"),
    q: str | None = Query(default=None, max_length=80, description="Part of the name or the registration number."),
    params: PageParams = Depends(page_params),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Every doctor, newest first, with the approval status and where the PMDC check stands."""
    query = db.query(DoctorProfile).join(User, User.id == DoctorProfile.user_id)
    if approval:
        query = query.filter(func.lower(DoctorProfile.verification_status) == approval)
    if pmdc_status:
        query = query.filter(DoctorProfile.pmdc_verified.is_(pmdc_status == "verified"))
    if q and q.strip():
        text = q.strip().lower()
        query = query.filter(
            func.lower(User.full_name).contains(text, autoescape=True)
            | func.lower(DoctorProfile.pmdc_number).contains(text, autoescape=True)
        )
    page = paginate(query.order_by(DoctorProfile.created_at.desc(), DoctorProfile.id.desc()), params, lambda p: p)
    names = _names(db, page["items"])
    return {**page, "items": [doctor_out(p, names) for p in page["items"]]}


@router.post("/doctors/{doctor_id}/pmdc-check", response_model=PmdcStatusOut)
@limiter.limit(PMDC_LIMIT)
def check_pmdc(
    request: Request,
    doctor_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Ask the PMDC public register about this doctor's number and record the answer."""
    profile = _profile(db, doctor_id)
    try:
        pmdc.run_check(db, profile, admin)
    except pmdc.PmdcDisabled as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The PMDC lookup is switched off on this server. Check the number on pmdc.pk and use "
            "'Decide by hand' instead.",
        ) from error
    except pmdc.PmdcUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The PMDC register could not be reached, so nothing was changed. Try again later, or check "
            "pmdc.pk yourself and use 'Decide by hand'.",
        ) from error
    return pmdc.status_out(profile, _names(db, [profile]))


@router.put("/doctors/{doctor_id}/pmdc-verified", response_model=PmdcStatusOut)
def decide_pmdc_by_hand(
    doctor_id: int,
    payload: PmdcManualIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """The administrator's own decision (for example after looking the doctor up on pmdc.pk), with the reason."""
    profile = _profile(db, doctor_id)
    was_verified = profile.pmdc_verified
    pmdc.set_by_hand(profile, payload.verified, payload.note, admin.id)
    if profile.pmdc_verified != was_verified:
        notifications.doctor_pmdc_changed(db, profile.user_id, profile.pmdc_verified)
    audit.record(
        db, admin, "admin.pmdc_manual", target_type="doctor_profile", target_id=profile.id,
        detail="verified" if payload.verified else "not verified", commit=False,
    )  # fmt: skip
    db.commit()
    db.refresh(profile)
    return pmdc.status_out(profile, _names(db, [profile]))
