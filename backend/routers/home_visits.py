"""On-demand home visits (Module 6): the patient's request, the doctor's answer and the steps of the visit.

Thin on purpose: this file checks who may do what and turns refusals into HTTP errors; the rules are in
services/home_visits (gate, matching, offers, state machine, workflow). Not for emergencies: a red flag or a
"yes" on the checklist saves nothing and shows only the 1122 notice. Browser location only (no maps service);
coordinates are shown to nobody but the patient's own device, the matched doctor and, audited, an admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_admin, require_doctor, require_patient
from models import DoctorProfile, EmergencyBooking, HomeVisitRequest, User
from pagination import Page, PageParams, page_params, paginate
from rate_limit import HOME_VISIT_LIMIT, limiter
from services import audit, clock
from services.home_visits import gate, geo, repository, states, views, workflow
from services.home_visits.geo import InvalidLocation
from services.home_visits.matching import rank
from services.home_visits.schemas import (
    AdminVisit,
    Checklist,
    CloseIn,
    DoctorChoice,
    DoctorOffer,
    DoctorVisit,
    EnRouteIn,
    HomeVisitCreate,
    LegacyRequest,
    Outcome,
    PatientVisit,
    RequestCheck,
    SettingsIn,
    SettingsOut,
    VisitRef,
)
from services.symptom_checker import EMERGENCY_NOTICE

router = APIRouter(prefix="/home-visits", tags=["home-visits"])

LOCATION_NOTE = (
    "Browser location needs HTTPS or localhost, and on a computer it can be approximate. "
    "Only straight-line distance is used: never a road distance or a travel time."
)


def _refuse(error: workflow.VisitError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


def _valid_place(location) -> None:
    try:
        geo.validate_coordinates(location.latitude, location.longitude)
        geo.validate_accuracy(location.accuracy_m)
    except InvalidLocation as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None


def _gate(payload: RequestCheck) -> tuple[gate.GateResult, Outcome | None]:
    """Emergency, incomplete and not-suitable answers; nothing is saved for any of them."""
    _valid_place(payload.location)
    result = gate.assess(payload.reason, payload.checklist)
    if result.status == gate.EMERGENCY:
        return result, Outcome(outcome="emergency", message=EMERGENCY_NOTICE, red_flags=result.red_flags)
    if result.status == gate.INCOMPLETE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.message)
    if result.status == gate.NOT_SUITABLE:
        return result, Outcome(outcome="not_suitable", message=result.message, specialty=result.specialty)
    return result, None


def _visit_or_404(db: Session, visit_id: int) -> HomeVisitRequest:
    visit = db.get(HomeVisitRequest, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found.")
    return visit


def _own_as_patient(db: Session, user: User, visit_id: int) -> HomeVisitRequest:
    visit = _visit_or_404(db, visit_id)
    if visit.patient_id != user.id:
        raise HTTPException(status_code=404, detail="Visit not found.")
    return visit


def _settle(db: Session, visit: HomeVisitRequest) -> HomeVisitRequest:
    """An offer whose window ended is settled the moment anyone looks (the worker does it too)."""
    if visit.status == states.OFFERED and workflow.advance(db, visit, clock.now()):
        db.refresh(visit)
    return visit


# --- shared ---------------------------------------------------------------------------------------------


@router.get("/checklist", response_model=Checklist)
def checklist(_: User = Depends(require_patient)):
    return {"notice": EMERGENCY_NOTICE, "questions": gate.checklist()}


# --- patient --------------------------------------------------------------------------------------------


@router.post("/doctors/search", response_model=Outcome)
@limiter.limit(HOME_VISIT_LIMIT)
def search_doctors(
    request: Request,
    payload: RequestCheck,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Doctors who could take this request, best match first. Runs the emergency gate first; saves nothing."""
    result, stop = _gate(payload)
    if stop:
        return stop
    now = clock.now()
    candidates = repository.candidates(db, now)
    ranked = rank(candidates, payload.location.latitude, payload.location.longitude, result.specialty or "")
    people = views._doctors(db, {r.doctor_id for r in ranked})
    availability = {c.doctor_id: c.availability for c in candidates}
    choices = [
        DoctorChoice(
            doctor_id=r.doctor_id,
            name=people[r.doctor_id].name,
            specialty=people[r.doctor_id].specialty,
            hospital=people[r.doctor_id].hospital,
            distance=geo.distance_label(r.distance_km),
            availability=availability[r.doctor_id],
        )
        for r in ranked
        if r.doctor_id in people
    ]
    return Outcome(outcome="doctors", doctors=choices, specialty=result.specialty)


@router.post("/requests", response_model=Outcome, status_code=status.HTTP_201_CREATED)
@limiter.limit(HOME_VISIT_LIMIT)
def create_request(
    request: Request,
    response: Response,
    payload: HomeVisitCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    result, stop = _gate(payload)
    if stop:
        response.status_code = status.HTTP_200_OK  # nothing was created
        return stop
    if payload.mode == "choose" and payload.doctor_id is None:
        raise HTTPException(status_code=422, detail="Choose a doctor, or use automatic matching.")
    now = clock.now()
    ranked = rank(
        repository.candidates(db, now), payload.location.latitude, payload.location.longitude, result.specialty or ""
    )
    try:
        visit = workflow.create(db, current_user, payload, result.specialty or "", ranked, now)
    except workflow.VisitError as exc:
        raise _refuse(exc) from None
    return Outcome(outcome="created", visit=views.patient_views(db, [visit])[0], specialty=result.specialty)


@router.get("", response_model=Page[PatientVisit])
def my_visits(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    for live in (
        db.query(HomeVisitRequest)
        .filter(HomeVisitRequest.patient_id == current_user.id, HomeVisitRequest.status == states.OFFERED)
        .all()
    ):
        _settle(db, live)
    query = db.query(HomeVisitRequest).filter(HomeVisitRequest.patient_id == current_user.id)
    page = paginate(query.order_by(HomeVisitRequest.created_at.desc(), HomeVisitRequest.id.desc()), params, lambda r: r)
    return {**page, "items": views.patient_views(db, page["items"])}


@router.get("/legacy", response_model=list[LegacyRequest])
def legacy_requests(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """The patient's own requests from before the home-visit service. Read-only; nothing was copied from them."""
    rows = (
        db.query(EmergencyBooking)
        .filter(EmergencyBooking.user_id == current_user.id)
        .order_by(EmergencyBooking.created_at.desc(), EmergencyBooking.id.desc())
        .limit(50)
        .all()
    )
    return [LegacyRequest(id=r.id, created_at=r.created_at, symptoms=r.symptoms, address=r.address) for r in rows]


# --- doctor settings and lists (declared before /{visit_id} so the words are not read as ids) -----------


def _profile(db: Session, doctor: User) -> DoctorProfile:
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == doctor.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Doctor profile not found.")
    return profile


def _settings_out(profile: DoctorProfile) -> SettingsOut:
    return SettingsOut(
        enabled=profile.home_visits_enabled,
        radius_km=profile.service_radius_km,
        latitude=profile.base_latitude,
        longitude=profile.base_longitude,
        note=LOCATION_NOTE,
    )


@router.get("/doctor/settings", response_model=SettingsOut)
def get_settings(current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    return _settings_out(_profile(db, current_user))


@router.put("/doctor/settings", response_model=SettingsOut)
def put_settings(payload: SettingsIn, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    if (payload.latitude is None) != (payload.longitude is None):
        raise HTTPException(status_code=422, detail="Give both the latitude and the longitude, or neither.")
    if payload.latitude is not None:
        try:
            geo.validate_coordinates(payload.latitude, payload.longitude)
        except InvalidLocation as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    try:
        profile = workflow.save_settings(
            db, _profile(db, current_user), payload.enabled, payload.radius_km, payload.latitude, payload.longitude
        )
    except workflow.VisitError as exc:
        raise _refuse(exc) from None
    return _settings_out(profile)


@router.get("/doctor/offers", response_model=list[DoctorOffer])
def my_offers(current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    """Requests waiting for this doctor's answer (expired ones are settled first)."""
    workflow.advance_due(db, clock.now())
    return views.doctor_offers(db, current_user.id)


@router.get("/doctor/visits", response_model=Page[DoctorVisit])
def my_doctor_visits(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    query = db.query(HomeVisitRequest).filter(HomeVisitRequest.doctor_id == current_user.id)
    page = paginate(query.order_by(HomeVisitRequest.created_at.desc(), HomeVisitRequest.id.desc()), params, lambda r: r)
    return {**page, "items": views.doctor_visits(db, page["items"], current_user.id)}


@router.get("/admin/{visit_id}", response_model=AdminVisit)
def admin_view(visit_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """The one place an administrator sees a visit's phone and coordinates; every view is written to the audit log."""
    visit = _visit_or_404(db, visit_id)
    audit.record(
        db, current_user, "home_visit.admin_view", patient_id=visit.patient_id, target_type="home_visit",
        target_id=visit.id,
    )  # fmt: skip
    base = views.patient_views(db, [visit])[0]
    return AdminVisit(
        **base.model_dump(),
        patient_id=visit.patient_id,
        doctor_id=visit.doctor_id,
        phone=visit.contact_phone,
        latitude=visit.latitude,
        longitude=visit.longitude,
    )


# --- one visit --------------------------------------------------------------------------------------------


@router.get("/{visit_id}", response_model=PatientVisit)
def my_visit(visit_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    visit = _settle(db, _own_as_patient(db, current_user, visit_id))
    return views.patient_views(db, [visit])[0]


@router.post("/{visit_id}/cancel", response_model=PatientVisit)
def cancel(visit_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    visit = _settle(db, _own_as_patient(db, current_user, visit_id))
    try:
        workflow.cancel_by_patient(db, current_user, visit, clock.now())
    except workflow.VisitError as exc:
        raise _refuse(exc) from None
    return views.patient_views(db, [visit])[0]


def _doctor_step(db: Session, doctor: User, visit_id: int, step, *args) -> DoctorVisit:
    visit = _visit_or_404(db, visit_id)
    try:
        step(db, doctor, visit, *args, clock.now())
    except workflow.VisitError as exc:
        raise _refuse(exc) from None
    return views.doctor_visits(db, [visit], doctor.id)[0]


@router.post("/{visit_id}/accept", response_model=DoctorVisit)
def accept(visit_id: int, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    return _doctor_step(db, current_user, visit_id, workflow.accept)


@router.post("/{visit_id}/decline", response_model=VisitRef)
def decline(visit_id: int, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    visit = _visit_or_404(db, visit_id)
    try:
        workflow.decline(db, current_user, visit, clock.now())
    except workflow.VisitError as exc:
        raise _refuse(exc) from None
    return VisitRef(id=visit_id, status="declined")


@router.post("/{visit_id}/en-route", response_model=DoctorVisit)
def en_route(
    visit_id: int, payload: EnRouteIn, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    return _doctor_step(db, current_user, visit_id, workflow.en_route, payload.eta_minutes)


@router.post("/{visit_id}/arrived", response_model=DoctorVisit)
def arrived(visit_id: int, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    return _doctor_step(db, current_user, visit_id, workflow.arrived)


@router.post("/{visit_id}/complete", response_model=DoctorVisit)
def complete(visit_id: int, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    return _doctor_step(db, current_user, visit_id, workflow.complete)


@router.post("/{visit_id}/close", response_model=DoctorVisit)
def close(visit_id: int, payload: CloseIn, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    return _doctor_step(db, current_user, visit_id, workflow.close, payload)


@router.post("/{visit_id}/doctor-cancel", response_model=DoctorVisit)
def doctor_cancel(visit_id: int, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    return _doctor_step(db, current_user, visit_id, workflow.cancel_by_doctor)


@router.post("/{visit_id}/escalate", response_model=VisitRef)
def escalate(visit_id: int, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    """The doctor judges this is an emergency: the patient is told to call 1122 and the request ends.
    Allowed before accepting too, so it returns no patient details."""
    visit = _visit_or_404(db, visit_id)
    try:
        workflow.escalate(db, current_user, visit, clock.now())
    except workflow.VisitError as exc:
        raise _refuse(exc) from None
    return VisitRef(id=visit.id, status=visit.status, message=EMERGENCY_NOTICE)
