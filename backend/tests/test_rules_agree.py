"""The per-report rules and the clinical-summary flags judge the same values the same way.

Both read values with icse.entities.extract_entities and judge them with lab_rules.assess. These
tests feed the same report text to both and check they agree, value by value: what one flags, the
other flags with the same severity; what one sends to "check against the original report", so does
the other; and a report with "No rule alerts" has no value flag in the summary.
"""

import pytest

from services.icse.entities import extract_entities
from services.icse.flags import build_flags
from services.lab_rules import RULES
from services.rule_validation_service import validate_medical_rules

BASE = (
    "Patient report reviewed in clinic today with routine laboratory panel attached for follow up. "
    "Allergies: none known. Doctor notes are attached below for reference."
)
SEVERITY = {"CAUTION": 1, "HIGH_RISK": 2}


def report_view(text: str, fields=None) -> tuple[dict[str, int], int, str]:
    """Per test: the most severe value warning; plus the number of values to check, and the status."""
    result = validate_medical_rules(f"{BASE}\n{text}", structured_fields=fields)
    by_code: dict[str, int] = {}
    checks = 0
    for warning in result["warnings"]:
        if warning["code"] == "VALUE_NEEDS_CHECK":
            checks += 1
        elif warning["code"] not in {"NO_RULE_ALERTS", "MISSING_ALLERGY_DATA", "INCOMPLETE_OCR_TEXT"}:
            by_code[warning["code"]] = max(by_code.get(warning["code"], 0), SEVERITY[warning["severity"]])
    return by_code, checks, result["status"]


def summary_view(text: str, fields=None) -> tuple[dict[str, int], int]:
    entities = extract_entities(f"{BASE}\n{text}", fields=fields)
    flags = build_flags([{"report_id": 1, "date": None, "entities": entities}])
    codes = {rule.name: rule for rule in RULES.values()}
    by_code: dict[str, int] = {}
    for flag in flags["flags"]:
        if flag["kind"] != "result":
            continue
        direction = flag["code"].removeprefix("RESULT_").lower()
        code = (
            "HYPERTENSION_INDICATOR"
            if flag["subject"] == "Blood Pressure"
            else codes[flag["subject"]].code_for(direction)
        )
        by_code[code] = max(by_code.get(code, 0), SEVERITY[flag["severity"]])
    return by_code, len(flags["check_original"])


def assert_agree(text: str, fields=None) -> None:
    report_codes, report_checks, status = report_view(text, fields)
    summary_codes, summary_checks = summary_view(text, fields)
    assert report_codes == summary_codes, text
    assert report_checks == summary_checks, text
    if status == "SAFE":  # "No rule alerts" on the report: nothing in the summary either
        assert not summary_codes and not summary_checks


def _values_around(rule) -> list[float]:
    points = []
    for limit in (rule.low, rule.high, rule.critical_low, rule.critical_high):
        if limit is not None:
            step = 0.1 if limit < 20 else 1
            points += [limit - step, limit, limit + step]
    return [round(p, 2) for p in points if rule.plausible[0] <= p <= rule.plausible[1]]


@pytest.mark.parametrize("rule", list(RULES.values()), ids=lambda rule: rule.name)
def test_every_threshold_gives_the_same_answer_in_both_places(rule):
    for value in _values_around(rule):
        assert_agree(f"{rule.name} {value:g} {rule.unit}")


@pytest.mark.parametrize(
    "text",
    [
        "Fasting Blood Sugar | 92 | mg/dL | 70 - 100\nRandom Blood Sugar | 230 | mg/dL | < 140",
        "Fasting Blood Sugar 150 mg/dL",  # flagged in both since the thresholds became one (126)
        "Hemoglobin 13.5 g/dL. Repeat Hemoglobin 6.8 g/dL.",
        "Creatinine Clearance 95 mL/min. Serum Creatinine 2.4 mg/dL.",
        "eGFR (MDRD) 70 mL/min. eGFR (CKD-EPI) 25 mL/min.",
        "BP 120/80 mmHg, repeat BP 190/110 mmHg",
        "Hb 135 g/L. Platelet count 2,50,000. TLC 13,200 /cumm",
        "Glucose 7.2, Creatinine 212",  # no unit, one possible reading each
        "Random Blood Sugar 30. Hemoglobin 9.1 %. Creatinine [?] mg/dL. BP 300/20",  # all to check
        "Hb electrophoresis: HbA 97 %, HbA2 2.5 %",
        "Potassium 6.9 mmol/L, Sodium 128 mmol/L, TSH 6.8 mIU/L",
        "No laboratory values in this note.",
    ],
)
def test_real_shaped_reports_agree(text):
    assert_agree(text)


def test_structured_fields_reach_both():
    assert_agree("Glucose 90.", fields={"glucose": "350", "blood_pressure": "150/95"})
    report_codes, _, status = report_view("Glucose 90.", fields={"glucose": "350"})
    assert status == "HIGH_RISK" and report_codes == {"HIGH_GLUCOSE": 2}
