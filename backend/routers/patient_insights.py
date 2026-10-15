"""Patient health flags: what the fixed rules found in the patient's own reports, in everyday words."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_patient
from models import User
from schemas import HealthFlagsOut
from services.patient_flags import health_flags

router = APIRouter(prefix="/patient", tags=["patient"])


@router.get("/health-flags", response_model=HealthFlagsOut)
def list_health_flags(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """The patient dashboard's "Health flags" (from the same rules as the report checks)."""
    return health_flags(db, current_user.id)
