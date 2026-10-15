"""Everyday wording in patient-facing text (services/plain_language.py, services/patient_summary.py)."""

import re

import pytest

from services import knowledge, report_ai_pipeline
from services.ai_client import AiResult
from services.icse.entities import extract_entities
from services.knowledge.tables import records
from services.patient_summary import build_patient_summary
from services.plain_language import (
    find_terms,
    glossary,
    patient_message,
    rewrite,
    rewrite_sections,
    unexplained_terms,
)
from services.report_service import conditions_mentioned
from services.rule_validation_service import validate_medical_rules

TERMS = records("plain_terms")
SOURCES = {row["key"] for row in records("sources")}
# Names the app knows that are already everyday words.
EVERYDAY = {"asthma", "stroke", "gout", "obesity", "depression", "migraine", "dengue", "typhoid fever",
            "Vitamin D", "Vitamin B12", "HIV disease"}  # fmt: skip


# --- the dictionary -------------------------------------------------------------------------------


def test_every_entry_is_complete_and_sourced():
    for entry in TERMS:
        assert entry["aliases"] or entry["abbreviations"]
        assert entry["plain"] and entry["explain"].endswith(".")
        assert entry["source"] in SOURCES
        text = (entry["plain"] + " " + entry["explain"]).lower()
        assert " safe" not in text and "normal" not in text


def test_everyday_wording_never_needs_explaining_itself():
    for entry in TERMS:
        assert unexplained_terms(entry["plain"]) == [], entry["plain"]
        assert unexplained_terms(entry["explain"]) == [], entry["explain"]


@pytest.mark.parametrize("kind", ["lab", "condition"])
def test_every_test_and_condition_the_app_knows_has_everyday_wording(kind):
    data = knowledge._load("lab_tests" if kind == "lab" else "conditions")
    names = [t["name"] for t in data["tests" if kind == "lab" else "conditions"]]
    missing = [n for n in names if n not in EVERYDAY and not find_terms(n)]
    assert missing == []


def test_one_letter_and_ambiguous_abbreviations_are_not_in_the_dictionary():
    abbreviations = {a for e in TERMS for a in e["abbreviations"]}
    assert all(len(a) > 1 for a in abbreviations)
    assert "RA" not in abbreviations  # rheumatoid arthritis or right atrium


# --- rewriting ------------------------------------------------------------------------------------


def test_the_term_is_kept_once_in_brackets_then_everyday_words_only():
    text = rewrite("Creatinine 2.4 mg/dL. Creatinine was repeated.")
    assert text == "Kidney waste level (Creatinine) 2.4 mg/dL. Kidney waste level was repeated."


def test_numbers_units_negation_and_report_marks_are_untouched():
    original = "No history of HTN. Creatinine 2.4 mg/dL H. eGFR 28 mL/min. Hb 10.2 g/dL L"
    text = rewrite(original)
    assert re.findall(r"\d+(?:\.\d+)?", text) == re.findall(r"\d+(?:\.\d+)?", original)
    assert text.startswith("No history of high blood pressure (HTN).")
    assert "mg/dL H." in text and "g/dL L" in text


def test_abbreviations_must_match_exactly():
    assert rewrite("K/C/O DM.") == "Known to have (K/C/O) diabetes (DM)."
    assert rewrite("dm me later") == "dm me later"
    assert rewrite("Vitamin K was given") == "Vitamin K was given"


def test_rewriting_twice_changes_nothing_more():
    text = "IMPRESSION: Cholelithiasis with mild hepatomegaly. Tab Metformin 500 mg BD. No TB."
    once = rewrite_sections(text)
    assert rewrite_sections(once) == once
    assert unexplained_terms(once) == []


def test_a_term_the_report_already_explains_is_left_alone():
    assert rewrite("Creatinine (waste from muscles) 1.1") == "Creatinine (waste from muscles) 1.1"


def test_section_headings_and_the_word_list_are_not_rewritten():
    text = "Your results explained\n- eGFR 70\nWords you might see\n- eGFR: how well the kidneys filter."
    out = rewrite_sections(text)
    assert out.splitlines() == [
        "Your results explained",
        "- Kidney filtering rate (eGFR) 70",
        "Words you might see",
        "- eGFR: how well the kidneys filter.",
    ]


def test_glossary_lists_each_term_once_with_its_explanation():
    words = glossary("Creatinine 2.4, creatinine again, eGFR 28, hepatomegaly")
    assert [w["term"] for w in words] == ["Creatinine", "eGFR", "hepatomegaly"]
    assert words[0]["explain"].startswith("A waste product")


# --- rule alerts for patients ---------------------------------------------------------------------

BASE = (
    "Patient report reviewed in clinic today with routine laboratory panel attached for follow up. "
    "Allergies: none known. Doctor notes are attached below for reference."
)


def test_every_rule_alert_has_everyday_wording_and_urgent_ones_say_so():
    result = validate_medical_rules(f"{BASE}\nCreatinine 2.4 mg/dL\neGFR 25 mL/min\nRandom Blood Sugar 30")
    messages = {w["code"]: w["patient_message"] for w in result["warnings"]}
    assert messages["KIDNEY_RISK_CREATININE"] == (
        "Your kidney waste level (Creatinine) reading of 2.4 mg/dL is above the range the app checks against. "
        "Please show this to your doctor."
    )
    assert messages["KIDNEY_RISK_EGFR"].endswith("This needs prompt attention from a doctor.")
    assert "could not read one value clearly" in messages["VALUE_NEEDS_CHECK"]
    for message in messages.values():
        assert " safe" not in message.lower() and unexplained_terms(message) == []


def test_alerts_saved_before_patient_wording_existed_get_it():
    assert patient_message({"code": "MISSING_ALLERGY_DATA", "severity": "CAUTION"}).startswith(
        "The report does not say whether you have any allergies"
    )


# --- the patient summary (no AI) ------------------------------------------------------------------

REPORT = (
    "Collected: 10-Jan-2026\nHemoglobin 9.1 g/dL 12 - 17.5 L\nCreatinine 2.4 mg/dL 0.6 - 1.3 H\n"
    "Potassium [?] mmol/L\nKnown case of DM and HTN. No history of TB. Family history of IHD.\n"
    "Tab Glucophage 500 mg BD\nIMPRESSION: Mild hepatomegaly."
)


def summary_for(text=REPORT):
    validation = validate_medical_rules(f"{BASE}\n{text}")
    return build_patient_summary(text, extract_entities(text), validation, "Lab", "Mild hepatomegaly.")


def test_the_rule_based_summary_has_the_plain_sections_and_no_jargon_left():
    summary = summary_for()
    for heading in ("What this report is", "Your results explained", "What may need attention",
                    "Conditions mentioned in your report", "Medicines mentioned in your report",
                    "Words you might see", "Questions to ask your doctor"):  # fmt: skip
        assert heading in summary.splitlines()
    assert unexplained_terms(summary) == []
    assert summary.endswith("Please consult your doctor for proper diagnosis and treatment.")


def test_results_keep_the_reports_values_and_marks_and_say_when_unreadable():
    summary = summary_for()
    assert "- Oxygen-carrying blood protein (Hemoglobin): 9.1 g/dL. The report marks it as low." in summary
    assert "- Kidney waste level (Creatinine): 2.4 mg/dL. The report marks it as high." in summary
    assert "could not be read clearly" in summary
    numbers = set(re.findall(r"\d+(?:\.\d+)?", summary))
    assert numbers <= set(re.findall(r"\d+(?:\.\d+)?", REPORT)) | {"3"}  # "about 3 months" in a word list


def test_conditions_are_mentioned_not_diagnosed_and_family_or_negated_ones_are_left_out():
    summary = summary_for()
    section = summary.split("Conditions mentioned in your report")[1].split("\n\n")[0]
    assert "- Diabetes (diabetes mellitus) (a long-term condition)" in section
    assert "- High blood pressure (hypertension)" in section
    assert "TB" not in section and "heart disease" not in section
    assert "the app does not diagnose" in section


def test_attention_lists_urgent_alerts_first():
    summary = summary_for("eGFR 20 mL/min\nCreatinine 2.4 mg/dL")
    attention = summary.split("What may need attention")[1].split("\n\n")[0].strip().splitlines()
    assert attention[0].endswith("This needs prompt attention from a doctor.")


def test_a_report_with_nothing_marked_never_says_normal_or_safe():
    summary = summary_for("Hemoglobin 14.0 g/dL")
    assert "did not mark anything" in summary and "does not mean everything is normal" in summary
    assert " safe" not in summary.lower()


def test_conditions_for_the_report_page():
    entities = extract_entities("K/C/O DM. No history of asthma. Mother has HTN.")
    assert conditions_mentioned(entities) == [{"name": "diabetes mellitus", "plain": "diabetes", "chronic": True}]


# --- the AI path ----------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_ai_gets_the_everyday_words_and_any_jargon_it_leaves_is_rewritten(monkeypatch):
    prompts = []

    async def fake_ai(instructions, prompt):
        prompts.append(prompt)
        return AiResult(text="Your results explained\n- Your eGFR is 28 and creatinine is 2.4.", provider="gemini")

    monkeypatch.setattr(report_ai_pipeline, "generate_text", fake_ai)
    text = "Creatinine 2.4 mg/dL\neGFR 28 mL/min"
    summary, warning, source = await report_ai_pipeline._generate_patient_summary(
        text, "Lab", {}, validate_medical_rules(f"{BASE}\n{text}")
    )
    assert source == "gemini" and warning is None
    assert '- Creatinine: say "kidney waste level"' in prompts[0]
    assert "kidney filtering rate (eGFR) is 28 and kidney waste level (creatinine) is 2.4" in summary
    assert unexplained_terms(summary) == []


@pytest.mark.anyio
async def test_without_a_key_the_plain_rule_based_summary_is_used(monkeypatch):
    async def no_ai(instructions, prompt):
        return AiResult(error="no key")

    monkeypatch.setattr(report_ai_pipeline, "generate_text", no_ai)
    summary, _, source = await report_ai_pipeline._generate_patient_summary(REPORT, "Lab", {}, {"warnings": []})
    assert source == "rule_based" and "Your results explained" in summary and unexplained_terms(summary) == []
