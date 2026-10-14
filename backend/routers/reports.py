"""Patient reports: department tiles, search/list, detail, upload, edit, re-run OCR, delete.

Helpers live in services/report_service.py. Every query is scoped to the signed-in patient.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_patient
from models import MedicalDepartment, PatientReport, User
from pagination import Page, PageParams, page_params, paginate
from rate_limit import AI_LIMIT, UPLOAD_LIMIT, limiter
from schemas import DepartmentTileOut, PatientReportOut, PatientReportUpdateRequest
from services.file_service import save_upload_file, stored_path_to_disk_path
from services.ocr_space_service import (
    DEPARTMENTS,
    OcrError,
    build_ocr_result,
    department_slug,
)
from services.report_ocr import extract_report_text
from services.report_service import (
    analyze_report_result,
    apply_ocr_result,
    create_report_ai_analysis,
    dict_field,
    ensure_medical_departments,
    get_department,
    health_status_for_department,
    highest_validation_status,
    preview_text,
    report_to_out,
    requested_department,
    risk_level_for_status,
)

router = APIRouter(prefix="/patient/reports", tags=["patient reports"])


def report_query(db: Session, current_user: User):
    return db.query(PatientReport).filter(PatientReport.patient_id == current_user.id)


@router.get("/tiles", response_model=list[DepartmentTileOut])
def department_tiles(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    ensure_medical_departments(db)
    departments = db.query(MedicalDepartment).order_by(MedicalDepartment.id.asc()).all()
    reports = report_query(db, current_user).order_by(PatientReport.upload_date.desc()).all()
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


DEPARTMENT_SLUGS = {item["slug"] for item in DEPARTMENTS}
VALIDATION_STATUSES = {"SAFE", "CAUTION", "HIGH_RISK", "NOT_VALIDATED"}
SEARCH_MAX_LENGTH = 100


def _like_pattern(text: str) -> str:
    """Case-insensitive "contains" pattern with LIKE wildcards in the user's text escaped."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("", response_model=Page[PatientReportOut])
def list_reports(
    params: PageParams = Depends(page_params),
    q: str | None = Query(
        default=None, max_length=SEARCH_MAX_LENGTH, description="Search title, file name and summary"
    ),
    department: str | None = Query(default=None, description="Department slug, e.g. heart"),
    validation_status: str | None = Query(default=None, description="SAFE, CAUTION, HIGH_RISK or NOT_VALIDATED"),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    ensure_medical_departments(db)
    query = report_query(db, current_user)

    search = (q or "").strip()
    if search:
        pattern = _like_pattern(search)
        query = query.filter(
            or_(
                PatientReport.title.ilike(pattern, escape="\\"),
                PatientReport.original_file_name.ilike(pattern, escape="\\"),
                PatientReport.summary.ilike(pattern, escape="\\"),
            )
        )
    if department:
        slug = department.strip().lower()
        if slug not in DEPARTMENT_SLUGS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown department: {department}."
            )
        query = query.filter(PatientReport.department_id == get_department(db, slug).id)
    if validation_status:
        wanted = validation_status.strip().upper()
        if wanted not in VALIDATION_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown validation status: {validation_status}.",
            )
        query = query.filter(PatientReport.validation_status == wanted)

    query = query.order_by(PatientReport.upload_date.desc(), PatientReport.id.desc())
    return paginate(query, params, report_to_out)


@router.get("/department/{department}", response_model=Page[PatientReportOut])
def reports_by_department(
    department: str,
    params: PageParams = Depends(page_params),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    department_row = get_department(db, department)
    query = (
        report_query(db, current_user)
        .filter(PatientReport.department_id == department_row.id)
        .order_by(PatientReport.upload_date.desc(), PatientReport.id.desc())
    )
    return paginate(query, params, report_to_out)


@router.get("/{report_id}", response_model=PatientReportOut)
def get_report(report_id: int, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    report = report_query(db, current_user).filter(PatientReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report_to_out(report)


@router.post("/upload", response_model=PatientReportOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(UPLOAD_LIMIT)
async def upload_report(
    request: Request,
    title: str | None = Form(default=None),
    department: str | None = Form(default=None),
    category: str | None = Form(default=None),
    extracted_text: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Store a report file and process its text. If the browser already read the text
    locally (extracted_text, e.g. tesseract.js on /dashboard), that text is processed
    instead of sending the file to OCR.space."""
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
        upload_date=datetime.now(UTC),
    )

    try:
        local_text = (extracted_text or "").strip()
        if local_text:
            ocr_result = build_ocr_result(local_text, original_name, manual_department)
            ocr_result.setdefault("structured_data_json", {})["source"] = "client_local_ocr"
        else:
            ocr_result = await extract_report_text(
                str(stored_path_to_disk_path(stored_path)),
                original_name,
                manual_department,
            )
        final_department = manual_department or str(ocr_result.get("department_name") or "General")
        report.department = get_department(db, final_department)
        analysis = await analyze_report_result(ocr_result, final_department)
        summary = str(analysis.get("summary_text") or ocr_result.get("summary") or "")
        apply_ocr_result(report, ocr_result, final_department, summary)
    except OcrError as exc:
        # Saved without text: no summary, and "not validated" (no rule ran). The reason is kept in
        # structured_data_json["error"] for the report page.
        final_department = manual_department or "General"
        report.department = get_department(db, final_department)
        report.ocr_status = "FAILED"
        report.ocr_confidence = None
        report.extracted_text = None
        report.formatted_text = None
        report.summary = None
        report.validation_status = "NOT_VALIDATED"
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
@limiter.limit(AI_LIMIT)
async def update_report(
    request: Request,
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
        # Keep the OCR rows: lines the patient changed are theirs, while numbers OCR was unsure of on
        # lines left as read are still listed to check. The OCR's own confidence is kept as it was.
        previous = dict_field(report.structured_data_json)
        if previous.get("ocr_rows"):
            ocr_result["structured_data_json"]["ocr_rows"] = previous["ocr_rows"]
        ocr_result["structured_data_json"]["text_edited_by_patient"] = True
        ocr_confidence = report.ocr_confidence
        final_department = manual_department or str(ocr_result.get("department_name") or "General")
        report.department = get_department(db, final_department)
        analysis = await analyze_report_result(ocr_result, final_department)
        summary = str(analysis.get("summary_text") or ocr_result.get("summary") or "")
        apply_ocr_result(report, ocr_result, final_department, summary)
        report.ocr_confidence = ocr_confidence
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

    report.updated_at = datetime.now(UTC)
    if payload.extracted_text is not None:
        db.add(create_report_ai_analysis(report))
    db.commit()
    db.refresh(report)
    return report_to_out(report)


@router.post("/{report_id}/regenerate-ocr", response_model=PatientReportOut)
@limiter.limit(AI_LIMIT)
async def regenerate_report_ocr(
    request: Request,
    report_id: int,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    report = report_query(db, current_user).filter(PatientReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    try:
        ocr_result = await extract_report_text(
            str(stored_path_to_disk_path(report.file_url)),
            report.original_file_name,
            report.department.name if report.department else None,
        )
    except OcrError as exc:
        # Leave the report as it was (a failed re-read must not replace good text or a summary).
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    final_department = str(
        ocr_result.get("department_name") or (report.department.name if report.department else "General")
    )
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
