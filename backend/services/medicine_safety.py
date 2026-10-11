"""Deterministic medicine-safety rules.

These rules alone decide the status (AGENTS.md 6.2); an LLM may only explain it.
"No data" means no rule matched. It never means "safe": the rules know only a few
interactions plus allergy, duplicate and dosage-wording checks.
"""

from models import MedicineHistory


def normalized_medicine_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


SAFETY_SEVERITY = {"No data": 0, "Caution": 1, "High Risk": 2}


def _raise_status(current: str, candidate: str) -> str:
    return candidate if SAFETY_SEVERITY[candidate] > SAFETY_SEVERITY[current] else current


def check_medicine_safety(
    medicine_name: str, dosage: str | None, known_allergies: str | None, medicines: list[MedicineHistory]
):
    requested = normalized_medicine_name(medicine_name)
    allergy_text = (known_allergies or "").lower()
    warnings: list[str] = []
    # Never "Safe": these rules know only a few interactions (AGENTS.md 6.2).
    status_label = "No data"

    if requested and requested in allergy_text:
        warnings.append("The requested medicine appears in the known allergy text.")
        status_label = "High Risk"

    for medicine in medicines:
        existing = normalized_medicine_name(medicine.medicine_name)
        side_effects = (medicine.side_effects or "").lower()
        if existing == requested:
            warnings.append(f"Duplicate medicine history found: {medicine.medicine_name}.")
            status_label = _raise_status(status_label, "Caution")
        if (
            requested
            and requested in side_effects
            and any(term in side_effects for term in ["allergy", "rash", "swelling", "breathing"])
        ):
            warnings.append(f"Possible allergy or reaction noted previously for {medicine.medicine_name}.")
            status_label = "High Risk"

    active_names = {normalized_medicine_name(medicine.medicine_name) for medicine in medicines}
    requested_set = active_names | {requested}
    high_risk_pairs = [
        ({"warfarin", "aspirin"}, "Warfarin with aspirin can increase bleeding risk."),
        ({"warfarin", "ibuprofen"}, "Warfarin with ibuprofen can increase bleeding risk."),
        ({"nitrate", "sildenafil"}, "Nitrates with sildenafil can cause dangerous blood pressure drops."),
    ]
    caution_pairs = [
        ({"aspirin", "ibuprofen"}, "Aspirin with ibuprofen may increase stomach or bleeding risk."),
        ({"insulin", "glimepiride"}, "Insulin with sulfonylurea medicines can increase low sugar risk."),
        ({"metformin", "contrast"}, "Metformin needs doctor review around some contrast imaging procedures."),
    ]

    for pair, reason in high_risk_pairs:
        if pair.issubset(requested_set):
            warnings.append(reason)
            status_label = "High Risk"

    for pair, reason in caution_pairs:
        if pair.issubset(requested_set):
            warnings.append(reason)
            status_label = _raise_status(status_label, "Caution")

    if dosage and any(term in dosage.lower() for term in ["double", "extra", "repeat"]):
        warnings.append("Dosage wording suggests repeated or extra dosing and should be clarified.")
        status_label = _raise_status(status_label, "Caution")

    if not warnings:
        warnings.append(
            "No duplicate, allergy or listed interaction was found. This check covers only a few common "
            "interactions, so it does not mean the medicine is safe: ask your doctor or pharmacist."
        )

    reason = " ".join(warnings)
    return status_label, reason, warnings
