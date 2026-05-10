from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_patient
from models import MedicalAiAnalysis, MedicalDepartment, PatientReport, User
from schemas import DepartmentTileOut, PatientReportOut, PatientReportUpdateRequest
from services.file_service import save_upload_file, stored_path_to_disk_path
from services.ocr_space_service import (
    DEPARTMENTS,
    OcrSpaceError,
    build_ocr_result,
    department_slug,
    extract_report_with_ocr_space,
    normalize_department_name,
)
from services.report_ai_pipeline import run_report_ai_pipeline


router = APIRouter(prefix="/patient/reports", tags=["patient reports"])


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


def report_query(db: Session, current_user: User):
    return db.query(PatientReport).filter(PatientReport.patient_id == current_user.id)


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


def highest_validation_status(reports: list[PatientReport]) -> str:
    order = {"SAFE": 0, "CAUTION": 1, "HIGH_RISK": 2}
    status = "SAFE"
    for report in reports:
        report_status = report.validation_status or "SAFE"
        if order.get(report_status, 0) > order.get(status, 0):
            status = report_status
    return status


def risk_level_for_status(status_value: str) -> str:
    if status_value == "HIGH_RISK":
        return "High"
    if status_value == "CAUTION":
        return "Medium"
    return "Low"


def health_status_for_department(reports: list[PatientReport], status_value: str) -> str:
    if not reports:
        return "No reports"
    if status_value == "HIGH_RISK":
        return "Needs review"
    if status_value == "CAUTION":
        return "Monitor"
    return "Stable"


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
        file_type=report.file_type,
        extracted_text=report.extracted_text,
        formatted_text=report.formatted_text,
        structured_data_json=structured_payload,
        summary=report.summary,
        extracted_entities=[item for item in list_field(report.extracted_entities) if isinstance(item, dict)],
        rule_warnings=[item for item in list_field(report.rule_warnings) if isinstance(item, dict)],
        validation_status=report.validation_status or "SAFE",
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
        ai_summary=report.summary,
        patient_summary=structured_payload.get("patient_summary"),
    )


async def analyze_report_result(ocr_result: dict[str, Any], department_name: str) -> dict[str, Any]:
    cleaned_text = str(ocr_result.get("cleaned_text") or "").strip()
    formatted_text = str(ocr_result.get("formatted_text") or "").strip()
    structured_payload = dict_field(ocr_result.get("structured_data_json"))

    try:
        analysis = await run_report_ai_pipeline(
            cleaned_text=cleaned_text,
            formatted_text=formatted_text,
            structured_payload=structured_payload,
            department_name=department_name,
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
                "summary": str(ocr_result.get("summary") or "Report uploaded. Verify OCR text against the source file."),
            },
            "summary_text": str(ocr_result.get("summary") or "Report uploaded. Verify OCR text against the source file."),
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
    final_summary = (summary if summary is not None else str(analysis.get("summary_text") or ocr_result.get("summary") or "")).strip()
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
    report.updated_at = datetime.now(timezone.utc)


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


@router.get("/tiles", response_model=list[DepartmentTileOut])
def department_tiles(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    ensure_medical_departments(db)
    departments = db.query(MedicalDepartment).order_by(MedicalDepartment.id.asc()).all()
    reports = (
        report_query(db, current_user)
        .order_by(PatientReport.upload_date.desc())
        .all()
    )
    reports_by_department: dict[int, list[PatientReport]] = {}
    for report in reports:
        if report.department_id is not None:
            reports_by_department.setdefault(report.department_id, []).append(report)

    tiles: list[DepartmentTileOut] = []
    for department in departments:
        department_reports = reports_by_department.get(department.id, [])
        validation_status = highest_validation_status(department_reports)
        tiles.append(
            DepartmentTileOut(
                id=department.id,
                name=department.name,
                slug=department_slug(department.name),
                icon=department.icon,
                description=department.description,
                total_reports=len(department_reports),
                latest_upload_date=department_reports[0].upload_date if department_reports else None,
                preview_text=preview_text(department_reports[0]) if department_reports else None,
                health_status=health_status_for_department(department_reports, validation_status),
                risk_level=risk_level_for_status(validation_status),
                validation_status=validation_status,
            )
        )
    return tiles


@router.get("", response_model=list[PatientReportOut])
def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    ensure_medical_departments(db)
    reports = (
        report_query(db, current_user)
        .order_by(PatientReport.upload_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [report_to_out(report) for report in reports]


@router.get("/department/{department}", response_model=list[PatientReportOut])
def reports_by_department(
    department: str,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    department_row = get_department(db, department)
    reports = (
        report_query(db, current_user)
        .filter(PatientReport.department_id == department_row.id)
        .order_by(PatientReport.upload_date.desc())
        .all()
    )
    return [report_to_out(report) for report in reports]


@router.get("/{report_id}", response_model=PatientReportOut)
def get_report(report_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    report = report_query(db, current_user).filter(PatientReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report_to_out(report)


@router.post("/upload", response_model=PatientReportOut, status_code=status.HTTP_201_CREATED)
async def upload_report(
    title: str | None = Form(default=None),
    department: str | None = Form(default=None),
    category: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    manual_department = requested_department(department or category)
    storage_department = department_slug(manual_department or "general")
    stored_path, file_type = await save_upload_file(file, storage_department, patient_id=current_user.id)
    original_name = file.filename or "uploaded-report"
    safe_title = ((title or "").strip() or original_name.rsplit(".", 1)[0] or "Medical report")[:180]

    report = PatientReport(
        patient_id=current_user.id,
        title=safe_title,
        original_file_name=original_name,
        file_url=stored_path,
        file_type=file_type,
        ocr_status="PENDING",
        upload_date=datetime.now(timezone.utc),
    )

    try:
        ocr_result = await extract_report_with_ocr_space(
            str(stored_path_to_disk_path(stored_path)),
            original_name,
            manual_department,
        )
        final_department = manual_department or str(ocr_result.get("department_name") or "General")
        report.department = get_department(db, final_department)
        analysis = await analyze_report_result(ocr_result, final_department)
        summary = str(analysis.get("summary_text") or ocr_result.get("summary") or "")
        apply_ocr_result(report, ocr_result, final_department, summary)
    except OcrSpaceError as exc:
        final_department = manual_department or "General"
        report.department = get_department(db, final_department)
        report.ocr_status = "FAILED"
        report.ocr_confidence = None
        report.extracted_text = None
        report.formatted_text = None
        report.summary = str(exc)
        report.structured_data_json = {
            "fields": {},
            "department": final_department,
            "department_slug": department_slug(final_department),
            "detected_keywords": [],
            "source": "ocr_space",
            "error": str(exc),
        }

    db.add(report)
    db.flush()
    if report.ocr_status != "FAILED":
        db.add(create_report_ai_analysis(report))
    db.commit()
    db.refresh(report)
    return report_to_out(report)


@router.patch("/{report_id}", response_model=PatientReportOut)
async def update_report(
    report_id: int,
    payload: PatientReportUpdateRequest,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    report = report_query(db, current_user).filter(PatientReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    manual_department = requested_department(payload.department)
    if payload.title is not None:
        report.title = payload.title.strip()

    if payload.extracted_text is not None:
        ocr_result = build_ocr_result(
            payload.extracted_text,
            report.original_file_name,
            manual_department or (report.department.name if report.department else None),
        )
        final_department = manual_department or str(ocr_result.get("department_name") or "General")
        report.department = get_department(db, final_department)
        analysis = await analyze_report_result(ocr_result, final_department)
        summary = str(analysis.get("summary_text") or ocr_result.get("summary") or "")
        apply_ocr_result(report, ocr_result, final_department, summary)
        report.ocr_confidence = 0.9
        report.ocr_status = "REVIEWED"
    elif manual_department:
        report.department = get_department(db, manual_department)
        structured_payload = dict_field(report.structured_data_json)
        structured_payload["department"] = manual_department
        structured_payload["department_slug"] = department_slug(manual_department)
        report.structured_data_json = structured_payload

    if payload.formatted_text is not None:
        report.formatted_text = payload.formatted_text.strip()
        report.ocr_status = "REVIEWED"

    if payload.structured_data_json is not None:
        report.structured_data_json = payload.structured_data_json

    report.updated_at = datetime.now(timezone.utc)
    if payload.extracted_text is not None:
        db.add(create_report_ai_analysis(report))
    db.commit()
    db.refresh(report)
    return report_to_out(report)


@router.post("/{report_id}/regenerate-ocr", response_model=PatientReportOut)
async def regenerate_report_ocr(
    report_id: int,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    report = report_query(db, current_user).filter(PatientReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    try:
        ocr_result = await extract_report_with_ocr_space(
            str(stored_path_to_disk_path(report.file_url)),
            report.original_file_name,
            report.department.name if report.department else None,
        )
    except OcrSpaceError as exc:
        report.ocr_status = "FAILED"
        report.summary = str(exc)
        report.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(report)
        return report_to_out(report)

    final_department = str(ocr_result.get("department_name") or (report.department.name if report.department else "General"))
    report.department = get_department(db, final_department)
    analysis = await analyze_report_result(ocr_result, final_department)
    summary = str(analysis.get("summary_text") or ocr_result.get("summary") or "")
    apply_ocr_result(report, ocr_result, final_department, summary)
    db.add(create_report_ai_analysis(report))
    db.commit()
    db.refresh(report)
    return report_to_out(report)


@router.delete("/{report_id}")
def delete_report(report_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    report = report_query(db, current_user).filter(PatientReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    db.delete(report)
    db.commit()
    return {"message": "Report deleted successfully."}
