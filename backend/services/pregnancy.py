"""Pregnancy status on the patient profile: pregnant, not pregnant or not recorded.

Set by the patient, or by a doctor with an active access grant; the date and the role are kept. A "pregnant"
status older than `settings.pregnancy_status_max_months` counts as not recorded (an app rule (demo), not a
clinical standard), and the page asks for an update, because a stale "pregnant" would withhold a BMI category
and, in later checks, change advice for a person who may no longer be pregnant. "Not pregnant" does not expire.
Nothing is guessed from text: the status is only ever what a person set.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from models import PatientProfile, User
from services import audit, clock

PREGNANT = "pregnant"
NOT_PREGNANT = "not_pregnant"
NOT_RECORDED = "not_recorded"
STATUSES = (PREGNANT, NOT_PREGNANT, NOT_RECORDED)


def add_months(day: date, months: int) -> date:
    """`day` plus whole calendar months; the day is cut back to the end of a shorter month."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class PregnancyState:
    status: str  # pregnant, not_pregnant or not_recorded (what the checks use)
    set_on: date | None  # when it was last set, even if it has expired
    set_by_role: str | None  # patient or doctor
    expired: bool  # a "pregnant" status that is too old: counted as not recorded, the page asks for an update
    max_months: int

    @property
    def pregnant(self) -> bool:
        return self.status == PREGNANT


def effective(
    stored: str | None,
    set_at: datetime | date | None,
    set_by_role: str | None,
    today: date | None = None,
    max_months: int | None = None,
) -> PregnancyState:
    """The status the checks use. Anything other than a stored "pregnant" or "not_pregnant" is not recorded."""
    today = today or clock.today()
    months = settings.pregnancy_status_max_months if max_months is None else max_months
    set_on = clock.local_date(set_at)  # a stored timestamp is UTC; the date is the patient's local one
    if stored not in (PREGNANT, NOT_PREGNANT):
        return PregnancyState(NOT_RECORDED, None, None, False, months)
    if stored == PREGNANT and (set_on is None or today > add_months(set_on, months)):
        return PregnancyState(NOT_RECORDED, set_on, set_by_role, True, months)
    return PregnancyState(stored, set_on, set_by_role, False, months)


def state_for(profile: PatientProfile | None, today: date | None = None) -> PregnancyState:
    if profile is None:
        return effective(None, None, None, today)
    return effective(
        profile.pregnancy_status, profile.pregnancy_status_set_at, profile.pregnancy_status_set_by_role, today
    )


def set_status(db: Session, patient: User, actor: User, new: str) -> PatientProfile:
    """Store the status (`not_recorded` clears it) and write the audit row (label only). Caller commits."""
    profile = patient.patient_profile
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient profile not found.")
    if new not in STATUSES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose pregnant, not pregnant or not recorded.")
    if new == PREGNANT and (profile.gender or "").strip().lower() == "male":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Pregnancy status does not apply to a patient recorded as male."
        )
    role = "patient" if actor.id == patient.id else "doctor"
    if new == NOT_RECORDED:
        profile.pregnancy_status = None
        profile.pregnancy_status_set_at = None
        profile.pregnancy_status_set_by_role = None
        profile.pregnancy_status_set_by_id = None
    else:
        profile.pregnancy_status = new
        profile.pregnancy_status_set_at = clock.now()
        profile.pregnancy_status_set_by_role = role
        profile.pregnancy_status_set_by_id = actor.id
    audit.record(
        db, actor, "pregnancy_status.set", patient_id=patient.id, target_type="patient_profile",
        target_id=profile.id, detail="pregnancy status", commit=False,
    )  # fmt: skip
    return profile
