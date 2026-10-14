"""Each value carries its OCR confidence, and the report and the summary treat it the same way."""

from services.icse.entities import extract_entities
from services.icse.flags import build_flags
from services.rule_validation_service import validate_medical_rules

BASE = (
    "Patient report reviewed in clinic today with routine laboratory panel attached for follow up. "
    "Allergies: none known. Doctor notes are attached below for reference."
)


def row(*cells):
    return {
        "page": 1,
        "text": " ".join(text for text, _ in cells),
        "cells": [{"text": t, "score": s} for t, s in cells],
    }


ROWS = [
    row(("Hemoglobin", 0.99), ("6.8", 0.62), ("g/dL", 0.97), ("12-17.5", 0.98)),  # very low, but unsure
    row(("Creatinine", 0.99), ("2.4", 0.97), ("mg/dL", 0.71)),  # sure number, unsure unit
    row(("Potassium", 0.99), ("5.9", 0.96), ("mmol/L", 0.95)),  # sure
    row(("Tab", 0.98), ("Metformin", 0.97), ("500", 0.55), ("mg", 0.96), ("BD", 0.95)),  # unsure dose
]
TEXT = "\n".join(r["text"] for r in ROWS)
UNCERTAIN = [{"page": 1, "line": r["text"], "text": c["text"], "score": c["score"]}
             for r in ROWS for c in r["cells"] if c["score"] < 0.9 and any(ch.isdigit() for ch in c["text"])]  # fmt: skip


def by_name(entities):
    return {e["name"]: e for e in entities if e["type"] == "test_result"}


def test_a_values_confidence_is_the_lowest_of_its_number_and_unit_cells():
    values = by_name(extract_entities(TEXT, ocr_rows=ROWS))
    assert values["Hemoglobin"]["confidence"] == 0.62
    assert values["Creatinine"]["confidence"] == 0.71  # the unit was unsure
    assert values["Potassium"]["confidence"] == 0.95
    assert all(v["read_by"] == "ocr" for v in values.values())


def test_a_low_confidence_value_is_never_judged_in_the_report_or_the_summary():
    result = validate_medical_rules(f"{BASE}\n{TEXT}", uncertain_values=UNCERTAIN, ocr_rows=ROWS)
    codes = [w["code"] for w in result["warnings"]]
    assert "HEMOGLOBIN_LOW" not in codes and "KIDNEY_RISK_CREATININE" not in codes  # not judged as read
    assert codes.count("VALUE_NEEDS_CHECK") == 2
    assert "POTASSIUM_HIGH" in codes  # a sure value is judged

    flags = build_flags([{"report_id": 1, "date": None, "entities": extract_entities(TEXT, ocr_rows=ROWS)}])
    assert {f["subject"] for f in flags["flags"] if f["kind"] == "result"} == {"Potassium"}
    assert {c["subject"] for c in flags["check_original"]} == {"Hemoglobin", "Creatinine"}
    assert all("low confidence" in c["reason"] for c in flags["check_original"])


def test_other_uncertain_numbers_are_still_listed_once():
    result = validate_medical_rules(f"{BASE}\n{TEXT}", uncertain_values=UNCERTAIN, ocr_rows=ROWS)
    [warning] = [w for w in result["warnings"] if w["code"] == "UNCERTAIN_OCR_VALUES"]
    assert warning["message"].startswith("1 number(s)") and "500" in warning["message"]  # the dose only


def test_a_line_the_patient_corrected_is_read_as_text_and_judged():
    edited = TEXT.replace("Hemoglobin 6.8 g/dL", "Hemoglobin 6.9 g/dL")
    hemoglobin = by_name(extract_entities(edited, ocr_rows=ROWS))["Hemoglobin"]
    assert hemoglobin["read_by"] == "text" and hemoglobin["confidence"] is None
    codes = [w["code"] for w in validate_medical_rules(f"{BASE}\n{edited}", ocr_rows=ROWS)["warnings"]]
    assert "HEMOGLOBIN_LOW" in codes


def test_without_ocr_rows_nothing_changes():
    values = by_name(extract_entities(TEXT))
    assert all(v["confidence"] is None and "read_by" not in v for v in values.values())
