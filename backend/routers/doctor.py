from fastapi import APIRouter, Depends

from dependencies import require_doctor
from models import User


router = APIRouter(prefix="/doctor", tags=["doctor"])


@router.get("/dashboard")
def doctor_dashboard(current_user: User = Depends(require_doctor)):
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
        "stats": {
            "assigned_patients": 0,
            "pending_consults": 0,
            "records_reviewed": 0,
            "future_modules": 4,
        },
        "modules": [
            {
                "title": "Patient access by consent",
                "description": "Doctors will request patient-approved access before reviewing private records.",
            },
            {
                "title": "Report review queue",
                "description": "Uploaded OCR reports can be triaged by department and urgency.",
            },
            {
                "title": "Appointment workspace",
                "description": "Upcoming appointments and patient summaries will appear in one clinical view.",
            },
            {
                "title": "Prescription guidance",
                "description": "Future modules can support notes, prescriptions, and follow-up reminders.",
            },
        ],
    }
