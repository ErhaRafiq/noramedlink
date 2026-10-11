"""Summarize-page breakdown (services/report_breakdown.py)."""

import pytest

from services.report_breakdown import build_breakdown, measured_values, mentioned_terms, rule_alerts
from services.rule_validation_service import validate_medical_rules

EXAMPLE = (
    "CBC report: Hemoglobin 10.8 g/dL, WBC 13.2, Platelets 230. Patient has fever and cough for 3 days. "
    "No chest pain. Blood pressure 145/92. Glucose 186 mg/dL. Impression: possible infection."
)


def test_values_are_reported_as_written():
    assert measured_values(EXAMPLE) == [
        "Hemoglobin: 10.8 g/dL",
        "WBC: 13.2",
        "Platelets: 230",
        "Glucose: 186 mg/dL",
        "Blood pressure: 145/92",
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("HbA1c: 8.2%", "HbA1c: 8.2 %"),
        ("SGPT = 70 U/L", "ALT: 70 U/L"),
        ("eGFR 25", "eGFR: 25"),
        ("BP 120/80", "Blood pressure: 120/80"),
    ],
)
def test_aliases_and_units(text, expected):
    assert expected in measured_values(text)


def test_terms_are_split_into_present_and_absent():
    present, absent = mentioned_terms(EXAMPLE)
    assert present == ["fever", "cough", "infection"]
    assert absent == ["chest pain"]


def test_alerts_come_only_from_the_report_rules():
    text = "Tab Warfarin 5mg and Tab Aspirin 75mg. Creatinine 2.1 mg/dL. eGFR 25."
    alerts = rule_alerts(text)
    rule_messages = {w["message"] for w in validate_medical_rules(text)["warnings"]}
    assert alerts and all(any(alert.startswith(message) for message in rule_messages) for alert in alerts)


def test_scan_quality_alerts_are_left_out_for_pasted_text():
    alerts = rule_alerts("Short note.")  # short and without allergy information
    assert alerts == []


def test_breakdown_without_alerts_does_not_suggest_follow_up_on_alerts():
    breakdown = build_breakdown("Hemoglobin 13.5 g/dL. Allergies: none.")
    assert breakdown["risk_indicators"] == []
    assert len(breakdown["recommendations"]) == 2
    assert "Hemoglobin: 13.5 g/dL" in breakdown["key_findings"]


def test_breakdown_with_alerts():
    breakdown = build_breakdown(EXAMPLE)
    assert any("Blood pressure" in alert for alert in breakdown["risk_indicators"])
    assert "Stated as absent: chest pain" in breakdown["key_findings"]
    assert any("Discuss the alerts" in step for step in breakdown["recommendations"])


def test_lists_are_capped_and_unique():
    text = " ".join(f"Glucose {value} mg/dL." for value in range(100, 130))
    findings = build_breakdown(text)["key_findings"]
    assert len(findings) == 8 and len(set(findings)) == 8
