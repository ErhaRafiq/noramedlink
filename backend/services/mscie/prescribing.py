"""MSCIE FE-2 and FE-6: the real-time check before confirmation, and confirmation with overrides.

The check runs again on the server at confirmation (the client's copy is never trusted). Every
alert that is contraindicated or major needs the doctor's written justification (AGENTS.md 6.5);
the justifications are stored with the prescription. The doctor can prescribe any medicine,
including one the engine ranked lower or did not suggest: the engine informs, it never decides.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from models import Prescription, PrescriptionItem, SafetyOverride, User
from services import notifications
from services.mscie.alternatives import alternatives_for
from services.mscie.context import build_context, context_summary
from services.mscie.engine import RANK, PatientContext, Proposed, check, resolve, worst
from services.plain_language import rewrite

MIN_JUSTIFICATION = 20
NEEDS_ALTERNATIVES = {"contraindicated", "major", "moderate"}


class JustificationMissing(ValueError):
    def __init__(self, alerts: list[dict]):
        super().__init__("A written justification is needed for each high-risk alert.")
        self.alerts = alerts


def run_check(context: PatientContext, items: list[Proposed]) -> dict[str, Any]:
    """Alerts for each proposed medicine, and ranked alternatives where there is a risk."""
    results = check(context, items)
    resolved = [resolve(p.medicine, "this prescription") for p in items]
    for index, result in enumerate(results):
        result["alternatives"] = []
        if result["worst"] in NEEDS_ALTERNATIVES:
            others = [*context.medicines, *(m for i, m in enumerate(resolved) if i != index)]
            result["alternatives"] = alternatives_for(items[index], resolved[index], others, context)
    every = [a for r in results for a in r["alerts"]]
    return {
        "context": context_summary(context),
        "items": results,
        "worst": worst(every),
        "requires_justification": [a for a in every if a["requires_justification"]],
    }


def check_for_patient(db: Session, patient: User, items: list[Proposed]) -> dict[str, Any]:
    return run_check(build_context(db, patient), items)


def confirm(
    db: Session,
    patient: User,
    doctor: User,
    items: list[Proposed],
    justifications: dict[str, str],
    notes: str | None,
    extra: list[dict] | None = None,
) -> Prescription:
    """Store a confirmed prescription. Raises JustificationMissing when a high-risk alert has no
    written justification (at least MIN_JUSTIFICATION characters)."""
    result = check_for_patient(db, patient, items)
    missing = [
        a for a in result["requires_justification"]
        if len((justifications.get(a["id"]) or "").strip()) < MIN_JUSTIFICATION
    ]  # fmt: skip
    if missing:
        raise JustificationMissing(missing)
    prescription = Prescription(
        patient_id=patient.id,
        doctor_id=doctor.id,
        doctor_name=doctor.full_name,
        status="confirmed",
        notes=(notes or "").strip() or None,
        check_result=result["items"],
        context_snapshot=result["context"],
        created_at=datetime.now(UTC),
    )
    for position, (proposed, checked) in enumerate(zip(items, result["items"], strict=True), start=1):
        details = (extra or [{}] * len(items))[position - 1]
        prescription.items.append(
            PrescriptionItem(
                position=position,
                medicine=proposed.medicine.strip(),
                generic=" + ".join(checked["resolved"]["generics"]) or None,
                dose=proposed.dose,
                frequency=proposed.frequency,
                duration=proposed.duration,
                instructions=details.get("instructions"),
                replaced_medicine=details.get("replaced_medicine"),
            )
        )
    for alert in result["requires_justification"]:
        prescription.overrides.append(
            SafetyOverride(
                doctor_id=doctor.id,
                alert_id=alert["id"],
                alert_severity=alert["severity"],
                alert_title=alert["title"][:300],
                justification=justifications[alert["id"]].strip(),
            )
        )
    db.add(prescription)
    db.flush()  # the id, for the notification's key
    notifications.prescription_added(db, patient.id, doctor.full_name, prescription.id)
    db.commit()
    db.refresh(prescription)
    return prescription


def cancel(db: Session, prescription: Prescription) -> Prescription:
    prescription.status = "cancelled"
    prescription.cancelled_at = datetime.now(UTC)
    notifications.prescription_cancelled(db, prescription.patient_id, prescription.doctor_name, prescription.id)
    db.commit()
    db.refresh(prescription)
    return prescription


def to_out(prescription: Prescription) -> dict[str, Any]:
    alerts = [a for item in prescription.check_result or [] for a in item.get("alerts", [])]
    return {
        "id": prescription.id,
        "patient_id": prescription.patient_id,
        "doctor_id": prescription.doctor_id,
        "doctor_name": prescription.doctor_name,
        "status": prescription.status,
        "notes": prescription.notes,
        "created_at": prescription.created_at,
        "cancelled_at": prescription.cancelled_at,
        "items": [
            {
                "medicine": i.medicine,
                "generic": i.generic,
                "dose": i.dose,
                "frequency": i.frequency,
                "duration": i.duration,
                "instructions": i.instructions,
                "replaced_medicine": i.replaced_medicine,
            }
            for i in prescription.items
        ],
        "overrides": [
            {
                "alert_id": o.alert_id,
                "severity": o.alert_severity,
                "title": o.alert_title,
                "justification": o.justification,
                "created_at": o.created_at,
            }
            for o in prescription.overrides
        ],
        "alerts_at_confirmation": sorted(alerts, key=lambda a: -RANK[a["severity"]]),
    }


def to_patient_out(prescription: Prescription) -> dict[str, Any]:
    """What the patient sees: the medicines in everyday words, read-only. No clinical alerts."""
    return {
        "id": prescription.id,
        "doctor_name": prescription.doctor_name,
        "status": prescription.status,
        "created_at": prescription.created_at,
        "items": [
            {
                "medicine": i.medicine,
                "generic": i.generic,
                "how_to_take": rewrite(" ".join(p for p in (i.dose, i.frequency) if p) or "as your doctor told you"),
                "duration": i.duration,
                "instructions": i.instructions,
            }
            for i in prescription.items
        ],
    }
