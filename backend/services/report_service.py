"""Patient report helpers: departments, response building and OCR/AI analysis.

Used by routers/reports.py (upload, edit, re-run OCR) and the patient dashboard.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from models import MedicalAiAnalysis, MedicalDepartment, PatientReport
from schemas import PatientReportOut
from services.file_access import file_access_url
from services.ocr_layout import uncertain_values
from services.ocr_space_service import (
    DEPARTMENTS,
    department_slug,
    normalize_department_name,
)
from services.report_ai_pipeline import run_report_ai_pipeline


def ensure_medical_departments(db: Session) -> None:
    existing = {
        department.name
        for department in db.query(MedicalDepartment).filter(
            MedicalDepartment.name.in_([item["name"] for item in DEPARTMENTS])
        )
    }
    for item in DEPARTMENTS:
        if item["name"] not in existing:
            db.add(
                MedicalDepartment(
                    name=item["name"],
                    icon=item["icon"],
                    description=item["description"],
                )
            )
    db.flush()


def get_department(db: Session, value: str | None) -> MedicalDepartment:
    ensure_medical_departments(db)
    department_name = normalize_department_name(value)
    department = db.query(MedicalDepartment).filter(MedicalDepartment.name == department_name).first()
    if not department:
        department = MedicalDepartment(name="General", icon="stethoscope", description="General medical reports.")
        db.add(department)
        db.flush()
    return department


def requested_department(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized or normalized.lower() in {"auto", "automatic", "detect"}:
        return None
    return normalize_department_name(normalized)


def preview_text(report: PatientReport, limit: int = 180) -> str | None:
    text = report.summary or report.formatted_text or report.extracted_text
    if not text:
        return None
    compact = " ".join(text.split())
    return compact[:limit].rstrip() + ("..." if len(compact) > limit else "")


def dict_field(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_field(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


# A report the rules have not checked counts as NOT_VALIDATED, never as SAFE.
VALIDATION_ORDER = {"NOT_VALIDATED": -1, "SAFE": 0, "CAUTION": 1, "HIGH_RISK": 2}


def highest_validation_status(reports: list[PatientReport]) -> str:
    status = "NOT_VALIDATED"
    for report in reports:
        report_status = report.validation_status or "NOT_VALIDATED"
        if VALIDATION_ORDER.get(report_status, -1) > VALIDATION_ORDER[status]:
            status = report_status
    return status


def risk_level_for_status(status_value: str) -> str:
    """Words only for what the rules found: no alerts is "None flagged", not "Low" (AGENTS.md 6.2)."""
    if status_value == "HIGH_RISK":
        return "High"
    if status_value == "CAUTION":
        return "Medium"
    if status_value == "SAFE":
        return "None flagged"
    return "Unknown"


def health_status_for_department(reports: list[PatientReport], status_value: str) -> str:
    if not reports:
        return "No reports"
    if status_value == "HIGH_RISK":
        return "Needs review"
    if status_value == "CAUTION":
        return "Monitor"
    if status_value == "SAFE":
        return "No rule alerts"  # never "Stable" (AGENTS.md section 7)
    return "Not validated"


def _text_was_read(report: PatientReport) -> bool:
    return report.ocr_status != "FAILED" or bool((report.extracted_text or "").strip())


def report_to_out(report: PatientReport) -> PatientReportOut:
    department_name = report.department.name if report.department else "General"
    structured_payload = dict_field(report.structured_data_json)
    fields = dict_field(structured_payload.get("fields"))
    detected_keywords = structured_payload.get("detected_keywords")
    if not isinstance(detected_keywords, list):
        detected_keywords = []

    structured_sections = {key: str(value) for key, value in fields.items() if value is not None}

    return PatientReportOut(
        id=report.id,
        patient_id=report.patient_id,
        department_id=report.department_id,
        department_name=department_name,
        department_slug=department_slug(department_name),
        category=department_slug(department_name),
        title=report.title,
        original_file_name=report.original_file_name,
        original_filename=report.original_file_name,
        file_url=report.file_url.replace("\\", "/"),
        stored_file_path=report.file_url.replace("\\", "/"),
        file_access_url=file_access_url(report.file_url, report.patient_id),
        file_type=report.file_type,
        extracted_text=report.extracted_text,
        formatted_text=report.formatted_text,
        structured_data_json=structured_payload,
        summary=report.summary if _text_was_read(report) else None,
        extracted_entities=[item for item in list_field(report.extracted_entities) if isinstance(item, dict)],
        rule_warnings=[item for item in list_field(report.rule_warnings) if isinstance(item, dict)],
        validation_status=(report.validation_status or "NOT_VALIDATED") if _text_was_read(report) else "NOT_VALIDATED",
        validation_results=dict_field(report.validation_results),
        clinical_summary_json=dict_field(report.clinical_summary_json),
        llm_self_check=dict_field(report.llm_self_check),
        summary_source=report.summary_source or "rule_based",
        upload_date=report.upload_date,
        updated_at=report.updated_at,
        ocr_status=report.ocr_status,
        ocr_confidence=report.ocr_confidence,
        ocr_raw_text=report.extracted_text,
        ocr_cleaned_text=report.formatted_text or report.extracted_text,
        possible_report_type=f"{department_name} report",
        detected_keywords=[str(keyword) for keyword in detected_keywords],
        structured_sections=structured_sections,
        ai_summary=report.summary if _text_was_read(report) else None,
        patient_summary=structured_payload.get("patient_summary"),
    )


async def analyze_report_result(ocr_result: dict[str, Any], department_name: str) -> dict[str, Any]:
    cleaned_text = str(ocr_result.get("cleaned_text") or "").strip()
    formatted_text = str(ocr_result.get("formatted_text") or "").strip()
    structured_payload = dict_field(ocr_result.get("structured_data_json"))
    # Numbers OCR was unsure of and that are still in the text as read (a line the patient has
    # corrected is theirs, not OCR's). Recomputed at every analysis, so corrections clear them.
    uncertain = uncertain_values(formatted_text or cleaned_text, structured_payload.get("ocr_rows") or [])
    structured_payload["uncertain_values"] = uncertain

    try:
        analysis = await run_report_ai_pipeline(
            cleaned_text=cleaned_text,
            formatted_text=formatted_text,
            structured_payload=structured_payload,
            department_name=department_name,
            uncertain_values=uncertain,
        )
    except Exception as exc:
        analysis = {
            "entities": [],
            "entity_metadata": {"source": "failed", "warning": str(exc), "entity_count": 0},
            "validation_results": {
                "status": "CAUTION",
                "warnings": [
                    {
                        "code": "AI_PIPELINE_FAILED",
                        "severity": "CAUTION",
                        "message": "AI analysis failed. OCR text was still saved for doctor review.",
                    }
                ],
                "confidence": 0.35,
            },
            "rule_warnings": [
                {
                    "code": "AI_PIPELINE_FAILED",
                    "severity": "CAUTION",
                    "message": "AI analysis failed. OCR text was still saved for doctor review.",
                }
            ],
            "validation_status": "CAUTION",
            "clinical_summary_json": {
                "patient_overview": "Report uploaded and OCR text saved.",
                "key_findings": ["AI analysis was unavailable."],
                "detected_diseases": [],
                "medicines": [],
                "risks_alerts": ["AI analysis was unavailable."],
                "doctor_notes": ["Verify OCR text against the uploaded report."],
                "confidence_level": "Low",
                "missing_data": ["AI analysis could not complete."],
                "summary": str(
                    ocr_result.get("summary") or "Report uploaded. Verify OCR text against the source file."
                ),
            },
            "summary_text": str(
                ocr_result.get("summary") or "Report uploaded. Verify OCR text against the source file."
            ),
            "summary_source": "rule_based",
            "summary_warning": str(exc),
            "llm_self_check": {"passed": False, "confidence_level": "Low", "notes": [str(exc)], "source": "rule_based"},
            "confidence_level": "Low",
            "patient_summary": "Your report has been uploaded and the text was extracted. AI analysis was temporarily unavailable. Please consult your doctor for proper diagnosis and treatment.",
            "patient_summary_warning": str(exc),
        }

    structured_payload["bio_bert_entities"] = analysis["entities"]
    structured_payload["entity_metadata"] = analysis["entity_metadata"]
    structured_payload["rule_validation"] = analysis["validation_results"]
    structured_payload["rule_warnings"] = analysis["rule_warnings"]
    structured_payload["ai_summary"] = analysis["clinical_summary_json"]
    structured_payload["llm_self_check"] = analysis["llm_self_check"]
    structured_payload["summary_method"] = analysis["summary_source"]
    structured_payload["confidence_level"] = analysis["confidence_level"]
    structured_payload["patient_summary"] = analysis.get("patient_summary", "")
    if analysis.get("summary_warning"):
        structured_payload["summary_warning"] = analysis["summary_warning"]
    if analysis.get("patient_summary_warning"):
        structured_payload["patient_summary_warning"] = analysis["patient_summary_warning"]
    ocr_result["structured_data_json"] = structured_payload
    ocr_result["analysis"] = analysis
    return analysis


def apply_ocr_result(
    report: PatientReport,
    ocr_result: dict[str, Any],
    department_name: str | None = None,
    summary: str | None = None,
) -> None:
    final_department_name = department_name or str(ocr_result.get("department_name") or "General")
    structured_payload = dict_field(ocr_result.get("structured_data_json"))
    analysis = dict_field(ocr_result.get("analysis"))
    structured_payload["department"] = final_department_name
    structured_payload["department_slug"] = department_slug(final_department_name)
    final_summary = (
        summary if summary is not None else str(analysis.get("summary_text") or ocr_result.get("summary") or "")
    ).strip()
    structured_payload["summary"] = final_summary

    report.extracted_text = str(ocr_result.get("cleaned_text") or "")
    report.formatted_text = str(ocr_result.get("formatted_text") or "")
    report.structured_data_json = structured_payload
    report.summary = final_summary
    report.extracted_entities = list_field(analysis.get("entities"))
    report.rule_warnings = list_field(analysis.get("rule_warnings"))
    report.validation_status = str(analysis.get("validation_status") or "SAFE")
    report.validation_results = dict_field(analysis.get("validation_results"))
    report.clinical_summary_json = dict_field(analysis.get("clinical_summary_json"))
    report.llm_self_check = dict_field(analysis.get("llm_self_check"))
    report.summary_source = str(analysis.get("summary_source") or "rule_based")
    report.ocr_confidence = ocr_result.get("confidence")
    report.ocr_status = "COMPLETED" if report.extracted_text.strip() else "NEEDS_REVIEW"
    report.updated_at = datetime.now(UTC)


def create_report_ai_analysis(report: PatientReport) -> MedicalAiAnalysis:
    return MedicalAiAnalysis(
        user_id=report.patient_id,
        patient_report_id=report.id,
        source=report.summary_source or "rule_based",
        extracted_entities=report.extracted_entities or [],
        confidence_score=report.ocr_confidence,
        rule_warnings=report.rule_warnings or [],
        validation_results={
            **dict_field(report.validation_results),
            "validation_status": report.validation_status,
            "llm_self_check": report.llm_self_check or {},
        },
        doctor_summary=report.summary,
    )
