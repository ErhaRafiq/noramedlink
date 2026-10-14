"""A patient's identity never reaches extracted entities, summaries, AI prompts or SQL error logs."""

import json
import re

import pytest

from database import engine
from services import biobert_service, nlp_service, report_ai_pipeline
from services.openai_service import OpenAIResult
from services.privacy import REMOVED, identity_patterns, redact_identifiers

NAME, PHONE, CNIC = "Irha Rafiq", "0300-1234567", "12345-1234567-1"
IDENTITY = identity_patterns(NAME, PHONE, CNIC)
LEAKS = ("irha", "rafiq", "1234567", "12345-1234567-1")

# A report header as OCR reads it: labelled, unlabelled, titled and run-together forms of the name.
REPORT = (
    "IDC  Irha Rafiq  IMAGING & LAB SERVICES\n"
    "Patient Name: Irha Rafiq | Age/Sex: 23 Y / F\n"
    "Miss. Irha Rafiq  MRN: K-4-43102  CNIC: 12345-1234567-1  Phone: 0300 1234567\n"
    "irharafiq IRHA RAFIQ\n"
    "Hemoglobin 10.2 g/dL. Creatinine 1.9 mg/dL. History of diabetes. Allergies: none known.\n"
    "IMPRESSION: Mild anaemia. Raised creatinine.\n"
)


def assert_no_identity(label: str, value) -> None:
    text = json.dumps(value, default=str).lower() if not isinstance(value, str) else value.lower()
    for leak in LEAKS:
        assert leak not in text, f"{label} contains the patient's identity ({leak!r})"


# --- the patterns -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["Irha Rafiq", "IRHA RAFIQ", "irharafiq", "Irha  Rafiq", "Irha.Rafiq", "Rafiq", "Irha"]
)
def test_every_form_of_the_name_is_removed(text):
    assert redact_identifiers(text, IDENTITY) == REMOVED


@pytest.mark.parametrize("text", ["0300 1234567", "0300-1234567", "03001234567", "12345-1234567-1", "1234512345671"])
def test_phone_and_cnic_are_removed_with_any_separators(text):
    assert REMOVED in redact_identifiers(text, IDENTITY) and "1234567" not in redact_identifiers(text, IDENTITY)


def test_medical_text_and_other_names_stay():
    text = "Hemoglobin 10.2 g/dL, Ref. Dr. Faridullah Shah, Rafiqi (not the patient)"
    assert redact_identifiers(text, IDENTITY) == text


def test_titles_and_common_name_words_are_not_removed_on_their_own():
    patterns = identity_patterns("Muhammad Ali Khan")
    assert redact_identifiers("Khan Research Lab, Muhammad", patterns) == "Khan Research Lab, Muhammad"
    assert redact_identifiers("Ali", patterns) == REMOVED


# --- the whole report pipeline ------------------------------------------------------------------


class LeakyNer:
    """A worst-case entity model: tags every capitalised word (so the name too) and non-medical labels."""

    def __call__(self, text):
        found = [
            {"word": w.lower(), "entity_group": "Disease_disorder", "score": 0.99}
            for w in re.findall(r"[A-Z][a-z]+", text)
        ]
        return [*found, {"word": "23 y / f", "entity_group": "Age", "score": 0.99}]


@pytest.fixture
def leaky_world(monkeypatch):
    """BioBERT replaced by LeakyNer; the AI echoes its whole prompt back, so anything sent would show."""
    prompts: list[str] = []

    async def echo_text(instructions, prompt):
        prompts.append(prompt)
        return OpenAIResult(text=prompt, provider="gemini")

    async def echo_json(instructions, prompt):
        prompts.append(prompt)
        return OpenAIResult(text=prompt, data={"summary": prompt, "key_findings": [prompt]}, provider="gemini")

    monkeypatch.setattr(biobert_service, "_load_pipeline", lambda: LeakyNer())
    monkeypatch.setattr(report_ai_pipeline, "generate_openai_text", echo_text)
    monkeypatch.setattr(report_ai_pipeline, "generate_openai_json", echo_json)
    monkeypatch.setattr(nlp_service, "generate_openai_text", echo_text)
    return prompts


@pytest.mark.anyio
async def test_report_pipeline_keeps_identity_out_of_entities_summaries_and_prompts(leaky_world):
    fields = {"patient_name": NAME, "hemoglobin": "10.2 g/dL", "phone": PHONE}
    result = await report_ai_pipeline.run_report_ai_pipeline(
        cleaned_text=REPORT,
        formatted_text=REPORT,
        structured_payload={"fields": fields},
        department_name="Lab",
        identity=IDENTITY,
    )
    assert leaky_world, "the AI stub was not called"
    assert_no_identity("AI prompts", leaky_world)
    assert_no_identity("entities", result["entities"])
    assert_no_identity("clinical entities", result["clinical_entities"])
    assert_no_identity("clinical summary", result["clinical_summary_json"])
    assert_no_identity("patient summary", result["patient_summary"])
    assert_no_identity("rule warnings", result["rule_warnings"])
    assert {e["label"] for e in result["entities"]} <= biobert_service.MEDICAL_LABELS  # no "Age"
    # The medical content is still there.
    assert "creatinine" in json.dumps(result["entities"]).lower() or "1.9" in json.dumps(
        result["clinical_summary_json"]
    )


@pytest.mark.anyio
async def test_report_pipeline_without_ai_keeps_identity_out_of_rule_based_summaries(monkeypatch):
    async def no_ai(instructions, prompt):
        return OpenAIResult(error="No LLM provider configured.")

    monkeypatch.setattr(biobert_service, "_load_pipeline", lambda: LeakyNer())
    monkeypatch.setattr(report_ai_pipeline, "generate_openai_text", no_ai)
    monkeypatch.setattr(report_ai_pipeline, "generate_openai_json", no_ai)
    result = await report_ai_pipeline.run_report_ai_pipeline(
        cleaned_text=REPORT, formatted_text=REPORT, structured_payload={}, department_name="Lab", identity=IDENTITY
    )
    assert result["summary_source"] == "rule_based"
    for key in ("entities", "clinical_summary_json", "summary_text", "patient_summary"):
        assert_no_identity(key, result[key])


@pytest.mark.anyio
async def test_summarize_page_prompt_has_no_identity(leaky_world):
    await nlp_service.summarize_with_optional_llm(REPORT, "medical-report", IDENTITY)
    assert_no_identity("summarize prompt", leaky_world)


def test_biobert_keeps_only_medical_whole_words(monkeypatch):
    raw = [
        {"word": "creatinine", "entity_group": "Lab_value", "score": 0.9},
        {"word": "##tinine", "entity_group": "Lab_value", "score": 0.9},
        {"word": "mc", "entity_group": "Diagnostic_procedure", "score": 0.9},
        {"word": "lahore", "entity_group": "Nonbiological_location", "score": 0.9},
        {"word": "23 y / f", "entity_group": "Age", "score": 0.9},
        {"word": "cnic", "entity_group": "Diagnostic_procedure", "score": 0.9},
        {"word": "mri", "entity_group": "Diagnostic_procedure", "score": 0.9},
    ]
    monkeypatch.setattr(biobert_service, "_load_pipeline", lambda: (lambda text: raw))
    entities = biobert_service._run_biobert("any text")
    assert [(e["text"], e["label"]) for e in entities] == [("creatinine", "Lab Value"), ("mri", "Procedure")]


def test_sql_errors_are_logged_without_their_values():
    assert engine.hide_parameters is True


@pytest.mark.anyio
async def test_numbers_ocr_was_unsure_of_are_listed_without_the_patients_identity(monkeypatch):
    from types import SimpleNamespace

    from services import report_service

    async def stop(**kwargs):
        raise RuntimeError("only the list is checked here")

    monkeypatch.setattr(report_service, "run_report_ai_pipeline", stop)
    header = f"Patient Name: {NAME} Age 44 Phone {PHONE}"
    rows = [
        {"page": 1, "text": header, "cells": [{"text": header, "score": 0.7}]},
        {"page": 1, "text": "Creatinine 1.9 mg/dL", "cells": [
            {"text": "Creatinine", "score": 0.99}, {"text": "1.9", "score": 0.8}, {"text": "mg/dL", "score": 0.97}]},
    ]  # fmt: skip
    text = f"{header}\nCreatinine 1.9 mg/dL"
    patient = SimpleNamespace(full_name=NAME, phone=PHONE, cnic=CNIC)
    ocr_result = {"cleaned_text": text, "formatted_text": text, "structured_data_json": {"ocr_rows": rows}}
    await report_service.analyze_report_result(ocr_result, "Lab", patient)
    listed = ocr_result["structured_data_json"]["uncertain_values"]
    assert [v["text"] for v in listed] == ["1.9"]
    assert_no_identity("uncertain values", listed)
