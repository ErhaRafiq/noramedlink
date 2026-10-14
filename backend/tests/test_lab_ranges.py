"""Lab ranges, units and thresholds (services/lab_rules.py), as the per-report rules apply them."""

import pytest

from services.icse.entities import extract_entities
from services.knowledge import find_lab_tests
from services.lab_rules import RULES, assess
from services.rule_validation_service import validate_medical_rules

BASE = (
    "Patient report reviewed in clinic today with routine laboratory panel attached for follow up. "
    "Allergies: none known. Doctor notes are attached below for reference."
)


def codes(text: str) -> list[str]:
    result = validate_medical_rules(f"{BASE}\n{text}")
    return [w["code"] for w in result["warnings"] if w["code"] != "NO_RULE_ALERTS"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Each range, just inside and just outside.
        ("Hemoglobin 12.0 g/dL", []),
        ("Hemoglobin 11.9 g/dL", ["HEMOGLOBIN_LOW"]),
        ("Hemoglobin 17.6 g/dL", ["HEMOGLOBIN_HIGH"]),
        ("WBC 4.0", []),
        ("WBC 3.9", ["WBC_LOW"]),
        ("WBC 11.1", ["WBC_HIGH"]),
        ("Platelets 150", []),
        ("Platelets 140", ["PLATELETS_LOW"]),
        ("Platelets 460", ["PLATELETS_HIGH"]),
        ("Glucose 70 mg/dL", []),
        ("Glucose 65 mg/dL", ["GLUCOSE_LOW"]),
        ("Urea 45 mg/dL", []),
        ("Urea 50 mg/dL", ["UREA_HIGH"]),
        ("Bilirubin 1.2 mg/dL", []),
        ("Bilirubin 1.5 mg/dL", ["BILIRUBIN_HIGH"]),
        ("ALT 56 U/L", []),
        ("ALT 57 U/L", ["ALT_HIGH"]),
        ("AST 40 U/L", []),
        ("AST 41 U/L", ["AST_HIGH"]),
        ("LDL 130 mg/dL", []),
        ("LDL 160 mg/dL", ["LDL_HIGH"]),
        ("HDL 40 mg/dL", []),
        ("HDL 35 mg/dL", ["HDL_LOW"]),
        ("Triglycerides 150 mg/dL", []),
        ("Triglycerides 200 mg/dL", ["TRIGLYCERIDES_HIGH"]),
        ("SpO2 95%", []),
        ("SpO2 92%", ["SPO2_LOW"]),
        # Added when the summary's rules and the report's rules became one.
        ("Potassium 5.1 mmol/L", []),
        ("Potassium 5.6 mmol/L", ["POTASSIUM_HIGH"]),
        ("Sodium 131 mmol/L", ["SODIUM_LOW"]),
        ("Total Cholesterol 240 mg/dL", ["CHOLESTEROL_HIGH"]),
        ("TSH 6.8 mIU/L", ["TSH_HIGH"]),
        ("BUN 30 mg/dL", ["BUN_HIGH"]),
        ("Fasting Blood Sugar 125 mg/dL", []),
        ("Fasting Blood Sugar 126 mg/dL", ["HIGH_GLUCOSE"]),
    ],
)
def test_ranges(text, expected):
    assert codes(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Other units are converted, so in-range values in them raise nothing.
        ("Hb 135 g/L", []),
        ("Hb 95 g/L", ["HEMOGLOBIN_LOW"]),
        ("TLC 6,500 /cumm", []),
        ("WBC 13200 /uL", ["WBC_HIGH"]),
        ("Platelet count 2,50,000", []),  # no unit, but only "per microlitre" fits
        ("Platelets 1.2 lakh", ["PLATELETS_LOW"]),
        ("Glucose 5.4 mmol/L", []),
        ("Glucose 3.5 mmol/L", ["GLUCOSE_LOW"]),
        ("Urea 5 mmol/L", []),
        ("Urea 12 mmol/L", ["UREA_HIGH"]),
        ("Total bilirubin 15 umol/L", []),
        ("Total bilirubin 30 umol/L", ["BILIRUBIN_HIGH"]),
        ("LDL 3.0 mmol/L", []),
        ("LDL 4.5 mmol/L", ["LDL_HIGH"]),
        ("Triglycerides 1.5 mmol/L", []),
        ("Triglycerides 2.5 mmol/L", ["TRIGLYCERIDES_HIGH"]),
        ("HbA1c 64 mmol/mol", ["HIGH_HBA1C"]),  # about 8.0%
    ],
)
def test_units_are_converted(text, expected):
    assert codes(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "LDL/HDL ratio 3.1",  # a ratio, not LDL or HDL
        "Hemoglobin (13.0-17.0) 14.2 g/dL",  # printed range in brackets is skipped
        "No laboratory values in this note.",
        "Urine sugar 1+",  # not a blood glucose
        "Blood sugar 2 hours after meal",  # 2 is a time
    ],
)
def test_no_false_alerts(text):
    assert codes(text) == []


@pytest.mark.parametrize("text", ["Hb A1c 7.0 %", "HbA1c 8.0 %"])
def test_hba1c_is_never_read_as_hemoglobin(text):
    assert codes(text) == ["HIGH_HBA1C"]


def test_the_printed_range_does_not_hide_a_low_value():
    assert codes("Hemoglobin (13.0-17.0) 10.1 g/dL") == ["HEMOGLOBIN_LOW"]


def test_a_word_after_the_value_is_not_a_unit():
    assert codes("Hb 10.2 today, repeat next week") == ["HEMOGLOBIN_LOW"]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Hemoglobin 9.1 %", "unit"),
        ("Random Blood Sugar 30", "no unit"),  # 30 mg/dL or 30 mmol/L: cannot tell
        ("Creatinine 20", "no unit"),  # 20 mg/dL or 20 umol/L: cannot tell
        ("Hemoglobin 95 g/dL", "possible"),
        ("Creatinine [?] mg/dL", "could not be read"),
    ],
)
def test_a_value_that_cannot_be_used_is_shown_to_check_never_judged(text, reason):
    result = validate_medical_rules(f"{BASE}\n{text}")
    [warning] = [w for w in result["warnings"] if w["code"] != "NO_RULE_ALERTS"]
    assert warning["code"] == "VALUE_NEEDS_CHECK" and warning["severity"] == "CAUTION"
    assert reason in warning["message"] and "check against the original report" in warning["message"]


@pytest.mark.parametrize(
    ("text", "value"),
    [("Glucose 7.2", 129.6), ("Creatinine 212", 2.4), ("Hb 128", 12.8), ("Platelets 45000", 45)],
)
def test_a_value_without_a_unit_is_read_only_where_one_unit_fits(text, value):
    [entity] = [e for e in extract_entities(text) if e["type"] == "test_result"]
    assessment = assess(entity)
    assert round(assessment.value, 1) == value and assessment.unit_note.startswith("no unit printed")


def test_critical_values_are_high_risk():
    result = validate_medical_rules(f"{BASE}\nPotassium 6.9 mmol/L")
    assert result["status"] == "HIGH_RISK"
    assert validate_medical_rules(f"{BASE}\nGlucose 50 mg/dL")["status"] == "HIGH_RISK"


def test_messages_are_advisory_and_never_say_normal_or_safe():
    result = validate_medical_rules(f"{BASE}\nHemoglobin 9.0 g/dL. ALT 90 U/L. SpO2 90%")
    lab = [w for w in result["warnings"] if w["code"] in {"HEMOGLOBIN_LOW", "ALT_HIGH", "SPO2_LOW"}]
    assert len(lab) == 3
    for warning in lab:
        assert warning["severity"] == "CAUTION"
        assert "for physician review" in warning["message"]
        assert "Ranges differ between labs" in warning["message"]
        assert "normal" not in warning["message"].lower() and "safe" not in warning["message"].lower()


def test_every_rule_has_a_bound_and_a_knowledge_base_name():
    for name, rule in RULES.items():
        assert rule.low is not None or rule.high is not None
        assert [m.info.name for m in find_lab_tests(name)] == [name]


def test_evidence_is_the_line_the_value_came_from():
    result = validate_medical_rules(f"{BASE}\nReport: Hb 9.5 g/dL, recheck")
    [warning] = [w for w in result["warnings"] if w["code"] == "HEMOGLOBIN_LOW"]
    assert warning["evidence"] == "Report: Hb 9.5 g/dL, recheck"


def test_lab_ranges_raise_the_report_to_caution():
    result = validate_medical_rules(f"{BASE} Hemoglobin 9.5 g/dL.")
    assert result["status"] == "CAUTION"
    assert "HEMOGLOBIN_LOW" in {w["code"] for w in result["warnings"]}
    assert "lab_reference_ranges" in result["rules_checked"]


def test_glucose_in_mmol_is_converted():
    # 16.7 mmol/L is about 300 mg/dL; it used to be compared as 16.7 and missed.
    assert validate_medical_rules(f"{BASE} Glucose 16.7 mmol/L.")["status"] == "HIGH_RISK"


def test_creatinine_in_umol_is_converted():
    # 88 umol/L is about 1.0 mg/dL; it used to raise a kidney alert.
    assert "KIDNEY_RISK_CREATININE" not in codes("Creatinine 88 umol/L.")
    assert "KIDNEY_RISK_CREATININE" in codes("Creatinine 180 umol/L.")


def test_a_unit_written_after_another_value_is_not_borrowed():
    # The mmol/L belongs to urea; glucose 110 mg/dL must not be read as mmol.
    assert validate_medical_rules(f"{BASE} Glucose 110 mg/dL, Urea 5 mmol/L.")["status"] == "SAFE"


# Every glucose reading is checked; the most severe one counts.


def glucose_alerts(text: str) -> list[tuple[str, str]]:
    result = validate_medical_rules(f"{BASE}\n{text}")
    return [(w["code"], w["severity"]) for w in result["warnings"] if "GLUCOSE" in w["code"]]


def test_random_sugar_230_with_a_normal_fasting_value_raises_an_alert():
    text = "Fasting Blood Sugar | 92 | mg/dL | 70 - 100\nRandom Blood Sugar | 230 | mg/dL | < 140"
    assert glucose_alerts(text) == [("HIGH_GLUCOSE", "CAUTION")]
    assert validate_medical_rules(f"{BASE}\n{text}")["status"] == "CAUTION"


def test_the_most_severe_glucose_reading_sets_the_status():
    text = "Fasting Blood Sugar 210 mg/dL. Random Blood Sugar 320 mg/dL."
    assert validate_medical_rules(f"{BASE} {text}")["status"] == "HIGH_RISK"
    assert sorted(glucose_alerts(text)) == [("HIGH_GLUCOSE", "CAUTION"), ("HIGH_GLUCOSE", "HIGH_RISK")]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Post Prandial Blood Sugar 250 mg/dL", [("HIGH_GLUCOSE", "CAUTION")]),
        ("PPBS: 260 mg/dL", [("HIGH_GLUCOSE", "CAUTION")]),
        ("FBS 5.0 mmol/L, RBS 16.7 mmol/L", [("HIGH_GLUCOSE", "HIGH_RISK")]),  # 16.7 mmol/L is about 300 mg/dL
        ("Fasting Blood Sugar 95 mg/dL. Random Blood Sugar 62 mg/dL", [("GLUCOSE_LOW", "CAUTION")]),
        ("Fasting Blood Sugar 95 mg/dL. Random Blood Sugar 120 mg/dL", []),
        ("Fasting Blood Sugar 140 mg/dL", [("HIGH_GLUCOSE", "CAUTION")]),  # ADA fasting threshold, was 200
        ("Random Blood Sugar 50 mg/dL", [("GLUCOSE_LOW", "HIGH_RISK")]),  # under 54: was CAUTION
    ],
)
def test_each_kind_of_glucose_reading_is_checked(text, expected):
    assert glucose_alerts(text) == expected


def test_one_reading_reached_through_two_names_counts_once():
    # "Fasting Blood Sugar" also contains "blood sugar" and "sugar": one reading, one alert.
    assert glucose_alerts("Fasting Blood Sugar 250 mg/dL") == [("HIGH_GLUCOSE", "CAUTION")]


def test_a_time_after_the_name_is_not_a_glucose_value():
    # "2 hours" must not become glucose 2 (a false low alert); the 180 is then not read: missing, not wrong.
    assert glucose_alerts("Blood sugar 2 hours after meal 180 mg/dL") == []


def test_every_reading_is_kept_in_order():
    entities = extract_entities("FBS 92 mg/dL ... RBS 230 mg/dL ... PPBS 180 mg/dL")
    assert [(e["name"], e["value"]) for e in entities if e["type"] == "test_result"] == [
        ("Fasting Blood Sugar", "92"),
        ("Random Blood Sugar", "230"),
        ("Post Prandial Blood Sugar", "180"),
    ]
