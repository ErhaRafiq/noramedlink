"""The patient's summary of one report in everyday words, built by fixed rules (no AI needed).

Same sections as the AI summary, from what the app actually read: each test value as printed, the
report's own high/low marks, the rules' alerts in everyday words, conditions and medicines as
"mentioned in your report", and a short word list. Every medical word then gets its everyday
wording (services/plain_language.py). Nothing here judges a value itself, diagnoses, or says a
result is normal.
"""

from __future__ import annotations

from typing import Any

from services.plain_language import GLOSSARY_HEADING, glossary, named, plain_name, rewrite, rewrite_sections

CLOSING = "Please consult your doctor for proper diagnosis and treatment."
MAX_RESULTS = 15  # the summary states no counts of its own: every number in it is from the report
NOTHING_MARKED = (
    "The app's checks did not mark anything on this report for attention. "
    "That does not mean everything is normal; your doctor can tell you what the results mean for you."
)


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _rule(entity: dict[str, Any]) -> bool:
    return entity.get("method") != "biobert" and entity.get("certainty") != "model suggestion"


def _results(entities: list[dict]) -> list[str]:
    lines = []
    for entity in entities:
        if not _rule(entity) or entity.get("type") not in ("test_result", "vital"):
            continue
        name = _cap(named(entity["name"]))
        if not entity.get("readable", True) or not entity.get("value"):
            lines.append(f"- {name}: this value could not be read clearly. Please check your printed report.")
            continue
        value = " ".join(str(p) for p in (entity["value"], entity.get("unit") or "") if p)
        mark = {"H": " The report marks it as high.", "L": " The report marks it as low."}.get(
            entity.get("report_flag") or "", ""
        )
        lines.append(f"- {name}: {value}.{mark}")
    if len(lines) > MAX_RESULTS:
        lines = [*lines[:MAX_RESULTS], "- More results are in the full report text."]
    return lines


def _attention(validation: dict[str, Any]) -> list[str]:
    warnings = [w for w in validation.get("warnings", []) if w.get("severity") in ("HIGH_RISK", "CAUTION")]
    warnings.sort(key=lambda w: w.get("severity") != "HIGH_RISK")
    return [f"- {w.get('patient_message') or rewrite(str(w.get('message', '')))}" for w in warnings]


def _conditions(entities: list[dict]) -> list[str]:
    seen, lines = set(), []
    for entity in entities:
        if entity.get("type") != "condition" or not _rule(entity) or entity.get("negated") is not False:
            continue
        if entity["name"] in seen:
            continue
        seen.add(entity["name"])
        lines.append(f"- {_cap(named(entity['name']))}" + (" (a long-term condition)" if entity.get("chronic") else ""))
    return lines


def _medicines(entities: list[dict]) -> list[str]:
    seen, lines = set(), []
    for entity in entities:
        if entity.get("type") != "medication" or not _rule(entity) or entity.get("negated"):
            continue
        key = (entity["name"], entity.get("status"))
        if key in seen:
            continue
        seen.add(key)
        label = entity["name"] + (f" ({entity['brand']})" if entity.get("brand") else "")
        details = ", ".join(str(p) for p in (entity.get("dose"), entity.get("frequency")) if p)
        stopped = " - the report says this was stopped" if entity.get("status") == "stopped" else ""
        lines.append(f"- {label}{', ' + details if details else ''}{stopped}")
    return lines


def build_patient_summary(
    report_text: str,
    entities: list[dict[str, Any]],
    validation: dict[str, Any],
    department: str,
    conclusion: str | None = None,
) -> str:
    """The plain-language summary of one report. `report_text` is identity-free; `entities` come
    from services/icse/entities.py; `validation` from the report rules."""
    results = _results(entities)
    conditions = _conditions(entities)
    medicines = _medicines(entities)
    attention = _attention(validation)

    lines = ["What this report is"]
    kind = f"a {department.lower()} report" if department and department.lower() != "general" else "a medical report"
    lines.append(
        f"This is {kind}. These are the test results the app could read from it."
        if results
        else f"This is {kind}. The app did not find test values in it."
    )
    if conclusion:
        lines.append(f"The reporting doctor's conclusion, in everyday words: {conclusion}")

    lines += ["", "Your results explained", *(results or ["- No test values were found in this report."])]
    lines += ["", "What may need attention", *(attention or [NOTHING_MARKED])]
    if conditions:
        lines += [
            "",
            "Conditions mentioned in your report",
            *conditions,
            "These are mentioned in your report; the app does not diagnose. Ask your doctor what they mean for you.",
        ]
    if medicines:
        lines += ["", "Medicines mentioned in your report", *medicines]

    words = glossary(report_text)
    if words:
        lines += ["", GLOSSARY_HEADING, *(f"- {w['term']}: {w['explain']}" for w in words)]

    questions = ["- What do these results mean for my health?"]
    if attention:
        questions.append("- Do any of these results need a repeat test or treatment?")
    first_condition = next((e["name"] for e in entities if e.get("type") == "condition" and _rule(e)
                            and e.get("negated") is False), None)  # fmt: skip
    if first_condition:
        questions.append(f"- How do these results relate to my {plain_name(first_condition)}?")
    questions.append("- When should I have these tests again?")
    lines += ["", "Questions to ask your doctor", *questions, "", CLOSING]
    return rewrite_sections("\n".join(lines))
