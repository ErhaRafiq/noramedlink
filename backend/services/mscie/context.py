"""The patient context MSCIE checks against, built from the record (Module 3 reads it).

- Current medicines: the latest report's medicine list (not marked stopped), the medication
  schedule and medicine history entered in the app (not ended), and confirmed prescriptions.
- Previous responses: medicines stopped in reports, and medicine history with an end date or a side
  effect recorded.
- Conditions and allergies as mentioned in reports (not negated, not family history).
- The latest usable eGFR, potassium and creatinine, with their date and report.

Built from identity-free text (Module 3's reader); nothing here is written to the record.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from models import MedicineHistory, Prescription, User
from services import knowledge
from services.icse.versions import gather
from services.lab_rules import assess
from services.mscie.engine import Med, PatientContext, resolve

LAB_TESTS = ("eGFR", "Potassium", "Creatinine")


def _report_label(source: dict) -> str:
    title = source.get("title") or f"report {source['report_id']}"
    return f"{title}, {source['date']}" if source.get("date") else title


def build_context(db: Session, patient: User, today: date | None = None) -> PatientContext:
    today = today or date.today()
    inputs = gather(db, patient)
    sources = inputs["sources"]  # oldest first
    context = PatientContext()

    # Latest report that lists medicines: its ongoing medicines (same rule as the clinical summary).
    for source in reversed(sources):
        listed = [
            e for e in source["entities"]
            if e.get("type") == "medication" and e.get("method") != "biobert" and not e.get("negated")
        ]  # fmt: skip
        if listed:
            for entity in listed:
                if entity.get("status") == "stopped":
                    context.previous.append(
                        {
                            "generic": entity["name"],
                            "problem": True,
                            "note": f"marked stopped in {_report_label(source)}",
                        }
                    )
                else:
                    ref = {"report_id": source["report_id"], "date": source.get("date")}
                    context.medicines.append(resolve(entity["name"], "latest report's medicine list", ref))
            break

    for item in inputs["medications"]:
        if item.get("end_date") and item["end_date"] < today.isoformat():
            continue
        context.medicines.append(resolve(item["name"], f"{item['list']} (entered in the app)"))
    for history in db.query(MedicineHistory).filter(MedicineHistory.patient_id == patient.id).all():
        info = knowledge.resolve_medication(history.medicine_name)
        if info is None:
            continue
        problem = bool((history.side_effects or "").strip())
        ended = history.end_date is not None and history.end_date < today
        if problem or ended:
            note = f"side effect recorded: {history.side_effects.strip()}" if problem else f"ended {history.end_date}"
            for generic in info.generics:
                context.previous.append({"generic": generic, "problem": problem, "note": note})
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.id, Prescription.status == "confirmed")
        .order_by(Prescription.created_at.desc())
        .all()
    )
    for prescription in prescriptions:
        for item in prescription.items:
            when = prescription.created_at.date().isoformat() if prescription.created_at else None
            context.medicines.append(
                resolve(item.medicine, f"prescribed by {prescription.doctor_name}", {"date": when})
            )

    # De-duplicate medicines by what they are (a brand and its generic are one medicine).
    unique: dict[tuple, Med] = {}
    for med in context.medicines:
        unique.setdefault(med.generics or (med.name.lower(),), med)
    context.medicines = list(unique.values())

    for source in sources:
        for entity in source["entities"]:
            kind = entity.get("type")
            if entity.get("method") == "biobert":
                continue
            if kind == "condition" and entity.get("negated") is False:
                if all(c["name"] != entity["name"] for c in context.conditions):
                    context.conditions.append({"name": entity["name"], "source": _report_label(source)})
            elif kind == "allergy":
                info = knowledge.resolve_medication(entity["name"])
                context.allergies.append(
                    {
                        "name": entity["name"],
                        "generics": list(info.generics) if info else [],
                        "classes": list(entity.get("allergen_classes") or (info.classes if info else ())),
                        "source": _report_label(source),
                    }
                )
            elif kind == "allergy_status" and context.allergy_status == "not_recorded":
                context.allergy_status = "none_recorded"
            elif kind == "test_result" and entity.get("name") in LAB_TESTS:
                assessment = assess(entity)
                if assessment and assessment.value is not None and not assessment.problem:
                    context.labs[entity["name"]] = {  # sources run oldest first: the latest wins
                        "value": round(float(assessment.value), 2),
                        "unit": assessment.unit,
                        "date": source.get("date"),
                        "source": _report_label(source),
                    }
    if context.allergies:
        context.allergy_status = "listed"
    return context


def context_summary(context: PatientContext) -> dict[str, Any]:
    """The context as the physician sees it next to the alerts (FE-5: what the check used)."""
    return {
        "medicines": [
            {"name": m.label, "known": m.known, "source": m.source, "date": m.ref.get("date")}
            for m in context.medicines
        ],
        "conditions": context.conditions,
        "allergies": [{"name": a["name"], "source": a["source"]} for a in context.allergies],
        "allergy_status": context.allergy_status,
        "labs": [{"test": test, **lab} for test, lab in context.labs.items()],
        "previous": context.previous,
    }
