from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_doctor
from models import User
from schemas import ConsultationFeeIn, ConsultationFeeOut

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


@router.put("/consultation-fee", response_model=ConsultationFeeOut)
def set_consultation_fee(
    payload: ConsultationFeeIn, current_user: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    """What patients pay online for one consultation (whole PKR). Payments already started keep their amount."""
    profile = current_user.doctor_profile
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")
    profile.consultation_fee = payload.consultation_fee
    db.commit()
    return ConsultationFeeOut(consultation_fee=profile.consultation_fee)
