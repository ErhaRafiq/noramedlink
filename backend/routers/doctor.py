from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_doctor
from models import DoctorAvailability, User
from schemas import AvailabilityIn, AvailabilityOut, AvailabilityWindow
from services import scheduling

router = APIRouter(prefix="/doctor", tags=["doctor"])


@router.get("/dashboard")
def doctor_dashboard(current_user: User = Depends(require_doctor)):
    """The signed-in doctor's profile. Appointments, patients and counts come from /doctor/overview."""
    profile = current_user.doctor_profile
    return {
        "doctor": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone": current_user.phone,
            "specialization": profile.specialization if profile else "",
            "hospital_name": profile.hospital_name if profile else "",
            "verification_status": profile.verification_status if profile else "pending",
            "consultation_fee": profile.consultation_fee if profile else None,
        },
    }


def availability_out(rows: list[DoctorAvailability]) -> AvailabilityOut:
    ordered = sorted(rows, key=lambda r: (r.weekday, r.start_time))
    return AvailabilityOut(
        timezone=scheduling.CLINIC_TZ_NAME,
        slot_choices=list(scheduling.SLOT_CHOICES),
        windows=[
            AvailabilityWindow(
                weekday=r.weekday, start_time=r.start_time, end_time=r.end_time, slot_minutes=r.slot_minutes
            )
            for r in ordered
        ],
    )


@router.get("/availability", response_model=AvailabilityOut)
def get_availability(current_user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    """The doctor's weekly windows (clinic time)."""
    return availability_out(scheduling.windows_of(db, [current_user.id])[current_user.id])


@router.put("/availability", response_model=AvailabilityOut)
def set_availability(
    payload: AvailabilityIn, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    """Replace the weekly windows. Appointments already booked stay as they are."""
    windows = [scheduling.WindowInput(w.weekday, w.start_time, w.end_time, w.slot_minutes) for w in payload.windows]
    return availability_out(scheduling.save_windows(db, current_user.id, windows))
