"""Doctor search and appointments (Module 5): the public doctor list and slots, and the signed-in
booking, rescheduling, cancelling, finishing and reviewing. The rules live in services/appointments.py
and services/scheduling.py; this file checks who may do what.
"""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, require_patient
from models import Appointment, AppointmentReview, DoctorProfile, User
from pagination import Page, PageParams, page_params, paginate
from schemas import (
    AppointmentBookingResponse,
    AppointmentCreate,
    AppointmentDoctorOut,
    AppointmentOut,
    AppointmentUpdate,
    DaySlotsOut,
    ReviewIn,
    ReviewOut,
    SlotOut,
    SlotsOut,
)
from services import appointments as booking
from services import scheduling
from services.dashboard_access import ensure_otp_attempts_allowed, grant_access_by_otp, record_otp_attempt
from services.profiles import split_list

router = APIRouter(prefix="/appointments", tags=["appointments"])

# Admin approval sets the doctor profile's status to "approved".
VERIFIED_DOCTOR_STATUS = "approved"
DOCTOR_LIMIT = 100
MAX_SLOT_DAYS = 14
SortKey = Literal["soonest", "rating", "fee", "experience", "name"]


def fees_for(db: Session, doctor_ids: set[int]) -> dict[int, int | None]:
    if not doctor_ids:
        return {}
    rows = db.query(DoctorProfile.user_id, DoctorProfile.consultation_fee).filter(DoctorProfile.user_id.in_(doctor_ids))
    return dict(rows.all())


def appointment_to_out(
    appointment: Appointment, fees: dict[int, int | None] | None = None, reviewed: set[int] | None = None
) -> AppointmentOut:
    """`fees` and `reviewed` are looked up once per page (fees_for, reviewed_ids)."""
    return AppointmentOut(
        id=appointment.id,
        user_id=appointment.user_id,
        doctor_id=appointment.doctor_id,
        doctor_name=appointment.doctor_name,
        date=appointment.date,
        duration_minutes=appointment.duration_minutes,
        mode=appointment.mode,
        status=appointment.status,
        payment_status=appointment.payment_status,
        notes=appointment.notes,
        specialty=appointment.specialty,
        reason=appointment.reason,
        consultation_fee=(fees or {}).get(appointment.doctor_id) if appointment.doctor_id else None,
        reviewed=appointment.id in (reviewed or set()),
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


def reviewed_ids(db: Session, appointment_ids: list[int]) -> set[int]:
    if not appointment_ids:
        return set()
    rows = db.query(AppointmentReview.appointment_id).filter(AppointmentReview.appointment_id.in_(appointment_ids))
    return {appointment_id for (appointment_id,) in rows}


def one_out(db: Session, appointment: Appointment) -> AppointmentOut:
    doctor_ids = {appointment.doctor_id} if appointment.doctor_id else set()
    return appointment_to_out(appointment, fees_for(db, doctor_ids), reviewed_ids(db, [appointment.id]))


def can_access_appointment(user: User, appointment: Appointment) -> bool:
    role = user.role.lower()
    return role == "admin" or appointment.user_id == user.id or (role == "doctor" and appointment.doctor_id == user.id)


def verified_doctors_query(db: Session):
    """Active doctors whose profile an admin has approved. The only doctors patients may
    discover or book."""
    return (
        db.query(User)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .filter(
            func.lower(User.role) == "doctor",
            User.is_active.is_(True),
            func.lower(DoctorProfile.verification_status) == VERIFIED_DOCTOR_STATUS,
        )
    )


def doctor_to_out(
    doctor: User,
    rating: tuple[float, int] | None = None,
    availability: tuple[bool, datetime | None] | None = None,
    has_schedule: bool = False,
) -> AppointmentDoctorOut:
    profile = doctor.doctor_profile
    available_today, next_available = availability or (False, None)
    return AppointmentDoctorOut(
        id=doctor.id,
        doctor_id=doctor.id,
        name=doctor.full_name,
        specialty=profile.specialization if profile else "General Medicine",
        location=profile.hospital_name if profile else "Nora MedLink Clinic",
        rating=rating[0] if rating else None,
        rating_count=rating[1] if rating else 0,
        available_today=available_today,
        next_available=next_available,
        has_schedule=has_schedule,
        consultation_fee=profile.consultation_fee if profile else None,
        qualifications=profile.qualifications if profile else None,
        experience_years=profile.experience_years if profile else None,
        bio=profile.bio if profile else None,
        city=profile.city if profile else None,
        languages=split_list(profile.languages) if profile else [],
        consultation_modes=split_list(profile.consultation_modes) if profile else [],
    )


def filter_doctors(
    doctors: list[AppointmentDoctorOut],
    query: str | None = None,
    specialty: str | None = None,
    available_today: bool | None = None,
    city: str | None = None,
    mode: str | None = None,
    max_fee: int | None = None,
    min_rating: float | None = None,
    sort: SortKey = "soonest",
) -> list[AppointmentDoctorOut]:
    text = (query or "").strip().lower()
    wanted_specialty = (specialty or "").strip().lower()
    wanted_city = (city or "").strip().lower()

    results = doctors
    if text:
        results = [
            d
            for d in results
            if any(
                text in (value or "").lower() for value in (d.name, d.specialty, d.location, d.city, d.qualifications)
            )
        ]
    if wanted_specialty and wanted_specialty != "all specialties":
        results = [d for d in results if d.specialty.lower() == wanted_specialty]
    if wanted_city:
        results = [d for d in results if wanted_city in f"{d.city or ''} {d.location}".lower()]
    if mode:
        results = [d for d in results if mode in d.consultation_modes]
    if available_today is not None:
        results = [d for d in results if d.available_today == available_today]
    if max_fee is not None:
        # A doctor with no fee set is not "cheap": leave them out when the patient limits the price.
        results = [d for d in results if d.consultation_fee is not None and d.consultation_fee <= max_fee]
    if min_rating is not None:
        results = [d for d in results if d.rating is not None and d.rating >= min_rating]

    far = datetime.max.replace(tzinfo=UTC)
    keys = {
        "soonest": lambda d: (d.next_available or far, d.name.lower()),
        "rating": lambda d: (-(d.rating or 0), -d.rating_count, d.name.lower()),
        "fee": lambda d: (d.consultation_fee if d.consultation_fee is not None else 10**9, d.name.lower()),
        "experience": lambda d: (-(d.experience_years or 0), d.name.lower()),
        "name": lambda d: d.name.lower(),
    }
    return sorted(results, key=keys[sort])


def verified_directory(db: Session) -> list[AppointmentDoctorOut]:
    """Every verified, active doctor with their real rating, fee and next open slot (also used by the symptom checker)."""
    doctors = verified_doctors_query(db).order_by(User.full_name.asc()).limit(DOCTOR_LIMIT).all()
    ids = [doctor.id for doctor in doctors]
    ratings = booking.ratings_for(db, ids)
    availability = scheduling.directory_availability(db, ids)
    scheduled = {doctor_id for doctor_id, rows in scheduling.windows_of(db, ids).items() if rows}
    return [doctor_to_out(d, ratings.get(d.id), availability.get(d.id), d.id in scheduled) for d in doctors]


def aware(value: datetime) -> datetime:
    """A date without a time zone is taken as clinic time (the browser sends ISO with a zone)."""
    return value.replace(tzinfo=scheduling.CLINIC_TZ) if value.tzinfo is None else value


def get_verified_doctor(db: Session, doctor_id: int) -> User:
    doctor = verified_doctors_query(db).filter(User.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
    return doctor


def get_appointment(db: Session, user: User, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    if not can_access_appointment(user, appointment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Appointment access denied.")
    return appointment


# --- public: doctors, slots, reviews -------------------------------------------------------------


@router.get("/doctors", response_model=list[AppointmentDoctorOut])
def list_doctors(
    query: str | None = Query(default=None, max_length=100),
    specialty: str | None = Query(default=None, max_length=120),
    city: str | None = Query(default=None, max_length=80),
    mode: Literal["in_clinic", "online", "home"] | None = None,
    available_today: bool | None = None,
    max_fee: int | None = Query(default=None, ge=0, le=1_000_000),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    sort: SortKey = "soonest",
    db: Session = Depends(get_db),
):
    """Verified, active doctors only, with their real rating, fee and next open slot."""
    return filter_doctors(
        verified_directory(db), query, specialty, available_today, city, mode, max_fee, min_rating, sort
    )


@router.get("/doctors/{doctor_id}/slots", response_model=SlotsOut)
def doctor_slots(
    doctor_id: int,
    from_date: date | None = Query(default=None, alias="from"),
    days: int = Query(default=7, ge=1, le=MAX_SLOT_DAYS),
    db: Session = Depends(get_db),
):
    """Bookable times, day by day (clinic time). A slot with available=false is taken or too soon."""
    get_verified_doctor(db, doctor_id)
    first = from_date or scheduling.clinic_date(scheduling.now_utc())
    result = scheduling.slots_range(db, doctor_id, first, days)
    return SlotsOut(
        timezone=scheduling.CLINIC_TZ_NAME,
        days=[
            DaySlotsOut(day=day, slots=[SlotOut(start=s.start, end=s.end, available=s.available) for s in slots])
            for day, slots in result
        ],
    )


@router.get("/doctors/{doctor_id}/reviews", response_model=list[ReviewOut])
def doctor_reviews(doctor_id: int, limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    """The latest ratings, without the patient's name."""
    get_verified_doctor(db, doctor_id)
    rows = (
        db.query(AppointmentReview)
        .filter(AppointmentReview.doctor_id == doctor_id)
        .order_by(AppointmentReview.created_at.desc())
        .limit(limit)
        .all()
    )
    return [ReviewOut(rating=r.rating, comment=r.comment, created_at=r.created_at) for r in rows]


# --- signed in -----------------------------------------------------------------------------------


@router.get("", response_model=Page[AppointmentOut])
def list_appointments(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Appointment)
    if current_user.role.lower() == "doctor":
        # Matched by id only: matching by name would show one doctor another's patients.
        query = query.filter(Appointment.doctor_id == current_user.id)
    else:
        query = query.filter(Appointment.user_id == current_user.id)

    page = paginate(query.order_by(Appointment.date.desc(), Appointment.id.desc()), params, lambda a: a)
    fees = fees_for(db, {a.doctor_id for a in page["items"] if a.doctor_id})
    reviewed = reviewed_ids(db, [a.id for a in page["items"]])
    return {**page, "items": [appointment_to_out(a, fees, reviewed) for a in page["items"]]}


@router.post("", response_model=AppointmentBookingResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    doctor = get_verified_doctor(db, payload.doctor_id)
    patient_access_otp = payload.patient_access_otp.strip() if payload.patient_access_otp else ""
    if patient_access_otp:
        # Checked before anything is created, so a blocked request books nothing.
        ensure_otp_attempts_allowed(db, current_user.id)
    reason = payload.reason.strip() if payload.reason and payload.reason.strip() else None
    notes = payload.notes.strip() if payload.notes and payload.notes.strip() else reason

    appointment = booking.create(db, current_user, doctor, aware(payload.date), payload.mode, reason, notes)

    dashboard_access_granted = False
    if patient_access_otp:
        dashboard_access_granted = (
            grant_access_by_otp(db, doctor.id, patient_access_otp, expected_patient_id=current_user.id, commit=False)
            is not None
        )
        record_otp_attempt(db, current_user.id, "booking", dashboard_access_granted, commit=False)

    db.commit()
    db.refresh(appointment)
    message = (
        "Appointment booked and temporary dashboard access shared with the doctor."
        if dashboard_access_granted
        else "Appointment booked successfully."
    )
    return AppointmentBookingResponse(
        message=message,
        appointment=one_out(db, appointment),
        dashboard_access_granted=dashboard_access_granted,
    )


@router.put("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Patients move or cancel their own booking; the treating doctor completes, marks no-show or cancels."""
    appointment = get_appointment(db, current_user, appointment_id)
    role = current_user.role.lower()
    if payload.payment_status is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Payment status changes only when Stripe confirms a payment."
        )
    if role == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrators do not change appointments.")

    new_status = payload.status.strip().upper() if payload.status is not None else None
    allowed = {"patient": {"CANCELLED"}, "doctor": {"COMPLETED", "NO_SHOW", "CANCELLED"}}[role]
    if new_status is not None and new_status not in allowed:
        who = (
            "Patients can only cancel an appointment."
            if role == "patient"
            else "Choose completed, no-show or cancelled."
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=who)
    if payload.date is not None and role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the patient can move an appointment.")

    patient = current_user if role == "patient" else db.get(User, appointment.user_id)
    if payload.date is not None:
        booking.reschedule(db, appointment, aware(payload.date), patient)
    if new_status == "CANCELLED":
        booking.cancel(db, appointment, patient, by_doctor=role == "doctor")
    elif new_status is not None:
        booking.finish(db, appointment, new_status)
    if payload.notes is not None:
        appointment.notes = payload.notes.strip() or None

    db.commit()
    db.refresh(appointment)
    return one_out(db, appointment)


@router.post("/{appointment_id}/review", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def review_appointment(
    appointment_id: int,
    payload: ReviewIn,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """The patient rates a completed appointment, once."""
    appointment = get_appointment(db, current_user, appointment_id)
    review = booking.create_review(db, appointment, payload.rating, payload.comment)
    db.commit()
    db.refresh(review)
    return ReviewOut(rating=review.rating, comment=review.comment, created_at=review.created_at)
