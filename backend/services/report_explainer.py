"""A report explained to the patient who owns it, in everyday words, and answers to their follow-up questions.

What it is: a machine reading of the report's own values against the app's general ranges, with the meaning
of a higher or lower result taken from a reviewed-wording table (services/knowledge/data/lab_meanings.csv, a demo
knowledge base, not clinically reviewed). It is not a doctor and says so on every answer.

What it never does (AGENTS.md section 6):
- diagnose ("you have ..."), say a result is normal or safe, advise treatment, medicines, doses, diet or exercise;
- invent a number: every number comes from the report or from the app's published ranges;
- answer an emergency: words like chest pain or trouble breathing get the 1122 message and nothing else.

How an answer is made: always by fixed rules from the explanation below. When an AI key is configured the AI may only
re-word that answer for a nicer read; it is thrown away (and the rule-based answer used) if it contains a number
that is not in the report, wording that diagnoses or advises treatment, or claims to be a doctor. Nothing is stored,
and the question is not logged: it is medical text.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from functools import cache
from typing import Any

from services import symptom_checker
from services.ai_client import AiResult, generate_text
from services.ai_guard import numbers_not_in_source
from services.knowledge.tables import records
from services.lab_rules import RULES, assess
from services.plain_language import glossary, plain_name, rewrite, short_forms, term_info

MACHINE_NOTE = (
    "This explanation was written by a computer program, not by a doctor. It can be wrong or leave something out. "
    "It explains what the words and numbers in your report usually mean, but it cannot see your health history and "
    "cannot tell you whether you are ill or what to do. Please check anything that matters with your doctor."
)
URGENT_NOTE = (
    "This is well outside the usual range. Please contact your doctor soon instead of waiting for your next visit. "
    "If you feel very unwell, call 1122 or go to the nearest emergency department."
)
EMERGENCY_ANSWER = (
    "Some of the words you used can be signs of an emergency. Please do not wait for an answer here. "
    "Call 1122 or go to the nearest emergency department now."
)
MAX_QUESTION = 500
MAX_HISTORY = 6


@cache
def _meanings() -> dict[str, dict[str, str]]:
    return {row["test"]: row for row in records("lab_meanings")}


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _range_text(name: str) -> str | None:
    if name == "Blood Pressure":
        return "below 140/90 mmHg"
    rule = RULES.get(name)
    if rule is None:
        return None
    if rule.low is not None and rule.high is not None:
        return f"{rule.low:g} to {rule.high:g} {rule.unit}"
    if rule.high is not None:
        return f"up to {rule.high:g} {rule.unit}"
    if rule.low is not None:
        return f"{rule.low:g} or more {rule.unit}"
    return None


def _gauge(name: str, value: float) -> dict[str, float | None] | None:
    """Numbers for the scale drawn under a result: all from the app's range and the reading itself."""
    rule = RULES.get(name)
    if rule is None or (rule.low is None and rule.high is None):
        return None
    top = max(value, rule.high if rule.high is not None else (rule.low or 0) * 2) * 1.25
    return {"min": 0.0, "max": round(top, 2), "low": rule.low, "high": rule.high, "value": round(value, 2)}


def _item(entity: dict[str, Any]) -> dict[str, Any] | None:
    if entity.get("type") not in ("test_result", "vital") or entity.get("method") == "biobert":
        return None
    if entity.get("certainty") == "model suggestion":
        return None
    name = entity["name"]
    printed = " ".join(str(p) for p in (entity.get("value"), entity.get("unit") or "") if p)
    info = term_info(name)
    mark = {"H": "high", "L": "low"}.get(entity.get("report_flag") or "")
    item: dict[str, Any] = {
        "key": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
        "name": _cap(plain_name(name)),
        "medical_name": name,
        "printed": printed or None,
        "report_mark": mark,
        "what_it_is": info.explain if info else None,
        "position": "unknown",
        "range_text": _range_text(name),
        "where": "",
        "meaning": None,
        "urgent": False,
        "urgent_note": None,
        "note": None,
        "gauge": None,
    }
    assessment = assess(entity)
    if not entity.get("readable", True) or not entity.get("value"):
        item["position"] = "unreadable"
        item["where"] = "The app could not read this value clearly. Please check it against your printed report."
        return item
    if assessment is None:  # a test the app has no range for
        item["where"] = (
            f"The report marks it as {mark}."
            if mark
            else "The app has no usual range for this test. Your report may print one next to it."
        )
        return item
    if assessment.problem:
        item["position"] = "unreadable"
        item["where"] = (
            f"The app did not compare this value ({assessment.problem}). Please check it against your printed report."
        )
        return item
    grade = assessment.grade
    range_text = item["range_text"]
    if grade is None:
        item["position"] = "within"
        item["where"] = (
            f"Inside the usual range the app uses ({range_text})."
            if name != "Blood Pressure"
            else "Below the level the app marks as raised (140/90 mmHg)."
        )
    else:
        item["position"] = "above" if grade.direction == "high" else "below"
        word = "Higher" if grade.direction == "high" else "Lower"
        item["where"] = (
            f"{word} than the usual range ({range_text})." if range_text else f"{word} than the usual range."
        )
        row = _meanings().get(name)
        if row:
            item["meaning"] = row["higher" if grade.direction == "high" else "lower"]
        if grade.severity == "HIGH_RISK":
            item["urgent"], item["urgent_note"] = True, URGENT_NOTE
    if mark and ((mark == "high") != (item["position"] == "above") or item["position"] == "within"):
        item["note"] = (
            f"Your report marks this as {mark}, which is not the same as the app's general range. Labs print their own "
            "ranges, so your doctor will go by the one on your report."
        )
    if assessment.unit_note:
        item["note"] = " ".join(
            filter(None, [item["note"], f"The report printed no unit; the app read it as: {assessment.unit_note}."])
        )
    if isinstance(assessment.value, (int, float)) and name != "Blood Pressure":
        item["gauge"] = _gauge(name, float(assessment.value))
    return item


# Results that doctors usually read together: a short, careful note when the pattern is there.
_INSIGHTS: list[tuple[str, Callable[[dict[str, str]], bool], str]] = [
    (
        "Your kidney tests",
        lambda p: p.get("Creatinine") == "above" and p.get("eGFR") == "below",
        "Creatinine is higher and eGFR is lower than the usual range. These two tests both look at how well your kidneys "
        "filter your blood, and doctors usually read them together. Ask your doctor whether your kidneys need a closer look.",
    ),
    (
        "Your blood sugar",
        lambda p: any(
            p.get(t) == "above"
            for t in ("Fasting Blood Sugar", "Random Blood Sugar", "Post Prandial Blood Sugar", "Blood Glucose")
        )
        and p.get("HbA1c") == "above",
        "Both a blood sugar reading and your 3-month sugar average (HbA1c) are above the usual range. When both are raised, "
        "doctors take it more seriously than one reading. Ask your doctor what it means for you.",
    ),
    (
        "Your blood fats",
        lambda p: sum(p.get(t) == "above" for t in ("Total Cholesterol", "LDL Cholesterol", "Triglycerides"))
        + (p.get("HDL Cholesterol") == "below")
        >= 2,
        "More than one of your blood fat (cholesterol) results is outside the usual range. Together they affect the chance of "
        "heart and blood-vessel problems over time. Your doctor can tell you how much it matters for you.",
    ),
    (
        "Your liver tests",
        lambda p: p.get("ALT") == "above" and p.get("AST") == "above",
        "Both liver enzymes (ALT and AST) are above the usual range. They are usually read together; a doctor may want to "
        "ask about medicines, alcohol and weight, or repeat the test.",
    ),
    (
        "Your blood counts",
        lambda p: sum(p.get(t) in ("above", "below") for t in ("Hemoglobin", "WBC Count", "Platelet Count")) >= 2,
        "More than one blood count is outside the usual range. Doctors look at the blood counts together to see the whole picture.",
    ),
    (
        "Your heart and blood pressure",
        lambda p: p.get("Blood Pressure") == "above"
        and (p.get("Total Cholesterol") == "above" or p.get("LDL Cholesterol") == "above"),
        "A raised blood pressure together with raised cholesterol adds up over time. Your doctor can tell you how much this matters for you.",
    ),
]


def _attention(validation: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = [w for w in validation.get("warnings", []) if w.get("severity") in ("HIGH_RISK", "CAUTION")]
    warnings.sort(key=lambda w: w.get("severity") != "HIGH_RISK")
    return [
        {
            "text": w.get("patient_message") or rewrite(str(w.get("message", ""))),
            "urgent": w.get("severity") == "HIGH_RISK",
        }
        for w in warnings
    ]


def _conditions(entities: list[dict]) -> list[dict[str, Any]]:
    seen, out = set(), []
    for entity in entities:
        if entity.get("type") != "condition" or entity.get("method") == "biobert" or entity.get("negated") is not False:
            continue
        if entity["name"] in seen:
            continue
        seen.add(entity["name"])
        info = term_info(entity["name"])
        out.append(
            {
                "name": _cap(plain_name(entity["name"])),
                "medical_name": entity["name"],
                "chronic": bool(entity.get("chronic")),
                "explain": info.explain if info else None,
            }
        )
    return out


def _medicines(entities: list[dict]) -> list[dict[str, Any]]:
    seen, out = set(), []
    for entity in entities:
        if entity.get("type") != "medication" or entity.get("method") == "biobert" or entity.get("negated"):
            continue
        key = (entity["name"], entity.get("status"))
        if key in seen:
            continue
        seen.add(key)
        details = ", ".join(str(p) for p in (entity.get("dose"), entity.get("frequency")) if p)
        out.append(
            {
                "name": entity["name"] + (f" ({entity['brand']})" if entity.get("brand") else ""),
                "details": details or None,
                "stopped": entity.get("status") == "stopped",
            }
        )
    return out


def _headline(items: list[dict[str, Any]]) -> str:
    readable = [i for i in items if i["position"] in ("above", "below", "within")]
    if not items:
        return (
            "The app did not find test values in this report, so there are no results to compare. "
            "You can still ask what a word in your report means."
        )
    if not readable:
        return "The app found values in this report but could not read them clearly enough to compare them with a usual range. Please check your printed report."
    above = sum(i["position"] == "above" for i in readable)
    below = sum(i["position"] == "below" for i in readable)
    within = len(readable) - above - below
    parts = []
    if above:
        parts.append(f"{above} higher than")
    if below:
        parts.append(f"{below} lower than")
    outside = " and ".join(parts)
    if not outside:
        return (
            f"The app could read {len(readable)} result{'s' if len(readable) != 1 else ''} and all of them are inside the usual range it uses. "
            "That does not mean everything is fine: your doctor looks at much more than these numbers."
        )
    return (
        f"The app could read {len(readable)} result{'s' if len(readable) != 1 else ''}. {_cap(outside)} the usual range"
        f"{f' and {within} inside it' if within else ''}. A result outside the range is common and often has an ordinary explanation, "
        "but it is worth showing to your doctor."
    )


def build_explanation(text: str, entities: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
    """The whole explanation of one report, from what the app read from it. `text` and `entities` are identity-free."""
    items = [i for i in (_item(e) for e in entities) if i]
    positions = {i["medical_name"]: i["position"] for i in items}
    flagged = [i for i in items if i["position"] in ("above", "below")]
    conditions = _conditions(entities)
    questions = ["What do these results mean for my health?"]
    if flagged or _attention(validation):
        questions.append("Do any of these results need a repeat test or treatment?")
    for item in flagged[:3]:
        questions.append(
            f"Why is my {item['name'].lower()} {'higher' if item['position'] == 'above' else 'lower'} than usual?"
        )
    if conditions:
        questions.append(f"How do these results relate to my {conditions[0]['name'].lower()}?")
    questions.append("When should I have these tests again?")
    suggestions = ["What does this report say overall?", "Which results are outside the usual range?"]
    suggestions += [f"Explain my {i['name'].lower()} in more detail" for i in flagged[:2]]
    return {
        "readable": bool(items or conditions or entities),
        "headline": _headline(items),
        "attention": _attention(validation),
        "results": items,
        "insights": [{"title": title, "text": note} for title, test, note in _INSIGHTS if test(positions)],
        "conditions": conditions,
        "medicines": _medicines(entities),
        "glossary": glossary(text, limit=8),
        "questions": questions,
        "suggestions": suggestions,
        "disclaimer": MACHINE_NOTE,
    }


# --- questions -----------------------------------------------------------------------------------------

_TREATMENT = re.compile(
    r"\b(treat(ment|ments)?|cure|cures|medicine|medicines|medication|medications|tablet|tablets|pill|pills|dose|dosage|prescri\w+|"
    r"antibiotics?|supplements?|vitamins?|diet|eat|eating|food|foods|exercise|lifestyle|stop taking|should i take|can i take|"
    r"remed(y|ies)|ointment|injection|surgery|operation)\b",
    re.I,
)
_DIAGNOSIS = re.compile(
    r"(\bdo i have\b|\bam i (diabetic|anemic|anaemic|sick|ill|dying|pregnant)\b|\bis (it|this|that) (diabetes|cancer|kidney failure|anemia|anaemia|an infection)\b|"
    r"\bwhat (disease|illness|condition) do i have\b|what'?s wrong with me|\bdiagnos\w+\b|\bwhat is wrong with me\b)",
    re.I,
)
_SEVERITY = re.compile(
    r"\b(serious|dangerous|worried|worry|scared|afraid|critical|risk|risky|bad|urgent|will i (die|be ok|be fine)|how (bad|serious))\b",
    re.I,
)
_SUMMARY = re.compile(
    r"\b(overall|summar\w+|everything|whole report|in short|main points|what does (this|my) report say)\b", re.I
)
_OUTSIDE = re.compile(r"\b(out of range|outside|abnormal|high|low|higher|lower|wrong|not normal|which results)\b", re.I)
_DOCTOR_QUESTIONS = re.compile(r"\b(ask (my|the) doctor|questions? (for|to)|what should i ask)\b", re.I)
_DEFINE = re.compile(r"\b(what is|what are|what does|what do|meaning of|mean|explain|tell me about)\b", re.I)


def _words(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower())


def _topics(question: str, explanation: dict[str, Any], topic: str | None) -> list[dict[str, Any]]:
    """The results in this report that the question names (by their medical or everyday name), or the chosen topic."""
    if topic:
        chosen = [i for i in explanation["results"] if i["key"] == topic]
        if chosen:
            return chosen
    text = f" {_words(question)} "
    found = []
    for item in explanation["results"]:
        names = {_words(item["medical_name"]).strip(), _words(item["name"]).strip()}
        info = term_info(item["medical_name"])
        if info:
            names.add(info.key.lower())
            names.update(short_forms(item["medical_name"]))  # the short form on the report ("hb", "alt")
        if any(f" {n} " in text for n in names if n):
            found.append(item)
    return found


def _explain_item(item: dict[str, Any]) -> str:
    parts = [
        f"{item['name']} ({item['medical_name']})"
        if item["name"].lower() != item["medical_name"].lower()
        else item["medical_name"]
    ]
    if item["what_it_is"]:
        parts.append(f"What it is: {item['what_it_is']}")
    if item["printed"]:
        parts.append(f"Your result: {item['printed']}. {item['where']}")
    else:
        parts.append(item["where"])
    if item["meaning"]:
        parts.append(
            f"What this can mean: {item['meaning']} Many things can cause it, most of them ordinary, and only your doctor can tell which applies to you."
        )
    if item["note"]:
        parts.append(item["note"])
    if item["urgent_note"]:
        parts.append(item["urgent_note"])
    if not item["meaning"] and item["position"] == "within":
        parts.append("Your doctor will tell you what this result means for you.")
    return "\n\n".join(parts)


def _flagged_list(explanation: dict[str, Any]) -> str:
    flagged = [i for i in explanation["results"] if i["position"] in ("above", "below")]
    return "\n".join(f"- {i['name']}: {i['printed']} ({i['where'].rstrip('.').lower()})" for i in flagged)


def _followups(explanation: dict[str, Any], used: set[str]) -> list[str]:
    flagged = [i for i in explanation["results"] if i["position"] in ("above", "below") and i["key"] not in used]
    chips = [f"Explain my {i['name'].lower()} in more detail" for i in flagged[:2]]
    chips.append("What should I ask my doctor?")
    if not chips[:-1]:
        chips.insert(0, "What does this report say overall?")
    return chips[:3]


def rule_answer(question: str, explanation: dict[str, Any], topic: str | None = None) -> dict[str, Any]:
    """The answer by fixed rules: same words every time for the same report and question."""
    text = " ".join(question.split())[:MAX_QUESTION]
    if symptom_checker.red_flags(text):
        return {"intent": "emergency", "answer": EMERGENCY_ANSWER, "topics": [], "followups": [], "emergency": True}
    found = _topics(text, explanation, topic)
    keys = {i["key"] for i in found}

    if _TREATMENT.search(text) and not found:
        answer = (
            "I cannot give advice about treatment, medicines, doses, food or exercise. That depends on your whole health, which "
            "this tool cannot see. Your doctor or pharmacist can advise you. What I can do is explain what the results in your "
            "report mean, so you can ask them better questions."
        )
        return {
            "intent": "treatment",
            "answer": answer,
            "topics": [],
            "followups": _followups(explanation, keys),
            "emergency": False,
        }
    if _DIAGNOSIS.search(text):
        flagged = _flagged_list(explanation)
        answer = (
            "I cannot tell you whether you have a particular illness: only a doctor can, after asking about your symptoms and "
            "examining you. "
            + (
                f"What I can say is what your report shows:\n{flagged}\n\nA result outside the usual range can be linked to several things, none of them certain."
                if flagged
                else "The results the app could read are not outside the ranges it uses, which still does not mean everything is fine."
            )
        )
        return {
            "intent": "diagnosis",
            "answer": answer,
            "topics": [],
            "followups": _followups(explanation, keys),
            "emergency": False,
        }
    if _DOCTOR_QUESTIONS.search(text):
        answer = "Here are questions you could take to your doctor:\n" + "\n".join(
            f"- {q}" for q in explanation["questions"]
        )
        return {
            "intent": "doctor_questions",
            "answer": answer,
            "topics": [],
            "followups": _followups(explanation, keys),
            "emergency": False,
        }
    if found:
        answer = "\n\n".join(_explain_item(i) for i in found[:2])
        return {
            "intent": "result",
            "answer": answer,
            "topics": [i["key"] for i in found[:2]],
            "followups": _followups(explanation, keys),
            "emergency": False,
        }
    if _SEVERITY.search(text):
        urgent = [i for i in explanation["results"] if i["urgent"]]
        if urgent:
            answer = (
                "Some of your results are far from the usual range: "
                + ", ".join(i["name"].lower() for i in urgent)
                + ". "
                + URGENT_NOTE
            )
        elif _flagged_list(explanation):
            answer = (
                "I cannot tell how serious this is for you, and I understand it can be worrying. Results outside the usual range are common "
                "and often have ordinary explanations, but your doctor is the one who can tell you, so it is worth showing them this report.\n\n"
                f"These are the results outside the range:\n{_flagged_list(explanation)}\n\n"
                "If you ever have chest pain, trouble breathing, fainting or heavy bleeding, call 1122 or go to the nearest emergency department."
            )
        else:
            answer = (
                "The app did not find a result outside the ranges it checks. That does not mean everything is fine, because your doctor looks at much more "
                "than these numbers. If you are worried, tell your doctor. If you ever have chest pain, trouble breathing, fainting or heavy bleeding, "
                "call 1122 or go to the nearest emergency department."
            )
        return {
            "intent": "severity",
            "answer": answer,
            "topics": [],
            "followups": _followups(explanation, keys),
            "emergency": False,
        }
    if _SUMMARY.search(text) or _OUTSIDE.search(text):
        flagged = _flagged_list(explanation)
        answer = explanation["headline"] + (f"\n\nResults outside the usual range:\n{flagged}" if flagged else "")
        for insight in explanation["insights"][:2]:
            answer += f"\n\n{insight['title']}: {insight['text']}"
        return {
            "intent": "summary",
            "answer": answer,
            "topics": [],
            "followups": _followups(explanation, keys),
            "emergency": False,
        }
    if _DEFINE.search(text):
        terms = glossary(text, limit=3)
        if terms:
            answer = "\n\n".join(f"{t['term']}: {t['explain']}" for t in terms)
            return {
                "intent": "word",
                "answer": answer,
                "topics": [],
                "followups": _followups(explanation, keys),
                "emergency": False,
            }
    names = ", ".join(i["name"].lower() for i in explanation["results"][:6])
    answer = "I can only explain what is in this report. " + (
        f"You could ask about one of its results ({names}), or ask what the report says overall."
        if names
        else "Try asking what a word in your report means, or what the report says overall."
    )
    return {
        "intent": "unknown",
        "answer": answer,
        "topics": [],
        "followups": _followups(explanation, keys),
        "emergency": False,
    }


# --- optional AI wording ---------------------------------------------------------------------------------

AI_INSTRUCTIONS = (
    "You re-word an explanation of a medical report for a patient with no medical training. You are a computer program, "
    "not a doctor, and you never say or suggest otherwise. Use ONLY the facts in the text you are given and the usual "
    "meaning of the test names in it. Do not diagnose, do not say a result is normal or safe, do not suggest any medicine, "
    "dose, food, exercise or treatment, and do not add any number that is not in the text. Use short sentences and everyday words, "
    "keep any medical term in brackets after its everyday name, and keep the answer under 180 words. If the text says to contact "
    "a doctor or call 1122, keep that. End by suggesting the patient asks their doctor about anything that worries them."
)
_BANNED = re.compile(
    r"(\byou (have|are suffering from|suffer from)\b|\bdiagnos(ed|is)\b|\byou should (take|stop|start|eat|avoid)\b|\btake \d|"
    r"\b\d+\s?(mg|ml|mcg|tablets?|capsules?)\b|\bprescri\w+|\bas a (doctor|physician|medical)\b|\bi am a (doctor|physician)\b|\bis normal\b|\bis safe\b)",
    re.I,
)
Generate = Callable[[str, str], Awaitable[AiResult]]


async def answer_question(
    question: str,
    explanation: dict[str, Any],
    history: list[dict[str, str]] | None = None,
    topic: str | None = None,
    generate: Generate = generate_text,
) -> dict[str, Any]:
    """The answer to one question, by rules, re-worded by AI only when that is safe. Returns the answer, where it
    came from ("rules" or the AI provider's name), its intent, the topics it explained and follow-up suggestions."""
    base = rule_answer(question, explanation, topic)
    base["source"] = "rules"
    if base["emergency"] or base["intent"] in ("emergency", "treatment", "diagnosis"):
        return base  # fixed wording only: an AI never words an emergency or a refusal
    facts = base["answer"]
    context = "\n".join(
        f"- {i['name']} ({i['medical_name']}): {i['printed'] or 'not read'}; {i['where']}"
        for i in explanation["results"][:20]
    )
    turns = "\n".join(f"{t['role']}: {t['text'][:MAX_QUESTION]}" for t in (history or [])[-MAX_HISTORY:])
    prompt = (
        f"The patient's question: {question[:MAX_QUESTION]}\n\n"
        f"The report's results:\n{context or '(none read)'}\n\n"
        f"The answer already prepared (use only its facts):\n{facts}\n\n"
        + (f"The conversation so far:\n{turns}\n\n" if turns else "")
        + "Write the answer for the patient."
    )
    result = await generate(AI_INSTRUCTIONS, prompt)
    text = (result.text or "").strip()
    if (
        not text
        or len(text) > 1500
        or _BANNED.search(text)
        or numbers_not_in_source(text, f"{facts}\n{context}\n{question}")
    ):
        return base
    base["answer"], base["source"] = text, result.provider or "ai"
    return base
