"""Patient medicine history (CRUD) and the medicine-safety check."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_patient_profile, require_patient
from models import MedicineHistory, PatientProfile, User
from pagination import Page, PageParams, page_params, paginate
from rate_limit import AI_LIMIT, limiter
from schemas import (
    MedicineHistoryCreate,
    MedicineHistoryOut,
    MedicineHistoryUpdate,
    MedicineSafetyCheckRequest,
    MedicineSafetyCheckResponse,
)
from services.medicine_safety import check_medicine_safety
from services.openai_service import fallback_notice, generate_openai_json
from services.patient_insights import annotate_fallback, clean_ai_text

router = APIRouter(prefix="/patient", tags=["patient"])


def medicine_to_out(medicine: MedicineHistory) -> MedicineHistoryOut:
    return MedicineHistoryOut(
        id=medicine.id,
        patient_id=medicine.patient_id,
        medicine_name=medicine.medicine_name,
        dosage=medicine.dosage,
        frequency=medicine.frequency,
        start_date=medicine.start_date,
        end_date=medicine.end_date,
        reason=medicine.reason,
        prescribed_by=medicine.prescribed_by,
        side_effects=medicine.side_effects,
        created_at=medicine.created_at,
        updated_at=medicine.updated_at,
    )


def patient_medicine_query(db: Session, profile: PatientProfile):
    return db.query(MedicineHistory).filter(MedicineHistory.patient_id == profile.user_id)


@router.get("/medicines", response_model=Page[MedicineHistoryOut])
def list_medicines(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    profile = get_patient_profile(db, current_user)
    query = patient_medicine_query(db, profile).order_by(MedicineHistory.created_at.desc(), MedicineHistory.id.desc())
    return paginate(query, params, medicine_to_out)


@router.post("/medicines", response_model=MedicineHistoryOut, status_code=status.HTTP_201_CREATED)
def create_medicine(
    payload: MedicineHistoryCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)
):
    profile = get_patient_profile(db, current_user)
    medicine = MedicineHistory(
        patient_id=profile.user_id,
        medicine_name=payload.medicine_name.strip(),
        dosage=payload.dosage.strip(),
        frequency=payload.frequency.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason.strip(),
        prescribed_by=payload.prescribed_by.strip() if payload.prescribed_by else None,
        side_effects=payload.side_effects.strip() if payload.side_effects else None,
    )
    db.add(medicine)
    db.commit()
    db.refresh(medicine)
    return medicine_to_out(medicine)


@router.put("/medicines/{medicine_id}", response_model=MedicineHistoryOut)
def update_medicine(
    medicine_id: int,
    payload: MedicineHistoryUpdate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    profile = get_patient_profile(db, current_user)
    medicine = patient_medicine_query(db, profile).filter(MedicineHistory.id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine history entry not found.")

    for field_name in [
        "medicine_name",
        "dosage",
        "frequency",
        "start_date",
        "end_date",
        "reason",
        "prescribed_by",
        "side_effects",
    ]:
        value = getattr(payload, field_name)
        if value is not None:
            setattr(medicine, field_name, value.strip() if isinstance(value, str) else value)

    db.commit()
    db.refresh(medicine)
    return medicine_to_out(medicine)


@router.delete("/medicines/{medicine_id}")
def delete_medicine(medicine_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = get_patient_profile(db, current_user)
    medicine = patient_medicine_query(db, profile).filter(MedicineHistory.id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine history entry not found.")
    db.delete(medicine)
    db.commit()
    return {"message": "Medicine history deleted successfully."}


@router.post("/medicine-safety/check", response_model=MedicineSafetyCheckResponse)
@limiter.limit(AI_LIMIT)
async def medicine_safety_check(
    request: Request,
    payload: MedicineSafetyCheckRequest,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    profile = get_patient_profile(db, current_user)
    medicines = patient_medicine_query(db, profile).order_by(MedicineHistory.created_at.desc()).all()
    status_label, reason, warnings = check_medicine_safety(
        payload.medicine_name,
        payload.dosage,
        payload.known_allergies,
        medicines,
    )
    ai_result = await generate_openai_json(
        instructions=(
            "You explain medicine safety observations for a patient dashboard. "
            "Use only the supplied medicine history and allergy text. Do not prescribe, change dosage, "
            "rate the risk, or say a medicine is safe. Return JSON with reason (a short explanation) "
            "and warnings (an array of points for the patient to raise with their doctor)."
        ),
        prompt="\n".join(
            [
                f"Requested medicine: {payload.medicine_name}",
                f"Requested dosage: {payload.dosage or 'not provided'}",
                f"Known allergies or notes: {payload.known_allergies or 'not provided'}",
                "Saved medicine history:",
                "\n".join(
                    f"- {medicine.medicine_name}, {medicine.dosage}, {medicine.frequency}, reason: {medicine.reason}, side effects: {medicine.side_effects or 'none'}"
                    for medicine in medicines[:12]
                )
                or "No saved medicine history.",
            ]
        ),
    )

    if isinstance(ai_result.data, dict):
        # The rules above decide the status; the AI only explains and never changes it
        # (AGENTS.md 6.2). Its text is labelled as AI-generated (6.4).
        ai_reason = clean_ai_text(ai_result.data.get("reason"), "", 800)
        ai_warnings = ai_result.data.get("warnings")
        if isinstance(ai_warnings, list):
            warnings.extend(f"AI observation: {str(w).strip()}" for w in ai_warnings if str(w).strip())
        if ai_reason:
            reason = f"{reason} AI-generated explanation (advisory, verify with a clinician): {ai_reason}"
    else:
        warnings.append(fallback_notice(ai_result.error))
        reason = annotate_fallback(reason, ai_result.error)

    warnings = list(dict.fromkeys(warning for warning in warnings if warning))
    return MedicineSafetyCheckResponse(status=status_label, reason=reason, warnings=warnings)
