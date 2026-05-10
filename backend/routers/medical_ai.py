from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import MedicalAiAnalysis, User
from schemas import MedicalAiAnalysisOut


router = APIRouter(prefix="/medical-ai-analyses", tags=["medical-ai-analyses"])


def analysis_to_out(analysis: MedicalAiAnalysis) -> MedicalAiAnalysisOut:
    return MedicalAiAnalysisOut(
        id=analysis.id,
        user_id=analysis.user_id,
        medical_record_id=analysis.medical_record_id,
        patient_report_id=analysis.patient_report_id,
        source=analysis.source,
        extracted_entities=analysis.extracted_entities or [],
        confidence_score=analysis.confidence_score,
        rule_warnings=analysis.rule_warnings or [],
        validation_results=analysis.validation_results or {},
        doctor_summary=analysis.doctor_summary,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


@router.get("", response_model=list[MedicalAiAnalysisOut])
def list_medical_ai_analyses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    analyses = (
        db.query(MedicalAiAnalysis)
        .filter(MedicalAiAnalysis.user_id == current_user.id)
        .order_by(MedicalAiAnalysis.created_at.desc())
        .limit(100)
        .all()
    )
    return [analysis_to_out(analysis) for analysis in analyses]


@router.get("/{analysis_id}", response_model=MedicalAiAnalysisOut)
def get_medical_ai_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analysis = (
        db.query(MedicalAiAnalysis)
        .filter(MedicalAiAnalysis.id == analysis_id, MedicalAiAnalysis.user_id == current_user.id)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical AI analysis not found.")
    return analysis_to_out(analysis)
