"""Patient insights: risk observations, health tips and doctor summaries (list and generate)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_patient_profile, require_patient
from models import DoctorSummary, HealthRiskPrediction, HealthTip, MedicineHistory, User
from rate_limit import AI_LIMIT, limiter
from routers.patient_medicines import patient_medicine_query
from schemas import DoctorSummaryOut, HealthRiskPredictionOut, HealthTipOut
from services.openai_service import fallback_notice, generate_openai_json, generate_openai_text
from services.patient_insights import (
    annotate_fallback,
    build_doctor_summary,
    build_health_tips,
    build_risk_predictions,
    patient_context_for_ai,
    report_context,
    validate_ai_health_tips,
    validate_ai_risk_predictions,
)

router = APIRouter(prefix="/patient", tags=["patient"])


def risk_to_out(prediction: HealthRiskPrediction) -> HealthRiskPredictionOut:
    return HealthRiskPredictionOut(
        id=prediction.id,
        patient_id=prediction.patient_id,
        risk_title=prediction.risk_title,
        risk_level=prediction.risk_level,
        reason=prediction.reason,
        recommendation=prediction.recommendation,
        created_at=prediction.created_at,
    )


def tip_to_out(tip: HealthTip) -> HealthTipOut:
    return HealthTipOut(
        id=tip.id,
        patient_id=tip.patient_id,
        category=tip.category,
        tip_text=tip.tip_text,
        based_on_data=tip.based_on_data,
        created_at=tip.created_at,
    )


def summary_to_out(summary: DoctorSummary) -> DoctorSummaryOut:
    return DoctorSummaryOut(
        id=summary.id,
        patient_id=summary.patient_id,
        summary_text=summary.summary_text,
        generated_at=summary.generated_at,
    )


@router.get("/risk-predictions", response_model=list[HealthRiskPredictionOut])
def list_risk_predictions(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = get_patient_profile(db, current_user)
    predictions = (
        db.query(HealthRiskPrediction)
        .filter(HealthRiskPrediction.patient_id == profile.user_id)
        .order_by(HealthRiskPrediction.created_at.desc())
        .limit(10)
        .all()
    )
    return [risk_to_out(prediction) for prediction in predictions]


@router.post("/risk-predictions/generate", response_model=list[HealthRiskPredictionOut])
@limiter.limit(AI_LIMIT)
async def generate_risk_predictions(
    request: Request, current_user: User = Depends(require_patient), db: Session = Depends(get_db)
):
    profile = get_patient_profile(db, current_user)
    documents = report_context(db, profile)
    medicines = patient_medicine_query(db, profile).order_by(MedicineHistory.created_at.desc()).all()
    ai_result = await generate_openai_json(
        instructions=(
            "You generate cautious clinical risk observations for a patient dashboard. "
            "Use only the supplied reports and medicine history. Do not diagnose. "
            "Return up to 3 items with risk_title, risk_level (Low, Medium, High), reason, and recommendation."
        ),
        prompt=patient_context_for_ai(documents, medicines),
    )
    generated = validate_ai_risk_predictions(ai_result.data)
    if not generated:
        generated = build_risk_predictions(profile, documents, medicines)
        if generated:
            generated[0]["reason"] = annotate_fallback(generated[0]["reason"], ai_result.error)

    predictions = [HealthRiskPrediction(patient_id=profile.user_id, **prediction) for prediction in generated]
    db.add_all(predictions)
    db.commit()
    for prediction in predictions:
        db.refresh(prediction)
    return [risk_to_out(prediction) for prediction in predictions]


@router.get("/health-tips", response_model=list[HealthTipOut])
def list_health_tips(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = get_patient_profile(db, current_user)
    tips = (
        db.query(HealthTip)
        .filter(HealthTip.patient_id == profile.user_id)
        .order_by(HealthTip.created_at.desc())
        .limit(12)
        .all()
    )
    return [tip_to_out(tip) for tip in tips]


@router.post("/health-tips/generate", response_model=list[HealthTipOut])
@limiter.limit(AI_LIMIT)
async def generate_health_tips(
    request: Request, current_user: User = Depends(require_patient), db: Session = Depends(get_db)
):
    profile = get_patient_profile(db, current_user)
    documents = report_context(db, profile)
    medicines = patient_medicine_query(db, profile).order_by(MedicineHistory.created_at.desc()).all()
    ai_result = await generate_openai_json(
        instructions=(
            "You generate practical, safe health insights for a patient dashboard. "
            "Use only the supplied data and avoid diagnosis or medication changes. "
            "Return exactly 4 items using these categories: Food to prefer, Food to avoid, "
            "Lifestyle advice, When to consult a doctor. Each item needs category, tip_text, and based_on_data."
        ),
        prompt=patient_context_for_ai(documents, medicines),
    )
    generated = validate_ai_health_tips(ai_result.data)
    if not generated:
        generated = build_health_tips(documents, medicines)
        if generated:
            generated[0]["based_on_data"] = annotate_fallback(generated[0]["based_on_data"], ai_result.error)

    tips = [HealthTip(patient_id=profile.user_id, **tip) for tip in generated]
    db.add_all(tips)
    db.commit()
    for tip in tips:
        db.refresh(tip)
    return [tip_to_out(tip) for tip in tips]


@router.get("/doctor-summaries", response_model=list[DoctorSummaryOut])
def list_doctor_summaries(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = get_patient_profile(db, current_user)
    summaries = (
        db.query(DoctorSummary)
        .filter(DoctorSummary.patient_id == profile.user_id)
        .order_by(DoctorSummary.generated_at.desc())
        .limit(5)
        .all()
    )
    return [summary_to_out(summary) for summary in summaries]


@router.post("/doctor-summaries/generate", response_model=DoctorSummaryOut)
@limiter.limit(AI_LIMIT)
async def generate_doctor_summary(
    request: Request, current_user: User = Depends(require_patient), db: Session = Depends(get_db)
):
    profile = get_patient_profile(db, current_user)
    documents = report_context(db, profile)
    medicines = patient_medicine_query(db, profile).order_by(MedicineHistory.created_at.desc()).all()
    risks = (
        db.query(HealthRiskPrediction)
        .filter(HealthRiskPrediction.patient_id == profile.user_id)
        .order_by(HealthRiskPrediction.created_at.desc())
        .limit(5)
        .all()
    )
    ai_result = await generate_openai_text(
        instructions=(
            "You generate doctor-friendly structured patient overviews. "
            "Use only the provided patient data. Preserve report values and medicine details where available. "
            "Do not diagnose or prescribe. Include sections: Patient Overview, Key Medical Findings, "
            "Current Concerns, Medicine History, Possible Risks, Important Notes for Doctor."
        ),
        prompt=patient_context_for_ai(documents, medicines, risks),
    )
    if ai_result.text:
        # The name is added here, after generation, so it is never sent to the LLM.
        summary_text = f"Patient: {current_user.full_name}\n\n{ai_result.text}"
    else:
        summary_text = build_doctor_summary(current_user, documents, medicines, risks)
        summary_text = f"{summary_text}\n\n{fallback_notice(ai_result.error)}".strip()

    summary = DoctorSummary(patient_id=profile.user_id, summary_text=summary_text)
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary_to_out(summary)
