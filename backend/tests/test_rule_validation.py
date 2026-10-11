"""Report validation rules (services/rule_validation_service.py): they alone set validation_status."""

import pytest

from services.rule_validation_service import validate_medical_rules

# Long enough (20+ words) and mentions allergies, so only the rule under test fires.
BASE = (
    "Patient report reviewed in clinic today with routine laboratory panel attached for follow up. "
    "Allergies: none known. Doctor notes are attached below for reference."
)


def codes(result) -> set[str]:
    return {w["code"] for w in result["warnings"]}


def test_complete_report_without_findings_has_no_rule_alerts():
    result = validate_medical_rules(BASE)
    assert codes(result) == {"NO_RULE_ALERTS"}


def test_short_text_is_flagged_as_incomplete():
    result = validate_medical_rules("Glucose 90. Allergies: none.")
    assert result["status"] == "CAUTION"
    assert "INCOMPLETE_OCR_TEXT" in codes(result)
    assert result["confidence"] == 0.45


def test_missing_allergy_information_is_caution():
    text = BASE.replace("Allergies: none known.", "")
    result = validate_medical_rules(text)
    assert result["status"] == "CAUTION"
    assert "MISSING_ALLERGY_DATA" in codes(result)


@pytest.mark.parametrize(
    ("snippet", "status", "code"),
    [
        ("Glucose 180 mg/dL", None, None),
        ("Glucose 250 mg/dL", "CAUTION", "HIGH_GLUCOSE"),
        ("Glucose 320 mg/dL", "HIGH_RISK", "HIGH_GLUCOSE"),
        ("HbA1c 6.4 %", None, None),
        ("HbA1c 7.2 %", "CAUTION", "HIGH_HBA1C"),
        ("BP 120/80", None, None),
        ("BP 150/95", "CAUTION", "HYPERTENSION_INDICATOR"),
        ("BP 185/100", "HIGH_RISK", "HYPERTENSION_INDICATOR"),
        ("BP 130/125", "HIGH_RISK", "HYPERTENSION_INDICATOR"),
        ("Creatinine 1.1 mg/dL", None, None),
        ("Creatinine 2.0 mg/dL", "CAUTION", "KIDNEY_RISK_CREATININE"),
        ("eGFR 75", None, None),
        ("eGFR 45", "CAUTION", "KIDNEY_RISK_EGFR"),
        ("eGFR 20", "HIGH_RISK", "KIDNEY_RISK_EGFR"),
    ],
)
def test_lab_thresholds(snippet, status, code):
    result = validate_medical_rules(f"{BASE} {snippet}.")
    if code is None:
        assert codes(result) == {"NO_RULE_ALERTS"}, f"{snippet} should not raise an alert"
    else:
        assert code in codes(result)
        assert result["status"] == status


def test_structured_fields_take_precedence_over_text():
    result = validate_medical_rules(f"{BASE} Glucose 90.", structured_fields={"glucose": "350"})
    assert result["status"] == "HIGH_RISK"


@pytest.mark.parametrize(
    ("medicines", "status", "code"),
    [
        ("Tab Warfarin 5mg and Tab Aspirin 75mg", "HIGH_RISK", "DANGEROUS_MEDICINE_COMBINATION"),
        ("Tab Sildenafil 50mg and Tab Nitroglycerin", "HIGH_RISK", "DANGEROUS_MEDICINE_COMBINATION"),
        ("Tab Aspirin 75mg and Tab Ibuprofen 400mg", "CAUTION", "MEDICINE_COMBINATION_CAUTION"),
        ("Tab Metformin 500mg and Tab Metformin 500mg", "CAUTION", "DUPLICATE_MEDICINE"),
    ],
)
def test_medicine_rules_from_text(medicines, status, code):
    result = validate_medical_rules(f"{BASE} {medicines}.")
    assert code in codes(result)
    assert result["status"] == status


def test_medicine_entities_count_as_medicines():
    entities = [{"label": "Medicine", "text": "Warfarin"}, {"label": "Medicine", "text": "Ibuprofen"}]
    result = validate_medical_rules(BASE, entities=entities)
    assert result["status"] == "HIGH_RISK"


def test_status_never_goes_down():
    # High glucose (HIGH_RISK) followed by a caution-level rule keeps HIGH_RISK.
    result = validate_medical_rules(f"{BASE} Glucose 320. HbA1c 7.5.")
    assert result["status"] == "HIGH_RISK"
    assert {"HIGH_GLUCOSE", "HIGH_HBA1C"} <= codes(result)


def test_evidence_is_trimmed():
    result = validate_medical_rules("x " * 5)
    assert all(len(w.get("evidence", "")) <= 220 for w in result["warnings"])
