from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, require_patient
from models import Appointment, PatientDashboardAccess, PatientDashboardOtp, User
from schemas import (
    AppointmentBookingResponse,
    AppointmentCreate,
    AppointmentDoctorOut,
    AppointmentOut,
    AppointmentUpdate,
)


router = APIRouter(prefix="/appointments", tags=["appointments"])

DEMO_DOCTORS = [
    {
        "id": 1001,
        "name": "Dr. Ayesha Khan",
        "specialty": "Cardiology",
        "location": "Lahore Medical Center",
        "rating": 4.9,
        "available_today": True,
    },
    {
        "id": 1002,
        "name": "Dr. Hamza Ali",
        "specialty": "Dermatology",
        "location": "Gulberg Clinic, Lahore",
        "rating": 4.7,
        "available_today": False,
    },
    {
        "id": 1003,
        "name": "Dr. Sara Ahmed",
        "specialty": "Pediatrics",
        "location": "Children Care Hospital",
        "rating": 4.8,
        "available_today": True,
    },
    {
        "id": 1004,
        "name": "Dr. Usman Raza",
        "specialty": "Neurology",
        "location": "Johar Town Specialist Clinic",
        "rating": 4.6,
        "available_today": True,
    },
    {
        "id": 1005,
        "name": "Dr. Fatima Noor",
        "specialty": "Orthopedics",
        "location": "Model Town Health Center",
        "rating": 4.8,
        "available_today": False,
    },
    {
        "id": 1006,
        "name": "Dr. Bilal Siddiqui",
        "specialty": "General Medicine",
        "location": "DHA Family Clinic",
        "rating": 4.5,
        "available_today": True,
    },
]

CONSULTATION_ACCESS_HOURS = 2


def appointment_to_out(appointment: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=appointment.id,
        user_id=appointment.user_id,
        doctor_id=appointment.doctor_id,
        doctor_name=appointment.doctor_name,
        date=appointment.date,
        status=appointment.status,
        payment_status=appointment.payment_status,
        notes=appointment.notes,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


def can_access_appointment(user: User, appointment: Appointment) -> bool:
    role = user.role.lower()
    return appointment.user_id == user.id or (role == "doctor" and appointment.doctor_id == user.id)


def doctor_to_out(doctor: User) -> AppointmentDoctorOut:
    profile = doctor.doctor_profile
    return AppointmentDoctorOut(
        id=doctor.id,
        doctor_id=doctor.id,
        name=doctor.full_name,
        specialty=profile.specialization if profile else "General Medicine",
        location=profile.hospital_name if profile else "Nora MedLink Clinic",
        rating=4.8,
        available_today=True,
        source="registered",
    )


def demo_doctor_to_out(doctor: dict[str, object]) -> AppointmentDoctorOut:
    return AppointmentDoctorOut(
        id=int(doctor["id"]),
        doctor_id=None,
        name=str(doctor["name"]),
        specialty=str(doctor["specialty"]),
        location=str(doctor["location"]),
        rating=float(doctor["rating"]),
        available_today=bool(doctor["available_today"]),
        source="demo",
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
        results = [doctor for doctor in results if doctor.available_today == available_today]

    return results


def resolve_doctor(payload: AppointmentCreate, db: Session) -> User | None:
    if payload.doctor_id:
        doctor = db.get(User, payload.doctor_id)
        if not doctor or doctor.role.lower() != "doctor":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return doctor

    return (
        db.query(User)
        .filter(User.role.ilike("doctor"), User.full_name == payload.doctor_name.strip())
        .first()
    )


def grant_temporary_dashboard_access_by_otp(
    db: Session,
    doctor_id: int,
    otp_code: str,
    expected_patient_id: int,
) -> bool:
    now = datetime.now(timezone.utc)
    otp = (
        db.query(PatientDashboardOtp)
        .filter(
            PatientDashboardOtp.code == otp_code.strip(),
            PatientDashboardOtp.used_at.is_(None),
            PatientDashboardOtp.expires_at > now,
            PatientDashboardOtp.patient_id == expected_patient_id,
        )
        .first()
    )

    if not otp:
        return False

    otp.used_at = now
    expires_at = now + timedelta(hours=CONSULTATION_ACCESS_HOURS)
    access = (
        db.query(PatientDashboardAccess)
        .filter(
            PatientDashboardAccess.doctor_id == doctor_id,
            PatientDashboardAccess.patient_id == expected_patient_id,
        )
        .first()
    )

    if access:
        access.status = "ACTIVE"
        access.expires_at = expires_at
        access.ended_at = None
    else:
        db.add(
            PatientDashboardAccess(
                doctor_id=doctor_id,
                patient_id=expected_patient_id,
                status="ACTIVE",
                expires_at=expires_at,
            )
        )

    return True


@router.get("/doctors", response_model=list[AppointmentDoctorOut])
def list_doctors(
    query: str | None = None,
    specialty: str | None = None,
    available_today: bool | None = None,
    db: Session = Depends(get_db),
):
    registered_doctors = (
        db.query(User)
        .filter(User.role.ilike("doctor"))
        .order_by(User.full_name.asc())
        .limit(100)
        .all()
    )
    doctors = [doctor_to_out(doctor) for doctor in registered_doctors]
    registered_names = {doctor.name.lower() for doctor in doctors}
    doctors.extend(
        demo_doctor_to_out(doctor)
        for doctor in DEMO_DOCTORS
        if str(doctor["name"]).lower() not in registered_names
    )

    return filter_doctors(doctors, query, specialty, available_today)


@router.get("", response_model=list[AppointmentOut])
def list_appointments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Appointment)
    if current_user.role.lower() == "doctor":
        query = query.filter(
            (Appointment.doctor_id == current_user.id) | (Appointment.doctor_name == current_user.full_name)
        )
    else:
        query = query.filter(Appointment.user_id == current_user.id)

    appointments = query.order_by(Appointment.date.desc()).limit(100).all()
    return [appointment_to_out(appointment) for appointment in appointments]


@router.post("", response_model=AppointmentBookingResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    appointment_date = payload.date or datetime.now(timezone.utc)
    if appointment_date < datetime.now(timezone.utc) - timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment date must be current or future.",
        )

    doctor = resolve_doctor(payload, db)

    appointment = Appointment(
        user_id=current_user.id,
        doctor_id=doctor.id if doctor else None,
        doctor_name=(doctor.full_name if doctor else payload.doctor_name.strip()),
        date=appointment_date,
        notes=payload.notes.strip() if payload.notes else None,
        status="BOOKED",
        payment_status="PENDING",
    )
    db.add(appointment)

    dashboard_access_granted = False
    patient_access_otp = payload.patient_access_otp.strip() if payload.patient_access_otp else ""
    if patient_access_otp and doctor:
        dashboard_access_granted = grant_temporary_dashboard_access_by_otp(
            db=db,
            doctor_id=doctor.id,
            otp_code=patient_access_otp,
            expected_patient_id=current_user.id,
        )

    db.commit()
    db.refresh(appointment)
    message = (
        "Appointment booked and temporary dashboard access shared with the doctor."
        if dashboard_access_granted
        else "Appointment booked successfully."
    )
    return AppointmentBookingResponse(
        message=message,
        appointment=appointment_to_out(appointment),
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

    if payload.date is not None:
        if payload.date < datetime.now(timezone.utc) - timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment date must be current or future.",
            )
        appointment.date = payload.date
    if payload.status is not None:
        appointment.status = payload.status.strip().upper()
    if payload.payment_status is not None:
        appointment.payment_status = payload.payment_status.strip().upper()
    if payload.notes is not None:
        appointment.notes = payload.notes.strip() or None

    db.commit()
    db.refresh(appointment)
    return appointment_to_out(appointment)


@router.delete("/{appointment_id}")
def delete_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    if not can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Appointment access denied.")

    db.delete(appointment)
    db.commit()
    return {"message": "Appointment deleted successfully."}
