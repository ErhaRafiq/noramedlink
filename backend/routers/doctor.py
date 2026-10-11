from fastapi import APIRouter, Depends

from dependencies import require_doctor
from models import User

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
        },
    }
