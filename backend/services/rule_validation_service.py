import re
from typing import Any

from services.icse.entities import extract_entities
from services.lab_rules import assess, warning_for
from services.plain_language import patient_message

STATUS_ORDER = {"SAFE": 0, "CAUTION": 1, "HIGH_RISK": 2}

HIGH_RISK_PAIRS = [
    ({"warfarin", "aspirin"}, "Warfarin and aspirin can increase bleeding risk."),
    ({"warfarin", "ibuprofen"}, "Warfarin and ibuprofen can increase bleeding risk."),
    ({"nitroglycerin", "sildenafil"}, "Nitrates and sildenafil can cause dangerous blood pressure drops."),
    ({"nitrate", "sildenafil"}, "Nitrates and sildenafil can cause dangerous blood pressure drops."),
]

CAUTION_PAIRS = [
    ({"aspirin", "ibuprofen"}, "Aspirin and ibuprofen may increase stomach or bleeding risk."),
    ({"insulin", "glimepiride"}, "Insulin with sulfonylurea medicines can increase low sugar risk."),
    ({"metformin", "contrast"}, "Metformin needs doctor review around some contrast imaging procedures."),
]


def _highest_status(first: str, second: str) -> str:
    return first if STATUS_ORDER.get(first, 1) >= STATUS_ORDER.get(second, 1) else second


def _warning(code: str, severity: str, message: str, evidence: str | None = None) -> dict[str, str]:
    payload = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if evidence:
        payload["evidence"] = evidence[:220]
    return payload


def _medicine_names(entities: list[dict[str, Any]], text: str) -> list[str]:
    names: list[str] = []
    for entity in entities:
        if str(entity.get("label") or "").lower() == "medicine":
            names.append(str(entity.get("text") or "").lower().strip())

    for match in re.finditer(
        r"\b(?:tab|tablet|cap|capsule|inj|injection|syrup)\.?\s+([a-z][a-z0-9-]{2,35})",
        text,
        flags=re.IGNORECASE,
    ):
        names.append(match.group(1).lower())

    return [" ".join(name.split()) for name in names if len(name.strip()) >= 3]


def _has_allergy_data(text: str, entities: list[dict[str, Any]]) -> bool:
    lowered = text.lower()
    if any(term in lowered for term in ["allergy", "allergies", "allergic", "nkda", "no known drug allergies"]):
        return True
    return any(str(entity.get("label") or "").lower() == "allergy" for entity in entities)


def validate_medical_rules(
    text: str,
    structured_fields: dict[str, Any] | None = None,
    entities: list[dict[str, Any]] | None = None,
    uncertain_values: list[dict[str, Any]] | None = None,
    ocr_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`uncertain_values`: numbers OCR read with low confidence (ocr_layout.uncertain_values).
    `ocr_rows`: the OCR rows, so each value carries its own confidence (as in the clinical summary)."""
    source_text = text or ""
    fields = structured_fields or {}
    entity_rows = entities or []
    warnings: list[dict[str, str]] = []
    status = "SAFE"

    compact_text = " ".join(source_text.split())
    word_count = len(compact_text.split())
    if word_count < 20:
        warnings.append(
            _warning(
                "INCOMPLETE_OCR_TEXT",
                "CAUTION",
                "OCR text is short or incomplete. Verify the original file before clinical use.",
                compact_text,
            )
        )
        status = _highest_status(status, "CAUTION")

    medicine_names = _medicine_names(entity_rows, source_text)
    duplicated = sorted({name for name in medicine_names if medicine_names.count(name) > 1})
    for name in duplicated:
        warnings.append(
            _warning(
                "DUPLICATE_MEDICINE",
                "CAUTION",
                f"Possible duplicate medicine mention: {name}.",
                name,
            )
        )
        status = _highest_status(status, "CAUTION")

    medicine_set = set(medicine_names)
    for pair, message in HIGH_RISK_PAIRS:
        if pair.issubset(medicine_set):
            warnings.append(_warning("DANGEROUS_MEDICINE_COMBINATION", "HIGH_RISK", message, ", ".join(sorted(pair))))
            status = _highest_status(status, "HIGH_RISK")
    for pair, message in CAUTION_PAIRS:
        if pair.issubset(medicine_set):
            warnings.append(_warning("MEDICINE_COMBINATION_CAUTION", "CAUTION", message, ", ".join(sorted(pair))))
            status = _highest_status(status, "CAUTION")

    # Lab values and blood pressure are read once (icse.entities, the reader the clinical summary
    # uses too) and judged once (lab_rules), so a value is never flagged in one place and passed in
    # the other. Every reading counts; a value that cannot be used is "check against the original".
    values = extract_entities(source_text, fields=fields, ocr_rows=ocr_rows)
    for entity in values:
        assessment = assess(entity)
        warning = warning_for(assessment) if assessment else None
        if warning:
            warnings.append(warning)
            status = _highest_status(status, warning["severity"])

    # Numbers OCR was unsure of are never judged as read: the report is at least CAUTION and they are
    # listed to check against the original. (The number in the text is left exactly as OCR read it.)
    # A test value or blood pressure read with low confidence is already listed above, value by value
    # (VALUE_NEEDS_CHECK); this lists the other uncertain numbers (doses, for example).
    judged = {(e["ocr_row"], cell) for e in values if e.get("ocr_row") for cell in e.get("ocr_cells", [])}
    uncertain_values = [v for v in uncertain_values or [] if (v["line"], v["text"]) not in judged]
    if uncertain_values:
        listed = ", ".join(f'{v["text"]} (in "{v["line"][:60]}")' for v in uncertain_values[:8])
        more = f" and {len(uncertain_values) - 8} more" if len(uncertain_values) > 8 else ""
        warnings.append(
            _warning(
                "UNCERTAIN_OCR_VALUES",
                "CAUTION",
                f"{len(uncertain_values)} number(s) were read with low OCR confidence: {listed}{more}. "
                "Check them against the original report before relying on them. For physician review.",
                "; ".join(v["line"] for v in uncertain_values[:3]),
            )
        )
        status = _highest_status(status, "CAUTION")

    if not _has_allergy_data(source_text, entity_rows):
        warnings.append(
            _warning(
                "MISSING_ALLERGY_DATA",
                "CAUTION",
                "No allergy information was found in the OCR text. Confirm allergy history before medicine decisions.",
            )
        )
        status = _highest_status(status, "CAUTION")

    if not warnings:
        warnings.append(
            _warning(
                "NO_RULE_ALERTS",
                "SAFE",
                "No duplicate medicine, common interaction, high glucose, hypertension, or kidney rule alert was detected.",
            )
        )

    # Every alert also in everyday words for the patient; the clinical message stays for doctors.
    for warning in warnings:
        warning["patient_message"] = patient_message(warning)

    confidence = 0.86
    if word_count < 20:
        confidence = 0.45
    elif status == "HIGH_RISK":
        confidence = 0.78
    elif status == "CAUTION":
        confidence = 0.72

    return {
        "status": status,
        "warnings": warnings,
        "confidence": confidence,
        "rules_checked": [
            "duplicate_medicines",
            "dangerous_combinations",
            "high_glucose",
            "hypertension_indicators",
            "kidney_risk_indicators",
            "lab_reference_ranges",
            "values_to_check",
            "uncertain_ocr_values",
            "missing_allergy_data",
            "incomplete_ocr_text",
        ],
    }
