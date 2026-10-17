"""A report explained for the patient (services/report_explainer.py): where each result sits, the wording, what
the question box will and will not answer, and the guards on AI wording. No network: the AI is faked."""

import asyncio

import pytest

from services import report_explainer as explainer
from services.ai_client import AiResult
from services.icse.entities import extract_entities
from services.lab_rules import RULES

CBC = "Hemoglobin 10.8 g/dL\nWBC Count 7.5 x10^9/L\nPlatelet Count 250 x10^9/L\n"
KIDNEY = "Creatinine 2.4 mg/dL\neGFR 25 mL/min/1.73m2\nPotassium 4.2 mmol/L\n"


def explain(text: str, validation: dict | None = None) -> dict:
    return explainer.build_explanation(text, extract_entities(text), validation or {})


def result(explanation: dict, name: str) -> dict:
    return next(r for r in explanation["results"] if r["medical_name"] == name)


# --- the explanation -----------------------------------------------------------------------------------


def test_a_low_result_says_where_it_sits_what_the_test_is_and_what_low_can_mean():
    hb = result(explain(CBC), "Hemoglobin")
    assert hb["position"] == "below" and hb["printed"] == "10.8 g/dL"
    assert hb["where"] == "Lower than the usual range (12 to 17.5 g/dL)."
    assert hb["name"] == "Oxygen-carrying blood protein" and "carries oxygen" in hb["what_it_is"]
    assert "anaemia" in hb["meaning"] and "low iron" in hb["meaning"]
    assert hb["gauge"] == {"min": 0.0, "max": 21.88, "low": 12.0, "high": 17.5, "value": 10.8}


def test_a_result_inside_the_range_is_not_called_normal_or_safe():
    wbc = result(explain(CBC), "WBC Count")
    assert wbc["position"] == "within" and wbc["meaning"] is None and not wbc["urgent"]
    assert wbc["where"].startswith("Inside the usual range the app uses")
    assert "normal" not in wbc["where"].lower() and "safe" not in wbc["where"].lower()


def test_the_headline_counts_what_it_can_read_and_never_calls_the_report_fine():
    text = explain(CBC)["headline"]
    assert "3 results" in text and "1 lower than the usual range and 2 inside it" in text
    assert "worth showing to your doctor" in text
    all_inside = explain("WBC Count 7.5 x10^9/L\nPlatelet Count 250 x10^9/L\n")["headline"]
    assert "all of them are inside the usual range" in all_inside and "does not mean everything is fine" in all_inside


def test_a_result_far_from_the_range_says_to_call_the_doctor_soon_and_1122_if_unwell():
    potassium = result(explain("Potassium 7.2 mmol/L\n"), "Potassium")
    assert (
        potassium["urgent"]
        and "contact your doctor soon" in potassium["urgent_note"]
        and "1122" in potassium["urgent_note"]
    )


def test_an_unreadable_value_is_not_compared_or_drawn():
    entity = {"type": "test_result", "name": "Hemoglobin", "value": "[?]", "readable": False}
    explanation = explainer.build_explanation("", [entity], {})
    item = explanation["results"][0]
    assert (
        item["position"] == "unreadable"
        and item["gauge"] is None
        and "check it against your printed report" in item["where"]
    )
    assert "could not read" in explanation["headline"]


def test_a_report_mark_that_differs_from_the_apps_range_is_explained_not_hidden():
    entity = {
        "type": "test_result",
        "name": "Hemoglobin",
        "value": "12.5",
        "unit": "g/dL",
        "report_flag": "L",
        "readable": True,
    }
    item = explainer.build_explanation("", [entity], {})["results"][0]
    assert item["position"] == "within" and item["report_mark"] == "low"
    assert "marks this as low" in item["note"] and "go by the one on your report" in item["note"]


def test_a_test_the_app_has_no_range_for_says_so():
    entity = {"type": "test_result", "name": "Vitamin D", "value": "18", "unit": "ng/mL", "readable": True}
    item = explainer.build_explanation("", [entity], {})["results"][0]
    assert item["position"] == "unknown" and "no usual range" in item["where"] and item["gauge"] is None


def test_no_values_in_the_report_is_said_plainly():
    assert "did not find test values" in explainer.build_explanation("", [], {})["headline"]


def test_tests_doctors_read_together_get_one_careful_note_only_when_the_pattern_is_there():
    both = explain(KIDNEY)["insights"]
    assert [i["title"] for i in both] == ["Your kidney tests"] and "usually read them together" in both[0]["text"]
    assert explain("Creatinine 2.4 mg/dL\neGFR 85 mL/min/1.73m2\n")["insights"] == []


def test_the_questions_for_the_doctor_follow_the_results():
    questions = explain(CBC)["questions"]
    assert "What do these results mean for my health?" in questions
    assert any("lower than usual" in q for q in questions) and "When should I have these tests again?" in questions


def test_every_explanation_carries_the_machine_note():
    note = explain(CBC)["disclaimer"]
    assert (
        "written by a computer program, not by a doctor" in note
        and "can be wrong" in note
        and "check anything that matters with your doctor" in note
    )


def test_every_test_the_rules_grade_has_wording_for_higher_and_lower():
    missing = [name for name in RULES if name not in explainer._meanings()]
    assert missing == []
    for row in explainer._meanings().values():
        assert row["higher"].endswith(".") and row["lower"].endswith(".")
        assert "you have been diagnosed" not in (row["higher"] + row["lower"]).lower()  # general meanings only


# --- the question box ----------------------------------------------------------------------------------


def ask(question: str, text: str = CBC + KIDNEY, topic: str | None = None) -> dict:
    return explainer.rule_answer(question, explain(text), topic)


def test_emergency_words_get_the_1122_message_and_nothing_else():
    for question in ("I have chest pain and cannot breathe", "my father fainted and has slurred speech"):
        answer = ask(question)
        assert answer["emergency"] and answer["intent"] == "emergency" and "1122" in answer["answer"]
        assert answer["followups"] == [] and answer["topics"] == []


@pytest.mark.parametrize(
    "question",
    [
        "What medicine should I take?",
        "what dose of iron do I need",
        "should I stop taking my tablets",
        "what should I eat for this",
        "is there a cure",
    ],
)
def test_treatment_medicine_dose_and_diet_questions_are_refused(question):
    answer = ask(question)
    assert answer["intent"] == "treatment" and "cannot give advice about treatment" in answer["answer"]
    assert "ask" in answer["answer"].lower() or "your doctor" in answer["answer"]


@pytest.mark.parametrize(
    "question", ["Do I have anaemia?", "am I diabetic", "is it kidney failure", "what is wrong with me"]
)
def test_a_question_asking_for_a_diagnosis_is_not_answered_with_one(question):
    answer = ask(question)
    assert (
        answer["intent"] == "diagnosis" and "cannot tell you whether you have a particular illness" in answer["answer"]
    )
    assert (
        "only a doctor can" in answer["answer"] and "Hemoglobin" not in answer["answer"].split("only a doctor can")[0]
    )


def test_asking_about_a_result_by_name_explains_it_fully():
    answer = ask("What is my hemoglobin?")
    assert answer["intent"] == "result" and answer["topics"] == ["hemoglobin"]
    text = answer["answer"]
    assert "What it is:" in text and "Your result: 10.8 g/dL" in text and "Lower than the usual range" in text
    assert "What this can mean:" in text and "only your doctor can tell which applies to you" in text


def test_the_short_form_on_the_report_finds_the_result_too():
    assert ask("what does Hb mean")["topics"] == ["hemoglobin"]


def test_explain_more_on_a_result_uses_its_key():
    answer = ask("Explain this in more detail", topic="creatinine")
    assert answer["topics"] == ["creatinine"] and "kidneys" in answer["answer"]


def test_two_results_in_one_question_are_both_explained():
    assert ask("compare creatinine and potassium")["topics"] == ["creatinine", "potassium"]


def test_a_worried_question_is_met_without_judging_how_serious_it_is():
    answer = ask("is this serious? I am worried", text=CBC)
    assert (
        answer["intent"] == "severity"
        and "I cannot tell how serious this is for you" in answer["answer"]
        and "1122" in answer["answer"]
    )


def test_a_worried_question_with_a_far_out_result_says_to_call_the_doctor_soon():
    answer = ask("is it dangerous?", text="Potassium 7.2 mmol/L\n")
    assert "far from the usual range" in answer["answer"] and "contact your doctor soon" in answer["answer"]


def test_an_overall_question_gives_the_headline_the_outside_results_and_the_patterns():
    answer = ask("what does my report say overall?")
    assert (
        answer["intent"] == "summary"
        and "Results outside the usual range" in answer["answer"]
        and "Your kidney tests" in answer["answer"]
    )


def test_a_question_that_names_nothing_in_the_report_says_what_it_can_do():
    answer = ask("tell me a joke")
    assert answer["intent"] == "unknown" and "I can only explain what is in this report" in answer["answer"]
    assert "hemoglobin" not in answer["answer"].lower() or "oxygen-carrying" in answer["answer"].lower()


def test_questions_for_the_doctor_can_be_asked_for():
    answer = ask("what should I ask my doctor?")
    assert answer["intent"] == "doctor_questions" and "- What do these results mean for my health?" in answer["answer"]


def test_every_answer_offers_something_to_ask_next():
    for question in ("what is my hemoglobin", "what medicine should I take", "overall", "is it serious", "hello there"):
        assert ask(question)["followups"], question


def test_a_name_that_is_not_a_test_does_not_match_inside_a_word():
    assert ask("my sodium")["topics"] == []  # sodium is not in this report
    assert ask("hemoglobinuria")["topics"] == []


# --- AI wording and its guards --------------------------------------------------------------------------


def run(question: str, text: str, generate, history=None, topic=None) -> dict:
    return asyncio.run(explainer.answer_question(question, explain(text), history, topic, generate=generate))


def fake(text: str | None, provider: str = "fake"):
    seen = {}

    async def generate(instructions: str, prompt: str) -> AiResult:
        seen.update(instructions=instructions, prompt=prompt)
        return AiResult(text=text, provider=provider) if text else AiResult(error="no key")

    generate.seen = seen
    return generate


def test_without_an_ai_the_answer_is_the_rule_answer():
    answer = run("what is my hemoglobin", CBC, fake(None))
    assert answer["source"] == "rules" and "Your result: 10.8 g/dL" in answer["answer"]


def test_a_safe_ai_wording_replaces_the_rule_wording_and_says_where_it_came_from():
    nice = "Your oxygen-carrying blood protein (hemoglobin) is 10.8 g/dL, which is lower than the usual range. Ask your doctor about it."
    generate = fake(nice, provider="gemini")
    answer = run("what is my hemoglobin", CBC, generate)
    assert answer["answer"] == nice and answer["source"] == "gemini"
    prompt = generate.seen["prompt"]
    assert "what is my hemoglobin" in prompt and "10.8 g/dL" in prompt and "use only its facts" in prompt
    assert (
        "not a doctor" in generate.seen["instructions"] and "do not diagnose" in generate.seen["instructions"].lower()
    )


def test_an_ai_answer_with_an_invented_number_is_thrown_away():
    answer = run("what is my hemoglobin", CBC, fake("Your hemoglobin is 10.8 g/dL and should be 13.5 g/dL."))
    assert answer["source"] == "rules" and "13.5" not in answer["answer"]


@pytest.mark.parametrize(
    "bad",
    [
        "You have anaemia and need iron.",
        "You should take iron tablets every day.",
        "This is normal, do not worry.",
        "As a doctor I think this is fine.",
        "Take 2 tablets daily.",
        "This is safe.",
        "x" * 1600,
    ],
)
def test_an_ai_answer_that_diagnoses_advises_or_reassures_is_thrown_away(bad):
    assert run("what is my hemoglobin", CBC, fake(bad))["source"] == "rules"


@pytest.mark.parametrize("question", ["I have chest pain", "what medicine should I take", "do I have anaemia"])
def test_an_emergency_a_refusal_and_a_diagnosis_question_never_reach_the_ai(question):
    async def generate(instructions, prompt):
        raise AssertionError("the AI was asked")

    answer = run(question, CBC, generate)
    assert answer["source"] == "rules"


def test_the_conversation_so_far_goes_to_the_ai_but_only_the_last_turns():
    generate = fake(None)
    history = [{"role": "patient", "text": f"question {n}"} for n in range(10)]
    run("explain more", CBC, generate, history=history)
    prompt = generate.seen["prompt"]
    assert "question 9" in prompt and "question 3" not in prompt
