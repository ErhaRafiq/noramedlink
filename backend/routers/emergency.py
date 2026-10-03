"""Home-visit requests (emergency_bookings), ported from /api/emergency/book.

The former Next route invented a dispatch: it picked a random name from a hard-coded
list, set status DOCTOR_ASSIGNED and showed an 18-minute ETA. Nothing is dispatched,
so a request is now recorded as REQUESTED with no doctor and no ETA, and the response
directs real emergencies to 1122. Phase 2d replaces this with the home-visit engine.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_patient
from models import EmergencyBooking, User

router = APIRouter(prefix="/emergency", tags=["emergency"])

EMERGENCY_NOTICE = (
    "This is not an ambulance or emergency service. "
    "If this is an emergency, call 1122 or go to the nearest emergency department now."
)
NOT_ASSIGNED = "Not assigned"


class EmergencyRequestCreate(BaseModel):
    model_config = {"populate_by_name": True}

    patient_name: str = Field(alias="patientName", min_length=1, max_length=160)
    phone: str = Field(min_length=1, max_length=40)
    address: str = Field(min_length=1)
    symptoms: str = Field(min_length=1)
    latitude: float | None = None
    longitude: float | None = None


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_emergency_request(
    payload: EmergencyRequestCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    booking = EmergencyBooking(
        user_id=current_user.id,
        patient_name=payload.patient_name.strip(),
        phone=payload.phone.strip(),
        address=payload.address.strip(),
        symptoms=payload.symptoms.strip(),
        doctor_name=NOT_ASSIGNED,  # column is NOT NULL; no doctor has been assigned
        status="REQUESTED",
        estimated_minutes=0,  # column is NOT NULL; there is no ETA (returned as null)
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {
        "message": f"Request recorded. No doctor has been assigned yet. {EMERGENCY_NOTICE}",
        "booking": {
            "id": booking.id,
            "doctorName": None,
            "status": booking.status,
            "estimatedMinutes": None,
            "createdAt": booking.created_at,
        },
        "emergencyNotice": EMERGENCY_NOTICE,
    }
