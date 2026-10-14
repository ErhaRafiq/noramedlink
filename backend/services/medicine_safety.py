"""The patient's medicine-safety check, on the same engine as the doctor's (MSCIE, Module 4).

The rules alone decide the status (AGENTS.md 6.2); an LLM may only explain it. "No data" means no
rule matched. It never means "safe": the knowledge base is a demo covering about 60 medicines.
Status: contraindicated or major -> "High Risk"; moderate -> "Caution"; otherwise "No data".
The patient's messages are in everyday words.
"""

from __future__ import annotations

from datetime import date

from services.icse.entities import extract_entities
from services.mscie.engine import RANK, PatientContext, Proposed, check_item, resolve
from services.plain_language import rewrite

SAFETY_SEVERITY = {"No data": 0, "Caution": 1, "High Risk": 2}
STATUS = {"contraindicated": "High Risk", "major": "High Risk", "moderate": "Caution"}
NO_DATA = (
    "No allergy, duplicate, interaction or dose problem was found by the app's rules. These rules cover "
    "only a demo list of medicines, so this does not mean the medicine is safe: ask your doctor or pharmacist."
)
UNCLEAR_DOSE = ("double", "extra", "repeat")


def normalized_medicine_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _raise_status(current: str, candidate: str) -> str:
    return candidate if SAFETY_SEVERITY[candidate] > SAFETY_SEVERITY[current] else current


def _context_from(medicines, known_allergies: str | None, context: PatientContext | None) -> PatientContext:
    """The patient's record (when given) plus their saved medicine history and typed allergies."""
    ctx = context or PatientContext()
    today = date.today()
    for medicine in medicines:
        ended = getattr(medicine, "end_date", None) is not None and medicine.end_date < today
        side_effects = (getattr(medicine, "side_effects", None) or "").strip()
        resolved = resolve(medicine.medicine_name, "your medicine history")
        if side_effects:
            for generic in resolved.generics:
                ctx.previous.append(
                    {"generic": generic, "problem": True, "note": f"side effect recorded: {side_effects}"}
                )
        if not ended and resolved not in ctx.medicines:
            ctx.medicines.append(resolved)
    text = (known_allergies or "").strip()
    if text and text.lower() not in {"none", "nil", "no", "none known"}:
        for entity in extract_entities(f"Allergic to {text}."):
            if entity["type"] == "allergy":
                info = resolve(entity["name"])
                ctx.allergies.append(
                    {
                        "name": entity["name"],
                        "generics": list(info.generics),
                        "classes": list(entity.get("allergen_classes") or info.classes),
                        "source": "your allergy list",
                    }
                )
    return ctx


def _patient_words(alert: dict) -> str:
    return rewrite(f"{alert['title']}. {alert['effect']} {alert['management']}")


def check_medicine_safety(
    medicine_name: str,
    dosage: str | None,
    known_allergies: str | None,
    medicines,
    context: PatientContext | None = None,
):
    """(status, reason, warnings) for one medicine the patient asks about."""
    ctx = _context_from(medicines, known_allergies, context)
    requested = resolve(medicine_name, "your question")
    status_label = "No data"
    warnings: list[str] = []

    if not requested.known and requested.name.lower() in (known_allergies or "").lower():
        warnings.append(f"{requested.name} appears in your allergy text.")
        status_label = "High Risk"
    alerts = [
        a for a in check_item(requested, Proposed(medicine_name, dosage), ctx.medicines, ctx) if a["kind"] != "no_data"
    ]
    for alert in sorted(alerts, key=lambda a: -RANK[a["severity"]]):
        if alert["kind"] == "high_alert":
            continue
        if alert["kind"] == "allergy" and requested.known:
            warnings.append(f"{requested.label.capitalize()} matches your allergy text. " + _patient_words(alert))
        else:
            warnings.append(_patient_words(alert))
        status_label = _raise_status(status_label, STATUS.get(alert["severity"], "No data"))

    if dosage and any(term in dosage.lower() for term in UNCLEAR_DOSE):
        warnings.append("Dosage wording suggests repeated or extra dosing and should be clarified.")
        status_label = _raise_status(status_label, "Caution")
    if not requested.known:
        warnings.append(f"{requested.name} is not in the app's medicine list, so it could not be checked.")
    if not warnings or (status_label == "No data" and requested.known and not alerts):
        warnings.append(NO_DATA)
    return status_label, " ".join(warnings), warnings
