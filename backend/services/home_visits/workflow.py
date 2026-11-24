"""The home-visit workflow: create, offer, accept, move through the steps, and end.

Every status change goes through states.transition() and is written with a conditional UPDATE
(`WHERE status = <what we read>`), so two things happening at once (an accept and a timeout, a double click)
cannot both win: the loser gets a 409. Each change stamps its own timestamp, writes an audit row and tells
the people involved. Nothing here reads or writes the patient's record; the summary stays on the visit.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import DoctorProfile, HomeVisitOffer, HomeVisitRequest, User
from services import audit
from services.home_visits import notify, offers, repository, states
from services.home_visits.matching import Ranked, rank
from services.home_visits.schemas import CloseIn, HomeVisitCreate

log = logging.getLogger("nora.home_visits")


class VisitError(Exception):
    """A refusal with an HTTP status and a message that is safe to show."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _name(db: Session, user_id: int | None) -> str:
    user = db.get(User, user_id) if user_id else None
    return user.full_name if user else "The doctor"


def _move(db: Session, request: HomeVisitRequest, target: str, actor: str, now: datetime, **fields) -> None:
    """Change the status (checked by the state machine), stamp its time, and refuse if it changed meanwhile."""
    try:
        states.transition(request.status, target, actor)
    except states.InvalidTransition as exc:
        raise VisitError(409, str(exc)) from None
    values = {"status": target, states.TIMESTAMP_FIELD[target]: now, **fields}
    result = db.execute(
        update(HomeVisitRequest)
        .where(HomeVisitRequest.id == request.id, HomeVisitRequest.status == request.status)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise VisitError(409, "This visit has just changed. Refresh and try again.")
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise VisitError(409, "That is no longer possible: the doctor is already on another visit.") from None
    db.refresh(request)


def _log(db: Session, actor: User | None, action: str, request: HomeVisitRequest, detail: str = "") -> None:
    kwargs = {"patient_id": request.patient_id, "target_type": "home_visit", "target_id": request.id, "detail": detail}
    if actor is None:
        audit.record_system(db, action, commit=False, **kwargs)
    else:
        audit.record(db, actor, action, commit=False, **kwargs)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise VisitError(409, "That is no longer possible: the doctor is already on another visit.") from None


# --- offers -------------------------------------------------------------------------------------------


def _tried(db: Session, request_id: int) -> set[int]:
    return {row[0] for row in db.query(HomeVisitOffer.doctor_id).filter(HomeVisitOffer.request_id == request_id)}


def _offer(db: Session, request: HomeVisitRequest, ranked: Ranked, now: datetime) -> None:
    position = len(_tried(db, request.id)) + 1
    db.add(
        HomeVisitOffer(
            request_id=request.id,
            doctor_id=ranked.doctor_id,
            position=position,
            score=ranked.score,
            distance_km=ranked.distance_km,
            expires_at=offers.expires_at(now, request.match_mode),
            offered_at=now,
        )
    )
    db.flush()
    notify.offered(db, request, ranked.doctor_id)
    _log(db, None, "home_visit.offer", request, f"offer {position} of {offers.MAX_OFFERS}")


def _next_or_end(db: Session, request: HomeVisitRequest, now: datetime, *, by_doctor_decline: bool) -> None:
    """After an offer ended without an accept: offer the next doctor, or end the request."""
    if request.match_mode == offers.CHOOSE:
        if by_doctor_decline:
            _move(db, request, states.DECLINED, states.DOCTOR, now, ended_reason="The doctor declined.")
            notify.declined(db, request)
        else:
            _move(db, request, states.EXPIRED, states.SYSTEM, now, ended_reason="No answer in time.")
            notify.expired(db, request)
            _log(db, None, "home_visit.expire", request, "chosen doctor did not answer")
        return
    ranked = rank(repository.candidates(db, now), request.latitude, request.longitude, request.specialty)
    following = offers.next_candidate(ranked, _tried(db, request.id))
    if following is not None:
        _offer(db, request, following, now)
        return
    _move(db, request, states.NO_DOCTOR_FOUND, states.SYSTEM, now, ended_reason="No doctor could take the request.")
    notify.no_doctor_found(db, request)
    _log(db, None, "home_visit.no_doctor", request, f"{len(_tried(db, request.id))} offered")


def advance(db: Session, request: HomeVisitRequest, now: datetime) -> bool:
    """Settle an offer whose window has ended (timeout): next doctor, or the end. True if anything changed."""
    if request.status != states.OFFERED:
        return False
    pending = (
        db.query(HomeVisitOffer)
        .filter(HomeVisitOffer.request_id == request.id, HomeVisitOffer.outcome == "pending")
        .first()
    )
    if pending is not None and not offers.is_expired(pending.expires_at, now):
        return False
    if pending is not None:
        closed = db.execute(
            update(HomeVisitOffer)
            .where(HomeVisitOffer.id == pending.id, HomeVisitOffer.outcome == "pending")
            .values(outcome="expired", responded_at=now)
        )
        if closed.rowcount != 1:  # answered a moment ago
            db.rollback()
            return False
        notify.withdrawn(db, request, pending.doctor_id, "The time to answer a home visit request ran out.")
    _next_or_end(db, request, now, by_doctor_decline=False)
    db.commit()
    return True


def advance_due(db: Session, now: datetime) -> int:
    """The worker's job: settle every request whose offer window has ended."""
    due = (
        db.query(HomeVisitRequest)
        .join(HomeVisitOffer, HomeVisitOffer.request_id == HomeVisitRequest.id)
        .filter(
            HomeVisitRequest.status == states.OFFERED,
            HomeVisitOffer.outcome == "pending",
            HomeVisitOffer.expires_at <= now,
        )
        .all()
    )
    settled = 0
    for request in due:
        try:
            settled += advance(db, request, now)
        except VisitError:
            db.rollback()
        except Exception:
            db.rollback()
            log.exception("A home visit offer could not be settled; it will be tried again")
    return settled


# --- patient -------------------------------------------------------------------------------------------


def create(
    db: Session, patient: User, payload: HomeVisitCreate, specialty: str, ranked: list[Ranked], now: datetime
) -> HomeVisitRequest:
    """Save the request (the emergency gate already passed) and offer it. `ranked` is the eligible doctors."""
    if repository.has_live_request(db, patient.id):
        raise VisitError(409, "You already have a home visit in progress. Cancel it before sending another.")
    location = payload.location
    request = HomeVisitRequest(
        patient_id=patient.id,
        status=states.OFFERED,
        match_mode=payload.mode,
        reason=payload.reason,
        specialty=specialty,
        contact_phone=payload.phone.strip(),
        address_text=payload.address_text,
        latitude=location.latitude,
        longitude=location.longitude,
        accuracy_m=location.accuracy_m,
        location_source=location.source,
        created_at=now,
    )
    db.add(request)
    db.flush()
    _log(db, patient, "home_visit.request", request, f"mode {payload.mode}")
    if payload.mode == offers.CHOOSE:
        chosen = next((r for r in ranked if r.doctor_id == payload.doctor_id), None)
        if chosen is None:
            db.rollback()
            raise VisitError(422, "That doctor cannot take this request. Choose a doctor from the list.")
        _offer(db, request, chosen, now)
    elif ranked:
        _offer(db, request, ranked[0], now)
    else:
        _move(db, request, states.NO_DOCTOR_FOUND, states.SYSTEM, now, ended_reason="No doctor could take the request.")
        notify.no_doctor_found(db, request)
        _log(db, None, "home_visit.no_doctor", request, "0 eligible")
    _commit(db)
    db.refresh(request)
    return request


def cancel_by_patient(db: Session, patient: User, request: HomeVisitRequest, now: datetime) -> HomeVisitRequest:
    if request.patient_id != patient.id:
        raise VisitError(404, "Visit not found.")
    doctor_id = request.doctor_id
    pending = db.query(HomeVisitOffer).filter(
        HomeVisitOffer.request_id == request.id, HomeVisitOffer.outcome == "pending"
    )
    waiting = pending.first()
    _move(db, request, states.CANCELLED, states.PATIENT, now, ended_reason="Cancelled by the patient.")
    if waiting is not None:
        pending.update({"outcome": "withdrawn", "responded_at": now}, synchronize_session=False)
        notify.withdrawn(db, request, waiting.doctor_id, "The patient cancelled the request.")
    if doctor_id:
        notify.cancelled_by_patient(db, request)
    _log(db, patient, "home_visit.cancel", request)
    _commit(db)
    return request


# --- doctor --------------------------------------------------------------------------------------------


def _pending_offer(db: Session, request_id: int, doctor_id: int) -> HomeVisitOffer | None:
    return (
        db.query(HomeVisitOffer)
        .filter(
            HomeVisitOffer.request_id == request_id,
            HomeVisitOffer.doctor_id == doctor_id,
            HomeVisitOffer.outcome == "pending",
        )
        .first()
    )


def accept(db: Session, doctor: User, request: HomeVisitRequest, now: datetime) -> HomeVisitRequest:
    """First accept wins: the offer must still be pending and inside its window, decided by one UPDATE."""
    advance(db, request, now)
    db.refresh(request)
    offer = _pending_offer(db, request.id, doctor.id) if request.status == states.OFFERED else None
    if offer is None:
        raise VisitError(409, "This request is no longer waiting for you.")
    won = db.execute(
        update(HomeVisitOffer)
        .where(HomeVisitOffer.id == offer.id, HomeVisitOffer.outcome == "pending", HomeVisitOffer.expires_at > now)
        .values(outcome="accepted", responded_at=now)
    )
    if won.rowcount != 1:
        db.rollback()
        raise VisitError(409, "This request is no longer waiting for you.")
    _move(db, request, states.ACCEPTED, states.DOCTOR, now, doctor_id=doctor.id)
    notify.accepted(db, request, doctor.full_name)
    _log(db, doctor, "home_visit.accept", request)
    _commit(db)
    return request


def decline(db: Session, doctor: User, request: HomeVisitRequest, now: datetime) -> HomeVisitRequest:
    advance(db, request, now)
    db.refresh(request)
    offer = _pending_offer(db, request.id, doctor.id) if request.status == states.OFFERED else None
    if offer is None:
        raise VisitError(409, "This request is no longer waiting for you.")
    closed = db.execute(
        update(HomeVisitOffer)
        .where(HomeVisitOffer.id == offer.id, HomeVisitOffer.outcome == "pending")
        .values(outcome="declined", responded_at=now)
    )
    if closed.rowcount != 1:
        db.rollback()
        raise VisitError(409, "This request is no longer waiting for you.")
    _log(db, doctor, "home_visit.decline", request)
    _next_or_end(db, request, now, by_doctor_decline=True)
    _commit(db)
    return request


def _own_visit(request: HomeVisitRequest, doctor: User) -> None:
    if request.doctor_id != doctor.id:
        raise VisitError(404, "Visit not found.")


def en_route(db: Session, doctor: User, request: HomeVisitRequest, eta: int | None, now: datetime) -> HomeVisitRequest:
    _own_visit(request, doctor)
    _move(db, request, states.EN_ROUTE, states.DOCTOR, now, eta_minutes=eta)
    notify.en_route(db, request, doctor.full_name, eta)
    _log(db, doctor, "home_visit.en_route", request, "estimate typed by the doctor" if eta else "")
    _commit(db)
    return request


def arrived(db: Session, doctor: User, request: HomeVisitRequest, now: datetime) -> HomeVisitRequest:
    _own_visit(request, doctor)
    _move(db, request, states.ARRIVED, states.DOCTOR, now)
    notify.arrived(db, request, doctor.full_name)
    _log(db, doctor, "home_visit.arrive", request)
    _commit(db)
    return request


def complete(db: Session, doctor: User, request: HomeVisitRequest, now: datetime) -> HomeVisitRequest:
    _own_visit(request, doctor)
    _move(db, request, states.COMPLETED, states.DOCTOR, now)
    notify.completed(db, request, doctor.full_name)
    _log(db, doctor, "home_visit.complete", request)
    _commit(db)
    return request


def close(db: Session, doctor: User, request: HomeVisitRequest, summary: CloseIn, now: datetime) -> HomeVisitRequest:
    """Close the visit with the summary (findings, advice, follow-up), saved on the patient's visit record."""
    _own_visit(request, doctor)
    _move(
        db, request, states.CLOSED, states.DOCTOR, now,
        visit_findings=summary.findings.strip(), visit_advice=summary.advice.strip(), visit_follow_up=summary.follow_up.strip(),
    )  # fmt: skip
    notify.closed(db, request, doctor.full_name)
    _log(db, doctor, "home_visit.close", request)
    _commit(db)
    return request


def cancel_by_doctor(db: Session, doctor: User, request: HomeVisitRequest, now: datetime) -> HomeVisitRequest:
    _own_visit(request, doctor)
    _move(db, request, states.CANCELLED, states.DOCTOR, now, ended_reason="Cancelled by the doctor.")
    notify.cancelled_by_doctor(db, request, doctor.full_name)
    _log(db, doctor, "home_visit.cancel", request)
    _commit(db)
    return request


def escalate(db: Session, doctor: User, request: HomeVisitRequest, now: datetime) -> HomeVisitRequest:
    """The doctor judges it is an emergency: the patient is told to call 1122, and this ends the request."""
    waiting = _pending_offer(db, request.id, doctor.id)
    if request.doctor_id != doctor.id and waiting is None:
        raise VisitError(404, "Visit not found.")
    _move(db, request, states.REFERRED_EMERGENCY, states.DOCTOR, now, ended_reason="Referred to emergency care.")
    db.query(HomeVisitOffer).filter(
        HomeVisitOffer.request_id == request.id, HomeVisitOffer.outcome == "pending"
    ).update({"outcome": "withdrawn", "responded_at": now}, synchronize_session=False)
    notify.referred_emergency(db, request)
    _log(db, doctor, "home_visit.escalate", request)
    _commit(db)
    return request


# --- doctor settings -----------------------------------------------------------------------------------


def save_settings(
    db: Session, profile: DoctorProfile, enabled: bool, radius: float | None, lat: float | None, lon: float | None
) -> DoctorProfile:
    """Home visits can be on only with a base location and a service radius."""
    if enabled and (radius is None or lat is None or lon is None):
        raise VisitError(422, "Set your base location and service radius before switching home visits on.")
    profile.home_visits_enabled = enabled
    profile.service_radius_km = radius
    profile.base_latitude = lat
    profile.base_longitude = lon
    db.commit()
    return profile
