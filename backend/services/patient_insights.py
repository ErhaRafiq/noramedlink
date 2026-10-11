"""Patient insights: risk observations, health tips and the doctor summary.

The rule-based builders are the fallback when no LLM is configured or its output is
unusable; the validators clean LLM JSON before it is stored.
"""

from types import SimpleNamespace

from sqlalchemy.orm import Session

from models import HealthRiskPrediction, MedicineHistory, PatientProfile, PatientReport, User
from services.nlp_service import DISCLAIMER
from services.openai_service import fallback_notice

TIP_CATEGORIES = [
    "Food to prefer",
    "Food to avoid",
    "Lifestyle advice",
    "When to consult a doctor",
]


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
        prefer = (
            "Prefer fiber-rich meals, vegetables, lentils, whole grains in moderate portions, and unsweetened drinks."
        )
        avoid = "Limit sugary drinks, desserts, large refined-carb portions, and frequent fried snacks."
    elif kidney:
        prefer = "Prefer balanced home-cooked meals, doctor-approved fluids, and fresh foods with moderate salt."
        avoid = (
            "Avoid excess salt, self-prescribed painkillers, and high-protein dieting unless a clinician recommends it."
        )
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


def build_doctor_summary(
    current_user: User,
    documents: list[SimpleNamespace],
    medicines: list[MedicineHistory],
    risks: list[HealthRiskPrediction],
):
    latest_reports = documents[:5]
    report_findings = [
        f"- {document.title}: {document.possible_report_type or 'Medical report'}; summary: {document.ai_summary or 'No AI summary yet'}"
        for document in latest_reports
    ] or ["- No uploaded reports yet."]
    medicine_lines = [
        f"- {medicine.medicine_name}, {medicine.dosage}, {medicine.frequency}, reason: {medicine.reason}"
        for medicine in medicines[:8]
    ] or ["- No medicine history saved yet."]
    risk_lines = [f"- {risk.risk_title} ({risk.risk_level}): {risk.reason}" for risk in risks[:5]] or [
        "- No generated risk predictions yet."
    ]
    concern_lines = [f"- {document.notes}" for document in latest_reports if document.notes] or [
        "- No separate symptom notes saved with reports."
    ]

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


def patient_context_for_ai(
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

    # No name, phone or other identifiers: the LLM does not need them (privacy).
    return "\n\n".join(
        [
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
                "reason": clean_ai_text(
                    item.get("reason"), "OpenAI identified a follow-up observation from saved patient data."
                ),
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
        category_text = (
            category
            if isinstance(category, str) and category in allowed_categories
            else TIP_CATEGORIES[min(len(tips), 3)]
        )
        tips.append(
            {
                "category": category_text,
                "tip_text": clean_ai_text(
                    item.get("tip_text"), "Keep reports updated and discuss changes with a doctor."
                ),
                "based_on_data": clean_ai_text(
                    item.get("based_on_data"), "Based on saved reports and medicine history.", 320
                ),
            }
        )
    return tips
