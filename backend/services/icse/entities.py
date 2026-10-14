"""FE-1: typed medical entities from report text, for the clinical summary.

Rules and the shared knowledge base (services/knowledge) find everything that can be traced:
test results (name, value, unit, printed range, the report's own H/L flag), medications (name,
dose, frequency, stopped or not), conditions (negated or not, history or not) and allergies.
BioBERT is a secondary signal only: what it finds that the rules did not is added as a
low-confidence "model suggestion", and is never used for a flag.

Everything found in a report is "mentioned in report": a condition or allergy written in a
report is not a confirmed diagnosis. The caller passes text with identifiers already removed.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from services import knowledge
from services.lab_rules import looks_like_unit, plausible_blood_pressure

ENTITIES_VERSION = 4  # bump when extraction changes, so stored entities can be rebuilt
MENTIONED = "mentioned in report"
SUGGESTION = "model suggestion"

# --- context: negation, history, stopped ----------------------------------------------------------

_CLAUSE_BREAK = re.compile(r"\.(?!\d)|[;:\n]|\bbut\b|\bhowever\b", re.IGNORECASE)  # not the "." in "2.5"
_NEGATION_BEFORE = re.compile(
    r"\b(?:no|not|denies|denied|without|negative for|no history of|no h/o|no known|free of|"
    r"ruled out|rules out|r/o|absence of|never)\b",
    re.IGNORECASE,
)
_NEGATION_AFTER = re.compile(r"^\W{0,3}(?:ruled out|excluded|negative|not present|absent)\b", re.IGNORECASE)
_HISTORY = re.compile(
    r"\b(?:known case of|k/c/o|kco|h/o|history of|past history|diagnosed with|on treatment for)\b", re.IGNORECASE
)
_STOPPED = re.compile(r"\b(?:stopped|discontinued|held|withheld|stop|off)\b", re.IGNORECASE)


def _clause_before(text: str, start: int, limit: int = 60) -> str:
    window = text[max(0, start - limit) : start]
    parts = _CLAUSE_BREAK.split(window)
    return parts[-1] if parts else window


def _clause_after(text: str, end: int, limit: int = 40) -> str:
    window = text[end : end + limit]
    return _CLAUSE_BREAK.split(window)[0]


def _negated(text: str, start: int, end: int) -> bool:
    return bool(_NEGATION_BEFORE.search(_clause_before(text, start))) or bool(
        _NEGATION_AFTER.search(text[end : end + 25])
    )


# --- allergies ------------------------------------------------------------------------------------

_NO_ALLERGY = re.compile(r"\b(?:NKDA|NKA|no known (?:drug |food )?allerg(?:y|ies)|no allerg(?:y|ies))\b", re.IGNORECASE)
_ALLERGY_LIST = re.compile(
    r"\b(?:allergic to|allergy to|allergies to|sensitive to|hypersensitivity to|intolerant of|drug allerg(?:y|ies)|allerg(?:y|ies))\s*(?:[:\-]|to\b)?\s*(?P<items>[^.\n;]{2,120})",
    re.IGNORECASE,
)
_NONE_WORDS = {"none", "nil", "no", "not known", "none known", "nkda", "nka", "none recorded", "unknown"}


def _allergies(text: str) -> tuple[list[dict[str, Any]], list[tuple[int, int]]]:
    entities: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    for match in _NO_ALLERGY.finditer(text):
        entities.append(
            _entity("allergy_status", "no known allergies", match, certainty=MENTIONED, status="none_recorded")
        )
        spans.append(match.span())
    for match in _ALLERGY_LIST.finditer(text):
        if _NO_ALLERGY.search(match.group(0)) or re.match(r"\s*(?:none|nil)\b", match.group("items"), re.IGNORECASE):
            if not any(s[0] < match.end() and match.start() < s[1] for s in spans):  # "Allergies: NKDA" once
                entities.append(
                    _entity("allergy_status", "no known allergies", match, certainty=MENTIONED, status="none_recorded")
                )
            spans.append(match.span())
            continue
        spans.append(match.span())
        items = re.sub(r"\([^)]*\)?", " ", match.group("items"))  # "penicillin (rash)": the reaction is not an allergen
        for raw in re.split(r",|\band\b|/|&", items):
            item = " ".join(raw.split()).strip(" -()")
            if not item or item.lower() in _NONE_WORDS or len(item) > 40:
                continue
            classes = knowledge.allergy_classes().get(item.lower())
            medication = knowledge.resolve_medication(item)
            entities.append(
                {
                    "type": "allergy",
                    "name": item.lower(),
                    "allergen_kind": "medication class" if classes else "medication" if medication else "other",
                    "allergen_classes": list(classes or (medication.classes if medication else ())),
                    "text": item,
                    "position": match.start("items"),
                    "certainty": MENTIONED,
                    "method": "rules",
                    "confidence": None,
                }
            )
    return entities, spans


# --- medications ----------------------------------------------------------------------------------

_DOSE = re.compile(r"(\d+(?:\.\d+)?)\s?(mg|mcg|µg|g|ml|iu|units?)\b", re.IGNORECASE)
_FREQUENCY = re.compile(
    r"\b(OD|BD|BID|TDS|TID|QID|HS|SOS|PRN|STAT|once daily|twice daily|thrice daily|once a day|twice a day|"
    r"at night|every \d+ hours|\d\+\d\+\d)(?![\w+])",
    re.IGNORECASE,
)
_PRESCRIPTION = re.compile(r"\b(?:Tab|Tablet|Cap|Capsule|Inj|Injection|Syp|Syrup)\.?\s+(?P<name>[A-Z][A-Za-z\-]{2,})")


def _medications(text: str, excluded: list[tuple[int, int]]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    known_spans: list[tuple[int, int]] = []
    for mention in knowledge.find_medications(text):
        if any(s <= mention.start < e for s, e in excluded):
            continue  # named in an allergy clause, not a medicine being taken
        known_spans.append((mention.start, mention.end))
        info = mention.info
        after = _clause_after(text, mention.end, 45)
        entities.append(
            {
                "type": "medication",
                "name": " + ".join(info.generics),
                "generics": list(info.generics),
                "brand": info.brand,
                "classes": list(info.classes),
                "high_alert": info.high_alert,
                "dose": _first(_DOSE, after),
                "frequency": _first(_FREQUENCY, after),
                "status": "stopped"
                if _STOPPED.search(after) or _STOPPED.search(_clause_before(text, mention.start, 30))
                else "mentioned",
                "negated": _negated(text, mention.start, mention.end),
                "text": mention.text,
                "position": mention.start,
                "certainty": MENTIONED,
                "method": "knowledge base",
                "confidence": None,
            }
        )
    # "Tab Rifaximin 550 mg BD": a prescription for a medicine the demo list does not know.
    for match in _PRESCRIPTION.finditer(text):
        start = match.start("name")
        if any(s <= start < e for s, e in known_spans + excluded):
            continue
        after = _clause_after(text, match.end(), 45)
        entities.append(
            {
                "type": "medication",
                "name": match.group("name").lower(),
                "generics": [],
                "brand": None,
                "classes": [],
                "high_alert": False,
                "dose": _first(_DOSE, after),
                "frequency": _first(_FREQUENCY, after),
                "status": "stopped" if _STOPPED.search(after) else "mentioned",
                "negated": False,
                "known": False,  # not in the knowledge base: no class, no safety information
                "text": match.group(0),
                "position": start,
                "certainty": MENTIONED,
                "method": "prescription pattern",
                "confidence": None,
            }
        )
    return entities


def _first(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    return " ".join(match.group(0).split()) if match else None


# --- conditions -----------------------------------------------------------------------------------


# Family history is never the patient's own condition, positive or negated. A heading or a relative
# ("Family history: DM", "Fam hx of HTN", "mother has asthma") marks the rest of the sentence; "in
# (the) family" right after a condition marks that condition.
_RELATIVES = (
    r"mother|father|brother|sister|siblings?|parents?|grandmother|grandfather|grandparents?|aunt|uncle|"
    r"son|daughter|cousin"
)
_FAMILY_START = re.compile(
    r"\b(?:family\s+history|fam(?:ily)?\.?\s*hx|fhx|f/h|family\s+h/o)\b|"
    rf"\b(?:{_RELATIVES})s?(?:'s)?\s*(?::|-|\b(?:has|had|have|with|is|was|were|suffers? from|suffered from|"
    r"died of|died from|diagnosed with|known case of|k/c/o)\b)",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"\.(?!\d)|[;\n]|\b(?:patient|pt)\b", re.IGNORECASE)  # "... and patient has HTN"
_IN_FAMILY_AFTER = re.compile(r"^\W{0,3}(?:in (?:the )?family|runs in (?:the )?family)\b", re.IGNORECASE)
_RELATIVE = re.compile(rf"\b({_RELATIVES})s?\b", re.IGNORECASE)


def _family_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    for match in _FAMILY_START.finditer(text):
        end = _SENTENCE_END.search(text, match.end())
        spans.append((match.start(), end.start() if end else len(text)))
    return spans


def _in_family(text: str, start: int, end: int, family: list[tuple[int, int]]) -> bool:
    return any(s <= start < e for s, e in family) or bool(_IN_FAMILY_AFTER.search(text[end : end + 30]))


def _conditions(text: str, excluded: list[tuple[int, int]], family: list[tuple[int, int]]) -> list[dict[str, Any]]:
    entities = []
    for mention in knowledge.find_conditions(text):
        if any(s <= mention.start < e for s, e in excluded):
            continue
        before = _clause_before(text, mention.start, 80)
        negated = _negated(text, mention.start, mention.end)
        if _in_family(text, mention.start, mention.end, family):
            span_start = next((s for s, e in family if s <= mention.start < e), mention.start)
            relative = _RELATIVE.search(text[span_start : mention.start])
            entities.append(
                {
                    "type": "family_history",  # a separate type: never read as the patient's condition
                    "name": mention.info.name,
                    "relative": relative.group(1).lower() if relative else None,
                    "negated": negated,
                    "text": mention.text,
                    "position": mention.start,
                    "certainty": MENTIONED,
                    "method": "knowledge base",
                    "confidence": None,
                }
            )
            continue
        entities.append(
            {
                "type": "condition",
                "name": mention.info.name,
                "icd10": mention.info.icd10,
                "chronic": mention.info.chronic,
                "negated": negated,
                "context": "history" if not negated and _HISTORY.search(before) else None,
                "text": mention.text,
                "position": mention.start,
                "certainty": MENTIONED,
                "method": "knowledge base",
                "confidence": None,
            }
        )
    return entities


# --- test results ---------------------------------------------------------------------------------

_VALUE = re.compile(r"(?<![\w.\[])([<>]\s*)?(\d+(?:,\d+)*(?:\.\d+)?)(?![\w])")
_UNIT = re.compile(r"^\s*(/?[a-zA-Zµμ%][\w%/^µμ.*]*(?:/[\w.]+)?)")
_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)|([<>]\s*\d+(?:\.\d+)?)")
_FLAG = re.compile(r"(?:^|\s)\(?(H|L|HIGH|LOW|High|Low)\)?\s*$")
UNREADABLE = "[?]"
# Words between a test name and a number that show the number belongs to a different test.
_OTHER_TEST = re.compile(
    r"\b(?:clearance|ratio|electrophoresis|index|excretion|variant|fraction|HbA2?|HbF|HbS)\b", re.IGNORECASE
)
_PRINTED_RANGE_FIRST = re.compile(r"\s*\([^)\n]*\d[^)\n]*\)")
_TIME_UNIT = re.compile(r"^(?:hrs?|hours?|h|mins?|minutes?)$", re.IGNORECASE)
_URINE_BEFORE = re.compile(r"\burine\b[^\n\d]{0,12}$", re.IGNORECASE)


# --- values from structured fields (OCR.space's parser) ----------------------------------------------

_FIELD_TESTS = {
    "glucose": "Blood Glucose",
    "blood_sugar": "Blood Glucose",
    "rbs": "Random Blood Sugar",
    "fbs": "Fasting Blood Sugar",
    "creatinine": "Creatinine",
    "hba1c": "HbA1c",
    "hb_a1c": "HbA1c",
    "egfr": "eGFR",
    "e_gfr": "eGFR",
}
_FIELD_VALUE = re.compile(r"\s*([<>]?\s*\d+(?:,\d+)*(?:\.\d+)?)\s*([^\s,;]*)")


def _field_entities(fields: dict[str, Any], found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Readings from structured fields, unless the same value was already read from the text."""
    seen = {(e["name"], e.get("value")) for e in found}
    entities = []
    for key, raw in (fields or {}).items():
        key = str(key).lower()
        match = _FIELD_VALUE.match(str(raw)) if raw is not None else None
        if not match:
            continue
        if key == "blood_pressure":
            pair = re.match(r"\s*(\d{2,3})\s*/\s*(\d{2,3})", str(raw))
            if pair and ("Blood Pressure", f"{pair.group(1)}/{pair.group(2)}") not in seen:
                systolic, diastolic = int(pair.group(1)), int(pair.group(2))
                entities.append(
                    {
                        "type": "vital",
                        "name": "Blood Pressure",
                        "value": f"{systolic}/{diastolic}",
                        "unit": "mmHg",
                        "readable": plausible_blood_pressure(systolic, diastolic),
                        "text": f"{key}: {raw}",
                        "evidence": f"{key}: {raw}",
                        "position": None,
                        "certainty": MENTIONED,
                        "method": "structured field",
                        "confidence": None,
                    }
                )
            continue
        name = _FIELD_TESTS.get(key)
        printed = match.group(1).replace(" ", "")
        if not name or (name, printed) in seen:
            continue
        unit = match.group(2) if looks_like_unit(match.group(2)) else None
        entities.append(
            {
                "type": "test_result",
                "name": name,
                "panel": None,
                "value": printed,
                "unit": unit,
                "reference_range": None,
                "report_flag": None,
                "readable": True,
                "text": f"{key}: {raw}",
                "evidence": f"{key}: {raw}"[:160],
                "position": None,
                "certainty": MENTIONED,
                "method": "structured field",
                "confidence": None,
            }
        )
    return entities


def _test_results(text: str) -> list[dict[str, Any]]:
    entities = []
    offset = 0
    for line in text.splitlines(keepends=True):
        clean = line.replace("|", " ")
        mentions = knowledge.find_lab_tests(clean)
        for index, mention in enumerate(mentions):
            end = mentions[index + 1].start if index + 1 < len(mentions) else len(clean)
            if _URINE_BEFORE.search(clean[: mention.start]):
                continue  # "urine sugar": not a blood test
            segment = clean[mention.end : end]
            skip = _PRINTED_RANGE_FIRST.match(segment)  # "Hemoglobin (13.0-17.0) 10.1 g/dL"
            start = skip.end() if skip else 0
            value = _VALUE.search(segment, start)
            if UNREADABLE in segment[start : value.start() if value else len(segment)]:
                entities.append(_result(mention, offset, clean, value=None, readable=False))
                continue
            if not value or len(segment[start : value.start()].strip(" :-=")) > 25:
                continue  # no number close after the name: a heading or a sentence, not a result
            if _OTHER_TEST.search(segment[start : value.start()]):
                continue  # "Creatinine Clearance 95", "Hb electrophoresis: HbA 97 %": a different test
            rest = segment[value.end() :]
            unit = _UNIT.match(rest)
            if unit and _TIME_UNIT.match(unit.group(1)):
                continue  # "Blood sugar 2 hours after meal": 2 is a time, not a reading
            if unit and not looks_like_unit(unit.group(1)):
                unit = None  # "Hb 10.2 today": a word, not a unit
            after_unit = rest[unit.end() :] if unit else rest
            reference = _RANGE.search(after_unit)
            flag = _FLAG.search(after_unit[reference.end() :] if reference else after_unit)
            printed = (value.group(1) or "").replace(" ", "") + value.group(2)
            entities.append(
                _result(
                    mention,
                    offset,
                    clean,
                    value=printed,
                    unit=unit.group(1).rstrip(".") if unit else None,
                    reference=" ".join(reference.group(0).split()) if reference else None,
                    flag={"HIGH": "H", "LOW": "L"}.get(flag.group(1).upper(), flag.group(1).upper()) if flag else None,
                )
            )
        offset += len(line)
    return entities


def _result(mention, offset, line, value, unit=None, reference=None, flag=None, readable=True) -> dict[str, Any]:
    return {
        "type": "test_result",
        "name": mention.info.name,
        "panel": mention.info.panel,
        "value": value,
        "unit": unit,
        "reference_range": reference,
        "report_flag": flag,  # what the report itself marks; the app's rules decide their own flags
        "readable": readable,
        "text": mention.text,
        "evidence": " ".join(line.split())[:160],
        "position": offset + mention.start,
        "certainty": MENTIONED,
        "method": "rules",
        "confidence": None,  # filled from the report's OCR confidence when the summary is built
    }


# --- vitals: blood pressure -----------------------------------------------------------------------

# Only where the text says it is a blood pressure: "BP"/"blood pressure" just before, or "mmHg" just
# after. Any "a/b" (dates, IDs) is not one.
_BP_LABELLED = re.compile(
    r"\b(?:BP|B\.P\.?|blood\s*pressure)\b[^0-9\n]{0,15}(\d{2,3})\s*/\s*(\d{2,3})\b", re.IGNORECASE
)
_BP_WITH_UNIT = re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\s*mm\s*hg\b", re.IGNORECASE)


def _blood_pressures(text: str) -> list[dict[str, Any]]:
    found: dict[int, re.Match] = {}
    for pattern in (_BP_LABELLED, _BP_WITH_UNIT):
        for match in pattern.finditer(text):
            found.setdefault(match.start(1), match)  # "BP 150/95 mmHg" matches both: one reading
    entities = []
    for position in sorted(found):
        match = found[position]
        systolic, diastolic = int(match.group(1)), int(match.group(2))
        plausible = plausible_blood_pressure(systolic, diastolic)
        entities.append(
            {
                "type": "vital",
                "name": "Blood Pressure",
                "value": f"{systolic}/{diastolic}",
                "unit": "mmHg",
                "readable": plausible,  # an implausible pair is shown to check, never flagged
                "text": match.group(0),
                "position": position,
                "certainty": MENTIONED,
                "method": "rules",
                "confidence": None,
            }
        )
    return entities


# --- report date ----------------------------------------------------------------------------------

_MONTHS = {
    m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)
}
_DATE = (
    r"(?P<d1>\d{1,2})[-/ .](?P<mon>[A-Za-z]{3,9})[-/ .,]+(?P<y1>\d{4})"
    r"|(?P<d2>\d{1,2})[-/.](?P<m2>\d{1,2})[-/.](?P<y2>\d{4})"
    r"|(?P<y3>\d{4})-(?P<m3>\d{1,2})-(?P<d3>\d{1,2})"
)
# Which printed date describes the sample, best first. The upload date is never used for trends.
_DATE_LABELS = [
    ("collected", r"collected(?:\s+on)?|collection\s+date|sample\s+(?:collected|date|collection)"),
    ("visit", r"date\s+of\s+(?:visit|admission|discharge)|visit\s+date|admission\s+date|discharge\s+date"),
    ("dated", r"date"),
    ("reported", r"reported(?:\s+on)?|report\s+date"),
]


def _parse_date(match: re.Match) -> date | None:
    try:
        if match.group("y1"):
            month = _MONTHS.get(match.group("mon")[:3].lower())
            return date(int(match.group("y1")), month, int(match.group("d1"))) if month else None
        if match.group("y2"):  # day first, as printed in Pakistan
            return date(int(match.group("y2")), int(match.group("m2")), int(match.group("d2")))
        return date(int(match.group("y3")), int(match.group("m3")), int(match.group("d3")))
    except ValueError:
        return None


def _report_date(text: str) -> dict[str, Any] | None:
    for label, words in _DATE_LABELS:
        for match in re.finditer(rf"\b(?:{words})\b\s*[:\-]?\s*(?:{_DATE})", text, re.IGNORECASE):
            parsed = _parse_date(match)
            if parsed:
                return {
                    "type": "report_date",
                    "name": label,
                    "value": parsed.isoformat(),
                    "text": match.group(0),
                    "position": match.start(),
                    "certainty": MENTIONED,
                    "method": "rules",
                    "confidence": None,
                }
    return None


# --- BioBERT (secondary) --------------------------------------------------------------------------

_BIOBERT_TYPES = {"Disease": "condition", "Symptom": "symptom", "Medicine": "medication"}


def _biobert_suggestions(biobert_entities: list[dict[str, Any]], found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known = {e["name"].lower() for e in found} | {e.get("text", "").lower() for e in found}
    suggestions = []
    for item in biobert_entities or []:
        kind = _BIOBERT_TYPES.get(item.get("label", ""))
        text = str(item.get("text") or "").strip().lower()
        if not kind or not text or any(text in k or k in text for k in known if k):
            continue
        suggestions.append(
            {
                "type": kind,
                "name": text,
                "negated": None,  # the model does not say
                "text": item.get("text"),
                "position": None,
                "certainty": SUGGESTION,
                "method": "biobert",
                "confidence": round(min(float(item.get("confidence") or 0), 1.0) * 0.5, 3),  # deliberately low
            }
        )
    return suggestions


# --- entry point ----------------------------------------------------------------------------------


def _entity(kind: str, name: str, match: re.Match, **extra) -> dict[str, Any]:
    return {
        "type": kind,
        "name": name,
        "text": match.group(0),
        "position": match.start(),
        "method": "rules",
        "confidence": None,
        **extra,
    }


def extract_entities(
    text: str, biobert_entities: list[dict[str, Any]] | None = None, fields: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """All typed entities in one report's text (identifiers already removed), in text order, then
    values from structured fields that the text did not already give. The per-report rules and the
    clinical summary both read values through this function only."""
    text = text or ""
    family = _family_spans(text)
    allergies, allergy_spans = _allergies(text)
    # A relative's allergy or medicine ("mother allergic to penicillin", "father on insulin") is not
    # the patient's: dropped.
    allergies = [a for a in allergies if not any(s <= a["position"] < e for s, e in family)]
    entities = [
        *_test_results(text),
        *_medications(text, allergy_spans + family),
        *_conditions(text, allergy_spans, family),
        *allergies,
        *_blood_pressures(text),
    ]
    printed_date = _report_date(text)
    if printed_date:
        entities.append(printed_date)
    entities.sort(key=lambda e: e["position"] if e["position"] is not None else 0)
    entities += _field_entities(fields or {}, entities)
    return entities + _biobert_suggestions(biobert_entities or [], entities)
