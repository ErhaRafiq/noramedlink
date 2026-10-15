from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, require_patient
from models import Appointment, DoctorProfile, User
from pagination import Page, PageParams, page_params, paginate
from schemas import (
    AppointmentBookingResponse,
    AppointmentCreate,
    AppointmentDoctorOut,
    AppointmentOut,
    AppointmentUpdate,
)
from services.dashboard_access import ensure_otp_attempts_allowed, grant_access_by_otp, record_otp_attempt

router = APIRouter(prefix="/appointments", tags=["appointments"])

# Admin approval sets the doctor profile's status to "approved".
VERIFIED_DOCTOR_STATUS = "approved"
PATIENT_SETTABLE_STATUSES = {"CANCELLED"}


def appointment_to_out(appointment: Appointment, fees: dict[int, int | None] | None = None) -> AppointmentOut:
    """`fees`: doctor id -> current consultation fee, looked up once per page (fees_for)."""
    return AppointmentOut(
        id=appointment.id,
        user_id=appointment.user_id,
        doctor_id=appointment.doctor_id,
        doctor_name=appointment.doctor_name,
        date=appointment.date,
        status=appointment.status,
        payment_status=appointment.payment_status,
        notes=appointment.notes,
        specialty=appointment.specialty,
        reason=appointment.reason,
        consultation_fee=(fees or {}).get(appointment.doctor_id) if appointment.doctor_id else None,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


def fees_for(db: Session, doctor_ids: set[int]) -> dict[int, int | None]:
    if not doctor_ids:
        return {}
    rows = db.query(DoctorProfile.user_id, DoctorProfile.consultation_fee).filter(DoctorProfile.user_id.in_(doctor_ids))
    return dict(rows.all())


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


def doctor_to_out(doctor: User) -> AppointmentDoctorOut:
    profile = doctor.doctor_profile
    return AppointmentDoctorOut(
        id=doctor.id,
        doctor_id=doctor.id,
        name=doctor.full_name,
        specialty=profile.specialization if profile else "General Medicine",
        location=profile.hospital_name if profile else "Nora MedLink Clinic",
        consultation_fee=profile.consultation_fee if profile else None,
    )


def filter_doctors(
    doctors: list[AppointmentDoctorOut],
    query: str | None,
    specialty: str | None,
    available_today: bool | None,
) -> list[AppointmentDoctorOut]:
    normalized_query = (query or "").strip().lower()
    normalized_specialty = (specialty or "").strip().lower()

    results = doctors
    if normalized_query:
        results = [
            doctor
            for doctor in results
            if normalized_query in doctor.name.lower()
            or normalized_query in doctor.specialty.lower()
            or normalized_query in doctor.location.lower()
        ]
    if normalized_specialty and normalized_specialty != "all specialties":
        results = [doctor for doctor in results if doctor.specialty.lower() == normalized_specialty]
    if available_today is not None:
        # Availability is not recorded yet, so no doctor is known to be available today.
        results = [doctor for doctor in results if doctor.available_today == available_today]

    return results


def aware(value: datetime) -> datetime:
    """A date without a time zone is taken as the server's local time (the browser sends ISO with a zone)."""
    return value.astimezone() if value.tzinfo is None else value


def resolve_doctor(payload: AppointmentCreate, db: Session) -> User:
    if not payload.doctor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a doctor to book.")
    doctor = verified_doctors_query(db).filter(User.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
    return doctor


@router.get("/doctors", response_model=list[AppointmentDoctorOut])
def list_doctors(
    query: str | None = None,
    specialty: str | None = None,
    available_today: bool | None = None,
    db: Session = Depends(get_db),
):
    doctors = verified_doctors_query(db).order_by(User.full_name.asc()).limit(100).all()
    return filter_doctors([doctor_to_out(doctor) for doctor in doctors], query, specialty, available_today)


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
    return {**page, "items": [appointment_to_out(a, fees) for a in page["items"]]}


@router.post("", response_model=AppointmentBookingResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    appointment_date = aware(payload.date) if payload.date else datetime.now(UTC)
    if appointment_date < datetime.now(UTC) - timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment date must be current or future.",
        )

    doctor = resolve_doctor(payload, db)
    patient_access_otp = payload.patient_access_otp.strip() if payload.patient_access_otp else ""
    if patient_access_otp:
        # Checked before anything is created, so a blocked request books nothing.
        ensure_otp_attempts_allowed(db, current_user.id)
    reason = payload.reason.strip() if payload.reason and payload.reason.strip() else None
    notes = payload.notes.strip() if payload.notes and payload.notes.strip() else reason

    appointment = Appointment(
        user_id=current_user.id,
        doctor_id=doctor.id,
        doctor_name=doctor.full_name,
        specialty=doctor.doctor_profile.specialization if doctor.doctor_profile else None,
        reason=reason,
        date=appointment_date,
        notes=notes,
        status="BOOKED",
        payment_status="PENDING",
    )
    db.add(appointment)

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
        appointment=appointment_to_out(appointment, fees_for(db, {doctor.id})),
        dashboard_access_granted=dashboard_access_granted,
    )


@router.put("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    if not can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Appointment access denied.")

    role = current_user.role.lower()
    if payload.payment_status is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Payment status changes only when Stripe confirms a payment."
        )
    if (
        payload.status is not None
        and role == "patient"
        and payload.status.strip().upper() not in PATIENT_SETTABLE_STATUSES
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patients can only cancel an appointment.")

    if payload.date is not None:
        new_date = aware(payload.date)
        if new_date < datetime.now(UTC) - timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment date must be current or future.",
            )
        appointment.date = new_date
    if payload.status is not None:
        appointment.status = payload.status.strip().upper()
    if payload.notes is not None:
        appointment.notes = payload.notes.strip() or None

    db.commit()
    db.refresh(appointment)
    return appointment_to_out(appointment, fees_for(db, {appointment.doctor_id} if appointment.doctor_id else set()))
