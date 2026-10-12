import re
from typing import Any

from services.lab_ranges import check_lab_ranges, creatinine_mg_dl, glucose_mg_dl, read_value

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


def _number(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value or "")
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _value_near(text: str, aliases: list[str]) -> tuple[float | None, str | None]:
    compact = " ".join((text or "").split())
    for alias in aliases:
        escaped = re.escape(alias)
        match = re.search(
            rf"\b{escaped}\b[^0-9<>+-]{{0,45}}([<>+-]?\s*\d+(?:\.\d+)?)",
            compact,
            flags=re.IGNORECASE,
        )
        if match:
            value = _number(match.group(1))
            if value is not None:
                start = max(0, match.start() - 45)
                end = min(len(compact), match.end() + 60)
                return value, compact[start:end]
    return None, None


def _field_value(fields: dict[str, Any], keys: list[str]) -> tuple[float | None, str | None]:
    for key in keys:
        value = fields.get(key)
        if value is not None:
            parsed = _number(str(value))
            if parsed is not None:
                return parsed, f"{key}: {value}"
    return None, None


# A blood pressure only where the text says so: "BP"/"blood pressure" just before, or
# "mmHg" just after. Any "a/b" (dates, IDs such as "43102/2609") used to be read as one.
_BP_WITH_LABEL = re.compile(r"\b(?:bp|b\.p\.?|blood\s*pressure)\b[^0-9\n]{0,15}(\d{2,3})\s*/\s*(\d{2,3})\b", re.I)
_BP_WITH_UNIT = re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\s*mm\s*hg\b", re.I)


def _blood_pressure(field_value: str, text: str) -> tuple[int, int, str] | None:
    candidates = []
    field_match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", field_value)
    if field_match:
        candidates.append(field_match)
    candidates += [m for pattern in (_BP_WITH_LABEL, _BP_WITH_UNIT) for m in [pattern.search(text)] if m]
    for match in candidates:
        systolic, diastolic = int(match.group(1)), int(match.group(2))
        if 60 <= systolic <= 260 and 30 <= diastolic <= 160 and systolic > diastolic:  # plausible readings only
            return systolic, diastolic, f"{systolic}/{diastolic}"
    return None


def _converted_field(fields: dict[str, Any], keys: list[str], convert) -> tuple[float | None, str | None]:
    """A structured field's value, converted using the unit written right after the number."""
    for key in keys:
        raw = fields.get(key)
        if raw is None:
            continue
        match = re.match(r"\s*[<>]?\s*(\d+(?:\.\d+)?)\s*([a-zA-Zµμ%/^\d.]{0,14})", str(raw))
        if match:
            return round(convert(float(match.group(1)), match.group(2).lower()), 2), f"{key}: {raw}"
    return None, None


def _lab_value(fields, keys, text, aliases, convert) -> tuple[float | None, str | None]:
    value, evidence = _converted_field(fields, keys, convert)
    if value is None:
        reading = read_value(text, aliases, convert)
        if reading:
            value, evidence = reading.value, reading.evidence
    return value, evidence


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
) -> dict[str, Any]:
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

    # mmol/L values are converted to mg/dL (unit written after the number).
    glucose, glucose_evidence = _lab_value(
        fields, ["glucose", "blood_sugar", "rbs", "fbs"], source_text,
        ["glucose", "blood sugar", "sugar", "rbs", "fbs"], glucose_mg_dl,
    )  # fmt: skip
    if glucose is not None and glucose >= 200:
        warnings.append(
            _warning(
                "HIGH_GLUCOSE",
                "HIGH_RISK" if glucose >= 300 else "CAUTION",
                "Glucose value appears elevated and should be reviewed by a qualified clinician.",
                glucose_evidence,
            )
        )
        status = _highest_status(status, "HIGH_RISK" if glucose >= 300 else "CAUTION")

    hba1c, hba1c_evidence = _field_value(fields, ["hba1c", "hb_a1c"])
    if hba1c is None:
        hba1c, hba1c_evidence = _value_near(source_text, ["hba1c", "hb a1c"])
    if hba1c is not None and hba1c >= 6.5:
        warnings.append(
            _warning(
                "HIGH_HBA1C",
                "CAUTION",
                "HbA1c appears elevated and should be interpreted by a qualified clinician.",
                hba1c_evidence,
            )
        )
        status = _highest_status(status, "CAUTION")

    blood_pressure = _blood_pressure(str(fields.get("blood_pressure") or ""), " ".join(source_text.split()))
    if blood_pressure:
        systolic, diastolic, bp_evidence = blood_pressure
        if systolic >= 180 or diastolic >= 120:
            severity = "HIGH_RISK"
        elif systolic >= 140 or diastolic >= 90:
            severity = "CAUTION"
        else:
            severity = "SAFE"
        if severity != "SAFE":
            warnings.append(
                _warning(
                    "HYPERTENSION_INDICATOR",
                    severity,
                    "Blood pressure text appears elevated and should be checked against the original report.",
                    bp_evidence,
                )
            )
            status = _highest_status(status, severity)

    # umol/L values are converted to mg/dL; before, "Creatinine 88 umol/L" (normal) raised an alert.
    creatinine, creatinine_evidence = _lab_value(fields, ["creatinine"], source_text, ["creatinine"], creatinine_mg_dl)
    if creatinine is not None and creatinine > 1.3:
        warnings.append(
            _warning(
                "KIDNEY_RISK_CREATININE",
                "CAUTION",
                "Creatinine appears elevated and should be reviewed for possible kidney follow-up.",
                creatinine_evidence,
            )
        )
        status = _highest_status(status, "CAUTION")

    egfr, egfr_evidence = _field_value(fields, ["egfr", "e_gfr"])
    if egfr is None:
        egfr, egfr_evidence = _value_near(source_text, ["egfr", "e-gfr"])
    if egfr is not None and egfr < 60:
        warnings.append(
            _warning(
                "KIDNEY_RISK_EGFR",
                "HIGH_RISK" if egfr < 30 else "CAUTION",
                "eGFR appears reduced and should be reviewed by a qualified clinician.",
                egfr_evidence,
            )
        )
        status = _highest_status(status, "HIGH_RISK" if egfr < 30 else "CAUTION")

    for lab_warning in check_lab_ranges(source_text):
        warnings.append(lab_warning)
        status = _highest_status(status, lab_warning["severity"])

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
            "missing_allergy_data",
            "incomplete_ocr_text",
        ],
    }
