"""The clinical summary for doctors (ICSE FE-2 and FE-4).

Only a doctor with an active access grant from the patient can read or regenerate it; any other
doctor, a patient or an admin gets 403 (the same answer whether or not the patient exists).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_doctor
from models import ClinicalSummary, User
from pagination import Page, PageParams, page_params, paginate
from rate_limit import AI_LIMIT, limiter
from schemas import (
    AI_WORDED_NOTE,
    RULE_BASED_NOTE,
    ClinicalSummaryRegenerateOut,
    ClinicalSummaryStatusOut,
    ClinicalSummaryVersionMeta,
    ClinicalSummaryVersionOut,
)
from services.dashboard_access import patient_with_active_grant
from services.icse import versions

router = APIRouter(prefix="/doctor/patients/{patient_id}/clinical-summary", tags=["clinical-summary"])


def _patient(patient_id: int, doctor: User, db: Session) -> User:
    return patient_with_active_grant(db, doctor, patient_id, area="clinical summary")


def _meta(summary: ClinicalSummary) -> dict:
    return {
        "version": summary.version,
        "generated_at": summary.generated_at,
        "trigger": summary.trigger,
        "source": summary.source,
        "is_current": summary.is_current,
    }


def _out(summary: ClinicalSummary) -> ClinicalSummaryVersionOut:
    return ClinicalSummaryVersionOut(
        **_meta(summary),
        patient_id=summary.patient_id,
        summary_text=summary.summary_text,
        content=summary.content_json or {},
        note=RULE_BASED_NOTE if summary.source == "rule_based" else AI_WORDED_NOTE,
    )


@router.get("", response_model=ClinicalSummaryStatusOut)
def get_clinical_summary(patient_id: int, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)):
    """The current version and whether it is out of date. Reading never builds a version: the page
    shows the current one (labelled out of date when it is) and asks for a regeneration."""
    patient = _patient(patient_id, doctor, db)
    state = versions.status(db, patient)
    return ClinicalSummaryStatusOut(
        patient_id=patient.id,
        summary=_out(state["summary"]) if state["summary"] else None,
        out_of_date=state["out_of_date"],
        pending_change=state["pending_change"],
    )


@router.post("/regenerate", response_model=ClinicalSummaryRegenerateOut)
@limiter.limit(AI_LIMIT)
async def regenerate_clinical_summary(
    request: Request, patient_id: int, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    patient = _patient(patient_id, doctor, db)
    summary, created = await versions.regenerate(db, patient, doctor)
    return ClinicalSummaryRegenerateOut(summary=_out(summary), created=created)


@router.get("/versions", response_model=Page[ClinicalSummaryVersionMeta])
def list_clinical_summary_versions(
    patient_id: int,
    params: PageParams = Depends(page_params),
    doctor: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    patient = _patient(patient_id, doctor, db)
    query = (
        db.query(ClinicalSummary)
        .filter(ClinicalSummary.patient_id == patient.id)
        .order_by(ClinicalSummary.version.desc())
    )
    return paginate(query, params, _meta)


@router.get("/versions/{version}", response_model=ClinicalSummaryVersionOut)
def get_clinical_summary_version(
    patient_id: int, version: int, doctor: User = Depends(require_doctor), db: Session = Depends(get_db)
):
    patient = _patient(patient_id, doctor, db)
    summary = (
        db.query(ClinicalSummary)
        .filter(ClinicalSummary.patient_id == patient.id, ClinicalSummary.version == version)
        .first()
    )
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This summary version does not exist.")
    return _out(summary)
