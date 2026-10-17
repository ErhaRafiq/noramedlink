"""A patient's report explained in everyday words, and questions about it (the owner only).

The rules, the wording and the guards live in services/report_explainer.py. This file checks whose report it is,
reads it, and answers. A question is never stored and never logged. Every answer carries the note that it was
written by a computer program, not a doctor. Asking costs a little when an AI key is set, so it is rate limited.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_patient
from models import PatientReport, User
from rate_limit import AI_LIMIT, limiter
from schemas import AskAnswerOut, AskIn, ReportExplanationOut
from services import report_explainer
from services.icse.versions import report_entities
from services.privacy import patient_identity_patterns, redact_identifiers

router = APIRouter(prefix="/patient/reports", tags=["report-explainer"])

NO_TEXT = (
    "The app could not read this report, so there is nothing to explain yet. Open the report and check that the file is "
    "clear, or upload it again."
)


def _own_report(db: Session, patient: User, report_id: int) -> PatientReport:
    report = (
        db.query(PatientReport).filter(PatientReport.id == report_id, PatientReport.patient_id == patient.id).first()
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report


def _explanation(report: PatientReport, patient: User) -> dict:
    text = (report.formatted_text or report.extracted_text or "").strip()
    identity = patient_identity_patterns(patient)
    if not text or report.ocr_status == "FAILED":
        explanation = report_explainer.build_explanation("", [], {})
        explanation.update(readable=False, headline=NO_TEXT, suggestions=[])
        return explanation
    validation = report.validation_results or {"warnings": report.rule_warnings or []}
    return report_explainer.build_explanation(
        redact_identifiers(text, identity), report_entities(report, identity), validation
    )


@router.get("/{report_id}/explanation", response_model=ReportExplanationOut)
def report_explanation(report_id: int, patient: User = Depends(require_patient), db: Session = Depends(get_db)):
    """The report, result by result, in everyday words, with where each result sits against the usual range."""
    return _explanation(_own_report(db, patient, report_id), patient)


@router.post("/{report_id}/ask", response_model=AskAnswerOut)
@limiter.limit(AI_LIMIT)
async def ask_about_report(
    request: Request,
    report_id: int,
    payload: AskIn,
    patient: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Answers a question about this report. By fixed rules from its values; re-worded by AI only when that is safe."""
    explanation = _explanation(_own_report(db, patient, report_id), patient)
    if not explanation["readable"]:
        return AskAnswerOut(
            answer=NO_TEXT, source="rules", intent="unreadable", emergency=False, topics=[], followups=[],
            disclaimer=report_explainer.MACHINE_NOTE,
        )  # fmt: skip
    identity = patient_identity_patterns(patient)
    question = redact_identifiers(payload.question, identity)  # a name or number typed into the question stays here
    history = [{"role": t.role, "text": redact_identifiers(t.text, identity)} for t in payload.history]
    answer = await report_explainer.answer_question(question, explanation, history, payload.topic)
    return AskAnswerOut(disclaimer=report_explainer.MACHINE_NOTE, **answer)
