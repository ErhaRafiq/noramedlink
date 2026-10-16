"""Symptom checker (Module 7): the kind of doctor to see first, or an emergency message.

Open to visitors who are not signed in, because the emergency advice must never wait behind a login.
The rules live in services/symptom_checker.py. A red flag returns the emergency notice with no
specialists and no booking. Every run is saved (admin counts); the text is never logged.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_optional_user
from models import SymptomSession, User
from rate_limit import SYMPTOM_LIMIT, limiter
from routers.appointments import verified_directory
from schemas import SpecialtySuggestionOut, SymptomCheckIn, SymptomCheckOut
from services import symptom_checker as checker

router = APIRouter(prefix="/symptoms", tags=["symptoms"])

ADVISORY = (
    "Advisory only, built by fixed rules, not a diagnosis. It suggests whom to see first; a doctor decides. "
    "If you feel worse or are worried, get care sooner."
)


@router.post("/check", response_model=SymptomCheckOut)
@limiter.limit(SYMPTOM_LIMIT)
def check_symptoms(
    request: Request,
    payload: SymptomCheckIn,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    flags = checker.red_flags(payload.text)
    session = SymptomSession(
        user_id=current_user.id if current_user else None,
        symptom_text=payload.text,
        red_flag=bool(flags),
        red_flags=";".join(flag.id for flag in flags),
    )
    if flags:
        db.add(session)
        db.commit()
        return SymptomCheckOut(
            emergency=True,
            emergency_notice=checker.EMERGENCY_NOTICE,
            warning_signs=[flag.label for flag in flags],
            advisory=ADVISORY,
        )

    suggestions = checker.suggest_specialties(payload.text)
    directory = verified_directory(db)
    session.specialty = suggestions[0].specialty
    db.add(session)
    db.commit()
    return SymptomCheckOut(
        emergency=False,
        suggestions=[
            SpecialtySuggestionOut(
                specialty=s.specialty,
                plain=s.plain,
                matched=s.matched,
                fallback=s.fallback,
                doctors=checker.rank_doctors(directory, s.aliases),
            )
            for s in suggestions
        ],
        advisory=ADVISORY,
    )
