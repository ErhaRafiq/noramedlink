from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, require_patient
from models import PatientReport, User
from rate_limit import AI_LIMIT, limiter
from schemas import SummarizeRequest, SummaryResponse
from services.nlp_service import summarize_with_optional_llm
from services.privacy import patient_identity_patterns
from services.report_breakdown import build_breakdown

router = APIRouter(prefix="/nlp", tags=["nlp"])

MIN_TEXT = 20
MAX_TEXT = 20000
# Placeholder the old Next scan route stored when no OCR provider was configured.
UNUSABLE_TEXT = "AI scanning is not configured yet. Add a backend OCR provider to enable automatic text extraction."


def _check_length(text: str) -> str:
    text = text.strip()
    if len(text) < MIN_TEXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Enter at least 20 characters of medical report text."
        )
    if len(text) > MAX_TEXT:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Medical report text must be 20,000 characters or less.",
        )
    return text


@router.post("/summarize", response_model=SummaryResponse)
@limiter.limit(AI_LIMIT)
async def summarize(request: Request, payload: SummarizeRequest, current_user: User = Depends(get_current_user)):
    """Summarize pasted report text. Requires a signed-in user (it was public before)."""
    text = _check_length(payload.text)
    summary, method, warning = await summarize_with_optional_llm(
        text, payload.category, patient_identity_patterns(current_user)
    )
    return SummaryResponse(summary=summary, method=method, warning=warning, **build_breakdown(text))


@router.post("/summarize/saved-reports", response_model=SummaryResponse)
@limiter.limit(AI_LIMIT)
async def summarize_saved_reports(
    request: Request, current_user: User = Depends(require_patient), db: Session = Depends(get_db)
):
    """Summarize the signed-in patient's own saved reports (former Next saved-report mode)."""
    reports = (
        db.query(PatientReport)
        .filter(PatientReport.patient_id == current_user.id)
        .order_by(PatientReport.upload_date.desc())
        .all()
    )
    sections = []
    for report in reports:
        body = (report.formatted_text or report.extracted_text or "").strip()
        if not body or UNUSABLE_TEXT in body:
            continue
        sections.append(
            "\n".join(
                [
                    f"Report: {report.title}",
                    f"File: {report.original_file_name}",
                    f"Uploaded: {report.upload_date.isoformat()}",
                    body,
                ]
            )
        )
    combined = "\n\n".join(sections)
    if len(combined) < MIN_TEXT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No readable saved report text found for this patient yet."
        )
    text = combined[:MAX_TEXT]
    summary, method, warning = await summarize_with_optional_llm(
        text, "medical-report", patient_identity_patterns(current_user)
    )
    return SummaryResponse(summary=summary, method=method, warning=warning, **build_breakdown(text))
