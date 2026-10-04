from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_patient_profile, require_patient
from models import (
    DoctorSummary,
    HealthRiskPrediction,
    HealthTip,
    MedicineHistory,
    PatientReport,
    PatientProfile,
    User,
    Vitals,
)
from routers.reports import report_to_out
from routers.auth import user_to_out
from schemas import (
    DashboardCategory,
    DoctorSummaryOut,
    HealthRiskPredictionOut,
    HealthTipOut,
    MedicineHistoryCreate,
    MedicineHistoryOut,
    MedicineHistoryUpdate,
    MedicineSafetyCheckRequest,
    MedicineSafetyCheckResponse,
    PatientDashboardOut,
    VitalsOut,
)
from services.nlp_service import DISCLAIMER
from services.openai_service import fallback_notice, generate_openai_json, generate_openai_text


router = APIRouter(prefix="/patient", tags=["patient"])


VALID_CATEGORIES = {
    "cardiology",
    "nephrology",
    "orthopedics",
    "neurology",
    "pulmonology",
    "general-medicine",
    "dermatology",
    "gastroenterology",
    "endocrinology",
}

TIP_CATEGORIES = [
    "Food to prefer",
    "Food to avoid",
    "Lifestyle advice",
    "When to consult a doctor",
]


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


def report_context(db: Session, profile: PatientProfile) -> list[SimpleNamespace]:
    """The patient's reports (newest first) for the risk, tips and doctor-summary generators,
    with the attribute names those helpers use. patient_reports is the single report table."""
    reports = (
        db.query(PatientReport)
        .filter(PatientReport.patient_id == profile.user_id)
        .order_by(PatientReport.upload_date.desc())
        .all()
    )
    rows = []
    for report in reports:
        department = report.department.name if report.department else "General"
        rows.append(
            SimpleNamespace(
                title=report.title,
                category=department,
                notes=report.notes,
                ocr_cleaned_text=report.formatted_text or report.extracted_text,
                ai_summary=report.summary,
                possible_report_type=f"{department} report",
            )
        )
    return rows


def patient_medicine_query(db: Session, profile: PatientProfile):
    return db.query(MedicineHistory).filter(MedicineHistory.patient_id == profile.user_id)


def collect_patient_context(documents: list[SimpleNamespace], medicines: list[MedicineHistory]) -> str:
    report_text = "\n".join(
        " ".join(
            value
            for value in [
                document.title,
                document.category,
                document.notes or "",
                document.ocr_cleaned_text or "",
                document.ai_summary or "",
            ]
            if value
        )
        for document in documents
    )
    medicine_text = "\n".join(
        f"{medicine.medicine_name} {medicine.dosage} {medicine.frequency} {medicine.reason} {medicine.side_effects or ''}"
        for medicine in medicines
    )
    return f"{report_text}\n{medicine_text}".lower()


def context_has(context: str, terms: list[str]) -> bool:
    return any(term in context for term in terms)


def build_risk_predictions(profile: PatientProfile, documents: list[SimpleNamespace], medicines: list[MedicineHistory]):
    context = collect_patient_context(documents, medicines)
    predictions: list[dict[str, str]] = []

    if context_has(context, ["hba1c", "glucose", "blood sugar", "diabetes", "metformin", "insulin"]):
        predictions.append(
            {
                "risk_title": "Possible blood sugar control risk",
                "risk_level": "Medium" if "high" not in context and "elevated" not in context else "High",
                "reason": "Saved reports or medicine history mention blood sugar, HbA1c, diabetes, insulin, or glucose-related data.",
                "recommendation": "Track sugar readings, keep meals consistent, and discuss the latest report with a qualified doctor.",
            }
        )

    if context_has(context, ["creatinine", "urea", "kidney", "renal", "egfr"]):
        predictions.append(
            {
                "risk_title": "Possible kidney function follow-up risk",
                "risk_level": "High" if context_has(context, ["high creatinine", "low egfr", "abnormal"]) else "Medium",
                "reason": "Kidney-related terms were found in uploaded reports or summaries.",
                "recommendation": "Review hydration, avoid self-medicating painkillers, and consult a doctor for kidney function interpretation.",
            }
        )

    if context_has(context, ["cholesterol", "ldl", "hdl", "triglyceride", "lipid", "blood pressure", "hypertension"]):
        predictions.append(
            {
                "risk_title": "Possible heart health monitoring risk",
                "risk_level": "Medium",
                "reason": "Reports mention lipid, cholesterol, triglyceride, or blood pressure-related information.",
                "recommendation": "Maintain follow-up for BP and lipid readings, and ask a doctor whether further evaluation is needed.",
            }
        )

    if context_has(context, ["side effect", "rash", "swelling", "allergy", "breathing", "dizziness"]):
        predictions.append(
            {
                "risk_title": "Possible medicine reaction risk",
                "risk_level": "Medium",
                "reason": "Medicine history includes side-effect or allergy-like language.",
                "recommendation": "Do not restart suspected medicines without professional guidance. Share this history with the doctor.",
            }
        )

    if not predictions:
        predictions.append(
            {
                "risk_title": "No strong future risk signal detected",
                "risk_level": "Low",
                "reason": "The saved reports and medicine history do not show a clear risk pattern from available readable text.",
                "recommendation": "Keep reports updated and consult a doctor if symptoms persist, worsen, or feel unusual.",
            }
        )

    return predictions[:3]


def build_health_tips(documents: list[SimpleNamespace], medicines: list[MedicineHistory]):
    context = collect_patient_context(documents, medicines)
    base = "Based on saved reports, OCR text, and medicine history."
    sugar = context_has(context, ["hba1c", "glucose", "blood sugar", "diabetes", "metformin", "insulin"])
    kidney = context_has(context, ["creatinine", "urea", "kidney", "renal", "egfr"])
    heart = context_has(context, ["cholesterol", "ldl", "triglyceride", "lipid", "blood pressure", "hypertension"])

    if sugar:
        prefer = "Prefer fiber-rich meals, vegetables, lentils, whole grains in moderate portions, and unsweetened drinks."
        avoid = "Limit sugary drinks, desserts, large refined-carb portions, and frequent fried snacks."
    elif kidney:
        prefer = "Prefer balanced home-cooked meals, doctor-approved fluids, and fresh foods with moderate salt."
        avoid = "Avoid excess salt, self-prescribed painkillers, and high-protein dieting unless a clinician recommends it."
    elif heart:
        prefer = "Prefer vegetables, fruits, oats, lentils, nuts in small portions, and lean proteins."
        avoid = "Limit deep-fried foods, high-salt packaged meals, trans fats, and sugary drinks."
    else:
        prefer = "Prefer simple balanced meals with vegetables, fruits, whole grains, proteins, and enough water."
        avoid = "Avoid excessive sugar, very salty packaged foods, smoking, and self-medication."

    lifestyle = "Keep regular sleep, light activity if safe, medicine timing consistency, and a simple symptom log."
    consult = "Consult a doctor urgently for chest pain, breathing difficulty, fainting, severe weakness, allergic swelling, or worsening symptoms."

    return [
        {"category": TIP_CATEGORIES[0], "tip_text": prefer, "based_on_data": base},
        {"category": TIP_CATEGORIES[1], "tip_text": avoid, "based_on_data": base},
        {"category": TIP_CATEGORIES[2], "tip_text": lifestyle, "based_on_data": base},
        {"category": TIP_CATEGORIES[3], "tip_text": consult, "based_on_data": base},
    ]


def build_doctor_summary(current_user: User, documents: list[SimpleNamespace], medicines: list[MedicineHistory], risks: list[HealthRiskPrediction]):
    latest_reports = documents[:5]
    report_findings = [
        f"- {document.title}: {document.possible_report_type or 'Medical report'}; summary: {document.ai_summary or 'No AI summary yet'}"
        for document in latest_reports
    ] or ["- No uploaded reports yet."]
    medicine_lines = [
        f"- {medicine.medicine_name}, {medicine.dosage}, {medicine.frequency}, reason: {medicine.reason}"
        for medicine in medicines[:8]
    ] or ["- No medicine history saved yet."]
    risk_lines = [
        f"- {risk.risk_title} ({risk.risk_level}): {risk.reason}"
        for risk in risks[:5]
    ] or ["- No generated risk predictions yet."]
    concern_lines = [
        f"- {document.notes}"
        for document in latest_reports
        if document.notes
    ] or ["- No separate symptom notes saved with reports."]

    return "\n".join(
        [
            "Patient Overview",
            f"- Name: {current_user.full_name}",
            f"- Phone: {current_user.phone}",
            "",
            "Key Medical Findings",
            *report_findings,
            "",
            "Current Concerns",
            *concern_lines,
            "",
            "Medicine History",
            *medicine_lines,
            "",
            "Possible Risks",
            *risk_lines,
            "",
            "Important Notes for Doctor",
            "- OCR text may contain scanning errors and should be verified against original reports.",
            f"- {DISCLAIMER}",
        ]
    )


def normalized_medicine_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def check_medicine_safety(medicine_name: str, dosage: str | None, known_allergies: str | None, medicines: list[MedicineHistory]):
    requested = normalized_medicine_name(medicine_name)
    allergy_text = (known_allergies or "").lower()
    warnings: list[str] = []
    status_label = "Safe"

    if requested and requested in allergy_text:
        warnings.append("The requested medicine appears in the known allergy text.")
        status_label = "High Risk"

    for medicine in medicines:
        existing = normalized_medicine_name(medicine.medicine_name)
        side_effects = (medicine.side_effects or "").lower()
        if existing == requested:
            warnings.append(f"Duplicate medicine history found: {medicine.medicine_name}.")
            status_label = "Caution" if status_label != "High Risk" else status_label
        if requested and requested in side_effects and any(term in side_effects for term in ["allergy", "rash", "swelling", "breathing"]):
            warnings.append(f"Possible allergy or reaction noted previously for {medicine.medicine_name}.")
            status_label = "High Risk"

    active_names = {normalized_medicine_name(medicine.medicine_name) for medicine in medicines}
    requested_set = active_names | {requested}
    high_risk_pairs = [
        ({"warfarin", "aspirin"}, "Warfarin with aspirin can increase bleeding risk."),
        ({"warfarin", "ibuprofen"}, "Warfarin with ibuprofen can increase bleeding risk."),
        ({"nitrate", "sildenafil"}, "Nitrates with sildenafil can cause dangerous blood pressure drops."),
    ]
    caution_pairs = [
        ({"aspirin", "ibuprofen"}, "Aspirin with ibuprofen may increase stomach or bleeding risk."),
        ({"insulin", "glimepiride"}, "Insulin with sulfonylurea medicines can increase low sugar risk."),
        ({"metformin", "contrast"}, "Metformin needs doctor review around some contrast imaging procedures."),
    ]

    for pair, reason in high_risk_pairs:
        if pair.issubset(requested_set):
            warnings.append(reason)
            status_label = "High Risk"

    for pair, reason in caution_pairs:
        if pair.issubset(requested_set):
            warnings.append(reason)
            status_label = "Caution" if status_label != "High Risk" else status_label

    if dosage and any(term in dosage.lower() for term in ["double", "extra", "repeat"]):
        warnings.append("Dosage wording suggests repeated or extra dosing and should be clarified.")
        status_label = "Caution" if status_label != "High Risk" else status_label

    if not warnings:
        warnings.append("No duplicate, allergy, or common interaction warning was found in saved medicine history.")

    reason = " ".join(warnings)
    return status_label, reason, warnings


def patient_context_for_ai(
    current_user: User,
    documents: list[SimpleNamespace],
    medicines: list[MedicineHistory],
    risks: list[HealthRiskPrediction] | None = None,
) -> str:
    report_lines = [
        "\n".join(
            [
                f"Report title: {document.title}",
                f"Category: {document.category}",
                f"Notes: {document.notes or 'none'}",
                f"Report type: {document.possible_report_type or 'unknown'}",
                f"Existing summary: {document.ai_summary or 'none'}",
                f"OCR text: {(document.ocr_cleaned_text or '')[:1600]}",
            ]
        )
        for document in documents[:8]
    ]
    medicine_lines = [
        f"{medicine.medicine_name}; dosage {medicine.dosage}; frequency {medicine.frequency}; "
        f"reason {medicine.reason}; side effects {medicine.side_effects or 'none'}"
        for medicine in medicines[:12]
    ]
    risk_lines = [
        f"{risk.risk_title} ({risk.risk_level}): {risk.reason}. Recommendation: {risk.recommendation}"
        for risk in (risks or [])[:8]
    ]

    return "\n\n".join(
        [
            f"Patient: {current_user.full_name}",
            f"Phone: {current_user.phone or 'not provided'}",
            "Reports:",
            "\n\n".join(report_lines) or "No uploaded reports.",
            "Medicine history:",
            "\n".join(medicine_lines) or "No medicine history.",
            "Existing risk observations:",
            "\n".join(risk_lines) or "No generated risk observations.",
        ]
    )[:14000]


def annotate_fallback(value: str, warning: str | None) -> str:
    notice = fallback_notice(warning)
    return f"{value} {notice}" if notice else value


def clean_ai_text(value: object, fallback: str, max_length: int = 600) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()[:max_length]
    return fallback


def normalize_risk_level(value: object) -> str:
    if isinstance(value, str) and value.strip().lower() in {"low", "medium", "high"}:
        return value.strip().title()
    return "Medium"


def normalize_safety_status(value: object) -> str:
    if isinstance(value, str) and value.strip().lower() in {"safe", "caution", "high risk"}:
        return value.strip().title()
    return "Caution"


def highest_safety_status(first: str, second: str) -> str:
    severity = {"Safe": 0, "Caution": 1, "High Risk": 2}
    return first if severity.get(first, 1) >= severity.get(second, 1) else second


def validate_ai_risk_predictions(data: object) -> list[dict[str, str]]:
    if not isinstance(data, list):
        return []

    predictions: list[dict[str, str]] = []
    for item in data[:3]:
        if not isinstance(item, dict):
            continue
        predictions.append(
            {
                "risk_title": clean_ai_text(item.get("risk_title"), "Clinical follow-up observation", 180),
                "risk_level": normalize_risk_level(item.get("risk_level")),
                "reason": clean_ai_text(item.get("reason"), "OpenAI identified a follow-up observation from saved patient data."),
                "recommendation": clean_ai_text(
                    item.get("recommendation"),
                    "Review the observation with a qualified doctor before making care decisions.",
                ),
            }
        )
    return predictions


def validate_ai_health_tips(data: object) -> list[dict[str, str]]:
    if not isinstance(data, list):
        return []

    allowed_categories = set(TIP_CATEGORIES)
    tips: list[dict[str, str]] = []
    for item in data[:4]:
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        category_text = category if isinstance(category, str) and category in allowed_categories else TIP_CATEGORIES[min(len(tips), 3)]
        tips.append(
            {
                "category": category_text,
                "tip_text": clean_ai_text(item.get("tip_text"), "Keep reports updated and discuss changes with a doctor."),
                "based_on_data": clean_ai_text(item.get("based_on_data"), "Based on saved reports and medicine history.", 320),
            }
        )
    return tips


@router.get("/dashboard", response_model=PatientDashboardOut)
def dashboard(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = get_patient_profile(db, current_user)
    reports = (
        db.query(PatientReport)
        .filter(PatientReport.patient_id == profile.user_id)
        .order_by(PatientReport.upload_date.desc())
        .all()
    )
    category_rows = (
        db.query(
            PatientReport.department_id,
            func.count(PatientReport.id),
            func.max(PatientReport.upload_date),
        )
        .filter(PatientReport.patient_id == profile.user_id)
        .group_by(PatientReport.department_id)
        .all()
    )
    latest_risk = (
        db.query(HealthRiskPrediction)
        .filter(HealthRiskPrediction.patient_id == profile.user_id)
        .order_by(HealthRiskPrediction.created_at.desc())
        .first()
    )
    latest_summary = (
        db.query(DoctorSummary)
        .filter(DoctorSummary.patient_id == profile.user_id)
        .order_by(DoctorSummary.generated_at.desc())
        .first()
    )

    categories = []
    for department_id, count, last_updated in category_rows:
        department_name = "General"
        if department_id:
            matching_report = next((report for report in reports if report.department_id == department_id and report.department), None)
            if matching_report and matching_report.department:
                department_name = matching_report.department.name
        categories.append(DashboardCategory(category=department_name, document_count=count, last_updated=last_updated))

    return PatientDashboardOut(
        patient=user_to_out(current_user),
        total_reports=len(reports),
        categories_used=len(categories),
        latest_upload=report_to_out(reports[0]) if reports else None,
        ocr_processed_reports=sum(1 for report in reports if report.ocr_status in {"COMPLETED", "REVIEWED"}),
        ai_summaries_generated=sum(1 for report in reports if bool(report.summary)),
        categories=categories,
        recent_documents=[report_to_out(report) for report in reports[:5]],
        medicine_count=patient_medicine_query(db, profile).count(),
        latest_risk_prediction=risk_to_out(latest_risk) if latest_risk else None,
        latest_doctor_summary=summary_to_out(latest_summary) if latest_summary else None,
    )


@router.get("/vitals/latest", response_model=VitalsOut | None)
def latest_vitals(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = get_patient_profile(db, current_user)
    vital = (
        db.query(Vitals)
        .filter(Vitals.user_id == profile.user_id)
        .order_by(Vitals.created_at.desc())
        .first()
    )
    if not vital:
        return None
    return VitalsOut(
        id=vital.id,
        user_id=vital.user_id,
        blood_pressure=vital.blood_pressure,
        sugar_level=vital.sugar_level,
        created_at=vital.created_at,
    )


@router.get("/medicines", response_model=list[MedicineHistoryOut])
def list_medicines(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = get_patient_profile(db, current_user)
    medicines = patient_medicine_query(db, profile).order_by(MedicineHistory.created_at.desc()).all()
    return [medicine_to_out(medicine) for medicine in medicines]


@router.post("/medicines", response_model=MedicineHistoryOut, status_code=status.HTTP_201_CREATED)
def create_medicine(payload: MedicineHistoryCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
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
async def generate_risk_predictions(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = get_patient_profile(db, current_user)
    documents = report_context(db, profile)
    medicines = patient_medicine_query(db, profile).order_by(MedicineHistory.created_at.desc()).all()
    ai_result = await generate_openai_json(
        instructions=(
            "You generate cautious clinical risk observations for a patient dashboard. "
            "Use only the supplied reports and medicine history. Do not diagnose. "
            "Return up to 3 items with risk_title, risk_level (Low, Medium, High), reason, and recommendation."
        ),
        prompt=patient_context_for_ai(current_user, documents, medicines),
    )
    generated = validate_ai_risk_predictions(ai_result.data)
    if not generated:
        generated = build_risk_predictions(profile, documents, medicines)
        if generated:
            generated[0]["reason"] = annotate_fallback(generated[0]["reason"], ai_result.error)

    predictions = [
        HealthRiskPrediction(patient_id=profile.user_id, **prediction)
        for prediction in generated
    ]
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
async def generate_health_tips(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
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
        prompt=patient_context_for_ai(current_user, documents, medicines),
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
async def generate_doctor_summary(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
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
        prompt=patient_context_for_ai(current_user, documents, medicines, risks),
    )
    summary_text = ai_result.text or build_doctor_summary(current_user, documents, medicines, risks)
    if not ai_result.text:
        summary_text = f"{summary_text}\n\n{fallback_notice(ai_result.error)}".strip()

    summary = DoctorSummary(patient_id=profile.user_id, summary_text=summary_text)
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary_to_out(summary)


@router.post("/medicine-safety/check", response_model=MedicineSafetyCheckResponse)
async def medicine_safety_check(
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
            "You generate medicine safety observations for a patient dashboard. "
            "Use only the supplied medicine history and allergy text. Do not prescribe, change dosage, "
            "or say a medicine is definitely safe. Return JSON with status (Safe, Caution, High Risk), "
            "reason, and warnings array."
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
                ) or "No saved medicine history.",
            ]
        ),
    )

    if isinstance(ai_result.data, dict):
        ai_status = normalize_safety_status(ai_result.data.get("status"))
        ai_reason = clean_ai_text(ai_result.data.get("reason"), "", 800)
        ai_warnings = ai_result.data.get("warnings")
        if isinstance(ai_warnings, list):
            warnings.extend(str(warning).strip() for warning in ai_warnings if str(warning).strip())
        if ai_reason:
            reason = f"{reason} OpenAI observation: {ai_reason}"
        status_label = highest_safety_status(status_label, ai_status)
    else:
        warnings.append(fallback_notice(ai_result.error))
        reason = annotate_fallback(reason, ai_result.error)

    warnings = list(dict.fromkeys(warning for warning in warnings if warning))
    return MedicineSafetyCheckResponse(status=status_label, reason=reason, warnings=warnings)
