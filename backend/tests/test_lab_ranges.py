"""Lab reference-range rules (services/lab_ranges.py) and their place in the report rules."""

import pytest

from services.lab_ranges import LAB_RANGES, check_lab_ranges, read_value, read_values
from services.rule_validation_service import validate_medical_rules


def codes(text: str) -> list[str]:
    return [warning["code"] for warning in check_lab_ranges(text)]


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
    ],
)
def test_ranges(text, expected):
    assert codes(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Other units are converted, so normal values in them raise nothing.
        ("Hb 135 g/L", []),
        ("Hb 95 g/L", ["HEMOGLOBIN_LOW"]),
        ("TLC 6,500 /cumm", []),
        ("WBC 13200 /uL", ["WBC_HIGH"]),
        ("Platelet count 2,50,000", []),
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
    ],
)
def test_units_are_converted(text, expected):
    assert codes(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Hb A1c 7.0 %",  # not a hemoglobin value
        "HbA1c 8.0 %",
        "LDL/HDL ratio 3.1",  # a ratio, not LDL or HDL
        "Hemoglobin (13.0-17.0) 14.2 g/dL",  # printed range in brackets is skipped
        "No laboratory values in this note.",
    ],
)
def test_no_false_alerts(text):
    assert codes(text) == []


def test_the_printed_range_does_not_hide_a_low_value():
    assert codes("Hemoglobin (13.0-17.0) 10.1 g/dL") == ["HEMOGLOBIN_LOW"]


def test_messages_are_advisory_and_never_say_normal_or_safe():
    for warning in check_lab_ranges("Hemoglobin 9.0 g/dL. ALT 90 U/L. SpO2 90%"):
        assert warning["severity"] == "CAUTION"
        assert "for physician review" in warning["message"]
        assert "Ranges differ between labs" in warning["message"]
        assert "normal" not in warning["message"].lower() and "safe" not in warning["message"].lower()


def test_every_range_has_a_bound_and_an_alias():
    for lab in LAB_RANGES:
        assert lab.aliases and (lab.low is not None or lab.high is not None)


def test_read_value_reports_the_converted_value_and_evidence():
    reading = read_value("Report: Hb 135 g/L, fine", ["hb"], lambda value, unit: value / 10 if "g/l" in unit else value)
    assert reading is not None and reading.value == 13.5 and reading.evidence.startswith("Hb 135 g/L")


# In the report rules (validate_medical_rules).
BASE = (
    "Patient report reviewed in clinic today with routine laboratory panel attached for follow up. "
    "Allergies: none known. Doctor notes are attached below for reference."
)


def test_lab_ranges_raise_the_report_to_caution():
    result = validate_medical_rules(f"{BASE} Hemoglobin 9.5 g/dL.")
    assert result["status"] == "CAUTION"
    assert "HEMOGLOBIN_LOW" in {w["code"] for w in result["warnings"]}
    assert "lab_reference_ranges" in result["rules_checked"]


def test_glucose_in_mmol_is_converted_for_the_existing_high_glucose_rule():
    # 16.7 mmol/L is about 300 mg/dL; it used to be compared as 16.7 and missed.
    result = validate_medical_rules(f"{BASE} Glucose 16.7 mmol/L.")
    assert result["status"] == "HIGH_RISK"


def test_creatinine_in_umol_is_converted():
    # 88 umol/L is about 1.0 mg/dL (normal); it used to raise a kidney alert.
    assert "KIDNEY_RISK_CREATININE" not in {
        w["code"] for w in validate_medical_rules(f"{BASE} Creatinine 88 umol/L.")["warnings"]
    }
    assert "KIDNEY_RISK_CREATININE" in {
        w["code"] for w in validate_medical_rules(f"{BASE} Creatinine 180 umol/L.")["warnings"]
    }


def test_a_unit_written_after_another_value_is_not_borrowed():
    # The mmol/L belongs to urea; glucose 110 mg/dL must not be read as mmol.
    result = validate_medical_rules(f"{BASE} Glucose 110 mg/dL, Urea 5 mmol/L.")
    assert result["status"] == "SAFE"


# Every glucose reading is checked; the most severe one counts.


def glucose_alerts(text: str) -> list[tuple[str, str]]:
    result = validate_medical_rules(f"{BASE} {text}")
    return [(w["code"], w["severity"]) for w in result["warnings"] if "GLUCOSE" in w["code"]]


def test_random_sugar_230_with_a_normal_fasting_value_raises_an_alert():
    text = "Fasting Blood Sugar | 92 | mg/dL | 70 - 100\nRandom Blood Sugar | 230 | mg/dL | < 140"
    assert glucose_alerts(text) == [("HIGH_GLUCOSE", "CAUTION")]
    assert validate_medical_rules(f"{BASE} {text}")["status"] == "CAUTION"


def test_the_most_severe_glucose_reading_sets_the_status():
    result = validate_medical_rules(f"{BASE} Fasting Blood Sugar 210 mg/dL. Random Blood Sugar 320 mg/dL.")
    assert result["status"] == "HIGH_RISK"
    assert sorted(glucose_alerts("Fasting Blood Sugar 210 mg/dL. Random Blood Sugar 320 mg/dL.")) == [
        ("HIGH_GLUCOSE", "CAUTION"),
        ("HIGH_GLUCOSE", "HIGH_RISK"),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Post Prandial Blood Sugar 250 mg/dL", [("HIGH_GLUCOSE", "CAUTION")]),
        ("PPBS: 260 mg/dL", [("HIGH_GLUCOSE", "CAUTION")]),
        ("FBS 5.0 mmol/L, RBS 16.7 mmol/L", [("HIGH_GLUCOSE", "HIGH_RISK")]),  # 16.7 mmol/L is about 300 mg/dL
        ("Fasting Blood Sugar 95 mg/dL. Random Blood Sugar 62 mg/dL", [("GLUCOSE_LOW", "CAUTION")]),
        ("Fasting Blood Sugar 95 mg/dL. Random Blood Sugar 120 mg/dL", []),
    ],
)
def test_each_kind_of_glucose_reading_is_checked(text, expected):
    assert glucose_alerts(text) == expected


def test_one_reading_reached_through_two_names_counts_once():
    # "Fasting Blood Sugar" matches both "blood sugar" and "sugar": one reading, one alert.
    assert glucose_alerts("Fasting Blood Sugar 250 mg/dL") == [("HIGH_GLUCOSE", "CAUTION")]
    assert [r.value for r in read_values("Fasting Blood Sugar 250 mg/dL", ["blood sugar", "sugar"])] == [250]


def test_a_time_after_the_name_is_not_a_glucose_value():
    # "2 hours" must not become glucose 2 (a false low alert); the 180 is then not read: missing, not wrong.
    assert glucose_alerts("Blood sugar 2 hours after meal 180 mg/dL") == []


def test_read_values_keeps_every_reading_in_order():
    readings = read_values("FBS 92 mg/dL ... RBS 230 mg/dL ... PPBS 180 mg/dL", ["fbs", "rbs", "ppbs"])
    assert [r.value for r in readings] == [92, 230, 180]
