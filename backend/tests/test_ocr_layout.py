"""Numbers OCR was unsure of (services/ocr_layout.py) and how the report rules treat them."""

import pytest

from services import report_service
from services.ocr_layout import UNCERTAIN_BELOW, uncertain_values
from services.rule_validation_service import validate_medical_rules

ROWS = [
    {"page": 1, "text": "Hemoglobin 9.5 g/dL 12-17.5", "cells": [
        {"text": "Hemoglobin", "score": 0.99}, {"text": "9.5", "score": 0.62},
        {"text": "g/dL", "score": 0.97}, {"text": "12-17.5", "score": 0.98}]},
    {"page": 1, "text": "Platelets 230 x10^9/L", "cells": [
        {"text": "Platelets", "score": 0.99}, {"text": "230", "score": 0.95}, {"text": "x10^9/L", "score": 0.93}]},
    {"page": 1, "text": "Creatinine : 1.9 mg/dL", "cells": [
        {"text": "Creatinine :", "score": 0.97}, {"text": "1.9", "score": 0.8}, {"text": "mg/dL", "score": 0.96}]},
    {"page": 1, "text": "Comments attached", "cells": [{"text": "Comments attached", "score": 0.4}]},
]  # fmt: skip
TEXT = "Hemoglobin 9.5 g/dL 12-17.5\nPlatelets 230 x10^9/L\nCreatinine: 1.9 mg/dL\nComments attached"


def test_numbers_below_the_threshold_are_listed_as_read():
    found = uncertain_values(TEXT, ROWS)
    assert [(v["text"], v["score"]) for v in found] == [("9.5", 0.62), ("1.9", 0.8)]
    assert UNCERTAIN_BELOW == 0.90


def test_the_stored_texts_cleaning_does_not_hide_an_uncertain_number():
    # "Creatinine : 1.9" is stored as "Creatinine: 1.9" after cleaning; the row still matches.
    assert "1.9" in [v["text"] for v in uncertain_values(TEXT, ROWS)]


def test_a_line_the_patient_corrected_is_no_longer_uncertain_but_the_others_stay():
    edited = TEXT.replace("Hemoglobin 9.5 g/dL", "Hemoglobin 9.8 g/dL")
    assert [v["text"] for v in uncertain_values(edited, ROWS)] == ["1.9"]


def test_digital_pages_have_no_rows_and_nothing_uncertain():
    assert uncertain_values(TEXT, []) == []


BASE = (
    "Patient report reviewed in clinic today with routine laboratory panel attached for follow up. "
    "Allergies: none known. Doctor notes are attached below for reference."
)


def test_an_uncertain_number_makes_the_report_at_least_caution_never_no_rule_alerts():
    uncertain = [{"page": 1, "line": "Platelets 230 x10^9/L", "text": "230", "score": 0.7}]
    result = validate_medical_rules(f"{BASE} Platelets 230 x10^9/L.", uncertain_values=uncertain)
    assert result["status"] == "CAUTION"
    codes = {w["code"] for w in result["warnings"]}
    assert "UNCERTAIN_OCR_VALUES" in codes and "NO_RULE_ALERTS" not in codes
    [warning] = [w for w in result["warnings"] if w["code"] == "UNCERTAIN_OCR_VALUES"]
    assert "230" in warning["message"] and "against the original report" in warning["message"]


def test_without_uncertain_numbers_nothing_changes():
    assert validate_medical_rules(BASE, uncertain_values=[])["status"] == "SAFE"


@pytest.mark.anyio
async def test_each_analysis_recomputes_the_list_from_the_current_text(monkeypatch):
    seen = {}

    async def fake_pipeline(**kwargs):
        seen["uncertain"] = kwargs["uncertain_values"]
        raise RuntimeError("stop here")  # the fallback path still stores the list

    monkeypatch.setattr(report_service, "run_report_ai_pipeline", fake_pipeline)
    ocr_result = {"cleaned_text": TEXT, "formatted_text": TEXT, "structured_data_json": {"ocr_rows": ROWS}}
    await report_service.analyze_report_result(ocr_result, "Lab")
    assert [v["text"] for v in seen["uncertain"]] == ["9.5", "1.9"]
    assert ocr_result["structured_data_json"]["uncertain_values"] == seen["uncertain"]


def test_a_printed_reference_range_is_not_an_uncertain_value():
    rows = [
        {"page": 1, "text": "ALT 62 U/L < 56", "cells": [
            {"text": "ALT", "score": 0.99}, {"text": "62", "score": 0.97}, {"text": "U/L", "score": 0.95},
            {"text": "< 56", "score": 0.7}]},
        {"page": 1, "text": "Urea 30 mg/dL 15 - 45", "cells": [
            {"text": "Urea", "score": 0.99}, {"text": "30", "score": 0.85}, {"text": "mg/dL", "score": 0.95},
            {"text": "15 - 45", "score": 0.6}]},
    ]  # fmt: skip
    text = "ALT 62 U/L < 56\nUrea 30 mg/dL 15 - 45"
    assert [v["text"] for v in uncertain_values(text, rows)] == ["30"]
