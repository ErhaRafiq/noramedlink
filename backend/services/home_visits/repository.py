"""Database reads for home visits: who can be offered a request right now."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import DoctorProfile, HomeVisitOffer, HomeVisitRequest, User
from services import scheduling
from services.home_visits import states
from services.home_visits.availability import availability_state
from services.home_visits.matching import Candidate

APPROVED = "approved"
ACTIVE_VISIT_STATES = (states.ACCEPTED, states.EN_ROUTE, states.ARRIVED)


def doctor_rows(db: Session, ids: list[int] | None = None):
    """(User, DoctorProfile) of approved, active doctors who switched home visits on."""
    query = (
        db.query(User, DoctorProfile)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .filter(
            func.upper(User.role) == "DOCTOR",
            User.is_active.is_(True),
            func.lower(DoctorProfile.verification_status) == APPROVED,
            DoctorProfile.home_visits_enabled.is_(True),
        )
    )
    if ids is not None:
        query = query.filter(User.id.in_(ids))
    return query.all()


def busy_doctor_ids(db: Session) -> set[int]:
    """Doctors on a visit, or holding an offer they have not answered."""
    on_visit = db.query(HomeVisitRequest.doctor_id).filter(HomeVisitRequest.status.in_(ACTIVE_VISIT_STATES))
    waiting = db.query(HomeVisitOffer.doctor_id).filter(HomeVisitOffer.outcome == "pending")
    return {row[0] for row in on_visit.union(waiting).all() if row[0] is not None}


def candidates(db: Session, now: datetime) -> list[Candidate]:
    rows = doctor_rows(db)
    if not rows:
        return []
    ids = [user.id for user, _ in rows]
    windows = scheduling.windows_of(db, ids)
    busy = busy_doctor_ids(db)
    return [
        Candidate(
            doctor_id=user.id,
            listed_specialty=profile.specialization,
            latitude=profile.base_latitude,
            longitude=profile.base_longitude,
            radius_km=profile.service_radius_km,
            availability=availability_state([(w.weekday, w.start_time, w.end_time) for w in windows[user.id]], now),
            busy=user.id in busy,
        )
        for user, profile in rows
    ]


def has_live_request(db: Session, patient_id: int) -> bool:
    return (
        db.query(HomeVisitRequest.id)
        .filter(HomeVisitRequest.patient_id == patient_id, HomeVisitRequest.status.in_(tuple(states.ACTIVE)))
        .first()
        is not None
    )
