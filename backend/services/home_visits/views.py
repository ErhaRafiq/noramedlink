"""What each person is allowed to see of a home visit. Loaded in batches (a fixed number of queries per page).

- The patient sees their own request: the doctor only once chosen or matched, never any coordinates.
- A doctor with a pending offer sees the reason and a rounded straight-line distance: no name, phone or address.
- The matched doctor sees the patient's name, phone, written address and place, from the moment they accept.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import DoctorProfile, HomeVisitOffer, HomeVisitRequest, User
from services.home_visits import states
from services.home_visits.geo import accuracy_label, distance_label
from services.home_visits.schemas import (
    DoctorOffer,
    DoctorPublic,
    DoctorVisit,
    Eta,
    PatientContact,
    PatientVisit,
    Summary,
)
from services.symptom_checker import EMERGENCY_NOTICE


def _summary(request: HomeVisitRequest) -> Summary | None:
    if request.visit_findings is None:
        return None
    return Summary(
        findings=request.visit_findings, advice=request.visit_advice or "", follow_up=request.visit_follow_up or ""
    )


def _eta(request: HomeVisitRequest) -> Eta | None:
    return Eta(minutes=request.eta_minutes) if request.eta_minutes else None


def _doctors(db: Session, ids: set[int]) -> dict[int, DoctorPublic]:
    if not ids:
        return {}
    rows = (
        db.query(User.id, User.full_name, DoctorProfile.specialization, DoctorProfile.hospital_name)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .filter(User.id.in_(ids))
    )
    return {i: DoctorPublic(id=i, name=n, specialty=s, hospital=h) for i, n, s, h in rows}


def patient_views(db: Session, requests: list[HomeVisitRequest]) -> list[PatientVisit]:
    ids = [r.id for r in requests]
    counts: dict[int, int] = {}
    pending: dict[int, HomeVisitOffer] = {}
    if ids:
        counts = dict(
            db.query(HomeVisitOffer.request_id, func.count(HomeVisitOffer.id))
            .filter(HomeVisitOffer.request_id.in_(ids))
            .group_by(HomeVisitOffer.request_id)
            .all()
        )
        for offer in db.query(HomeVisitOffer).filter(
            HomeVisitOffer.request_id.in_(ids), HomeVisitOffer.outcome == "pending"
        ):
            pending[offer.request_id] = offer
    wanted = {r.doctor_id for r in requests if r.doctor_id}
    wanted |= {pending[r.id].doctor_id for r in requests if r.match_mode == "choose" and r.id in pending}
    doctors = _doctors(db, wanted)
    views = []
    for r in requests:
        offer = pending.get(r.id)
        doctor_id = r.doctor_id or (offer.doctor_id if offer and r.match_mode == "choose" else None)
        views.append(
            PatientVisit(
                id=r.id,
                status=r.status,
                status_label=states.LABELS[r.status],
                mode=r.match_mode,
                reason=r.reason,
                specialty=r.specialty,
                address_text=r.address_text,
                location=accuracy_label(r.accuracy_m),
                doctor=doctors.get(doctor_id) if doctor_id else None,
                offered_to_count=counts.get(r.id, 0),
                offer_expires_at=offer.expires_at if offer else None,
                eta=_eta(r),
                summary=_summary(r),
                emergency_notice=EMERGENCY_NOTICE if r.status == states.REFERRED_EMERGENCY else None,
                created_at=r.created_at,
                accepted_at=r.accepted_at,
                en_route_at=r.en_route_at,
                arrived_at=r.arrived_at,
                completed_at=r.completed_at,
                closed_at=r.closed_at,
                ended_at=r.ended_at,
            )
        )
    return views


def doctor_offers(db: Session, doctor_id: int) -> list[DoctorOffer]:
    rows = (
        db.query(HomeVisitOffer, HomeVisitRequest)
        .join(HomeVisitRequest, HomeVisitRequest.id == HomeVisitOffer.request_id)
        .filter(
            HomeVisitOffer.doctor_id == doctor_id,
            HomeVisitOffer.outcome == "pending",
            HomeVisitRequest.status == states.OFFERED,
        )
        .order_by(HomeVisitOffer.expires_at)
        .all()
    )
    return [
        DoctorOffer(
            id=request.id,
            reason=request.reason,
            specialty=request.specialty,
            distance=distance_label(offer.distance_km),
            expires_at=offer.expires_at,
            created_at=request.created_at,
        )
        for offer, request in rows
    ]


def _contact(request: HomeVisitRequest, name: str, doctor_id: int) -> PatientContact:
    """Phone, address and place only to the matched doctor and only while the visit is live: an ended visit, or one
    that went back to matching, keeps just the patient's name."""
    if request.status in states.TERMINAL or request.doctor_id != doctor_id:
        return PatientContact(name=name, phone=None, address_text=None, latitude=None, longitude=None, location=None)
    return PatientContact(
        name=name,
        phone=request.contact_phone,
        address_text=request.address_text,
        latitude=request.latitude,
        longitude=request.longitude,
        location=accuracy_label(request.accuracy_m),
    )


def doctor_visits(db: Session, requests: list[HomeVisitRequest], doctor_id: int) -> list[DoctorVisit]:
    ids = [r.id for r in requests]
    patients = {u.id: u for u in db.query(User).filter(User.id.in_({r.patient_id for r in requests}))} if ids else {}
    distances = (
        dict(
            db.query(HomeVisitOffer.request_id, HomeVisitOffer.distance_km).filter(
                HomeVisitOffer.request_id.in_(ids), HomeVisitOffer.doctor_id == doctor_id
            )
        )
        if ids
        else {}
    )
    return [
        DoctorVisit(
            id=r.id,
            status=r.status,
            status_label=states.LABELS[r.status],
            reason=r.reason,
            specialty=r.specialty,
            patient=_contact(r, patients[r.patient_id].full_name, doctor_id),
            distance=distance_label(distances.get(r.id, 0.0)),
            eta=_eta(r),
            summary=_summary(r),
            created_at=r.created_at,
            accepted_at=r.accepted_at,
            en_route_at=r.en_route_at,
            arrived_at=r.arrived_at,
            completed_at=r.completed_at,
            closed_at=r.closed_at,
            ended_at=r.ended_at,
        )
        for r in requests
    ]
