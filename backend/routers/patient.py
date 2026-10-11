"""Patient dashboard overview and latest vitals.

Medicines and the safety check are in routers/patient_medicines.py; risk observations,
health tips and doctor summaries in routers/patient_insights.py.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_patient_profile, require_patient
from models import DoctorSummary, HealthRiskPrediction, PatientReport, User, Vitals
from routers.patient_insights import risk_to_out, summary_to_out
from routers.patient_medicines import patient_medicine_query
from schemas import DashboardCategory, PatientDashboardOut, VitalsOut
from services.report_service import report_to_out
from services.signup_service import user_to_out

router = APIRouter(prefix="/patient", tags=["patient"])


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
            matching_report = next(
                (report for report in reports if report.department_id == department_id and report.department), None
            )
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
    vital = db.query(Vitals).filter(Vitals.user_id == profile.user_id).order_by(Vitals.created_at.desc()).first()
    if not vital:
        return None
    return VitalsOut(
        id=vital.id,
        user_id=vital.user_id,
        blood_pressure=vital.blood_pressure,
        sugar_level=vital.sugar_level,
        created_at=vital.created_at,
    )
