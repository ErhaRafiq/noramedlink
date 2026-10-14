"""The patient's "Health flags": what the app's fixed rules found in their own reports, in everyday words.

Replaces the AI-set risk levels on the patient dashboard (an AI never decides a risk, AGENTS.md
6.2). Built from each report's stored rule alerts (the same rules as the report page) and the
conditions its text mentions. Mentioned, never diagnosed; nothing here says "normal" or "safe".
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models import PatientReport
from services.report_service import conditions_mentioned, dict_field, list_field, with_patient_message

MAX_REPORTS = 8  # the most recent reports with a flag
# Alerts about the reading itself, not about the patient's health: shown on the report page only.
NOT_HEALTH = {"MISSING_ALLERGY_DATA", "INCOMPLETE_OCR_TEXT", "NO_RULE_ALERTS"}


def health_flags(db: Session, patient_id: int) -> dict[str, Any]:
    reports = (
        db.query(PatientReport)
        .filter(PatientReport.patient_id == patient_id)
        .order_by(PatientReport.upload_date.desc(), PatientReport.id.desc())
        .all()
    )
    flagged: list[dict[str, Any]] = []
    conditions: dict[str, dict[str, Any]] = {}
    for report in reports:
        for condition in conditions_mentioned(dict_field(report.structured_data_json).get("clinical_entities")):
            item = conditions.setdefault(condition["name"], {**condition, "report_ids": []})
            item["report_ids"].append(report.id)
        alerts = [
            with_patient_message(w)
            for w in list_field(report.rule_warnings)
            if isinstance(w, dict) and w.get("severity") in ("HIGH_RISK", "CAUTION") and w.get("code") not in NOT_HEALTH
        ]
        if alerts and len(flagged) < MAX_REPORTS:
            alerts.sort(key=lambda w: w.get("severity") != "HIGH_RISK")
            flagged.append(
                {
                    "report_id": report.id,
                    "report_title": report.title,
                    "upload_date": report.upload_date,
                    "severity": alerts[0]["severity"],
                    "messages": [w["patient_message"] for w in alerts],
                }
            )
    return {
        "reports": flagged,
        "high_risk_reports": sum(1 for r in flagged if r["severity"] == "HIGH_RISK"),
        "conditions_mentioned": list(conditions.values()),
    }
