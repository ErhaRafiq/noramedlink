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
from typing import Any

from services import knowledge

ENTITIES_VERSION = 2  # bump when extraction changes, so stored entities can be rebuilt
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


def _test_results(text: str) -> list[dict[str, Any]]:
    entities = []
    offset = 0
    for line in text.splitlines(keepends=True):
        clean = line.replace("|", " ")
        mentions = knowledge.find_lab_tests(clean)
        for index, mention in enumerate(mentions):
            end = mentions[index + 1].start if index + 1 < len(mentions) else len(clean)
            segment = clean[mention.end : end]
            value = _VALUE.search(segment)
            if UNREADABLE in segment[: value.start() if value else len(segment)]:
                entities.append(_result(mention, offset, value=None, readable=False))
                continue
            if not value or len(segment[: value.start()].strip(" :-=")) > 25:
                continue  # no number close after the name: a heading or a sentence, not a result
            rest = segment[value.end() :]
            unit = _UNIT.match(rest)
            after_unit = rest[unit.end() :] if unit else rest
            reference = _RANGE.search(after_unit)
            flag = _FLAG.search(after_unit[reference.end() :] if reference else after_unit)
            printed = (value.group(1) or "").replace(" ", "") + value.group(2)
            entities.append(
                _result(
                    mention,
                    offset,
                    value=printed,
                    unit=unit.group(1) if unit else None,
                    reference=" ".join(reference.group(0).split()) if reference else None,
                    flag={"HIGH": "H", "LOW": "L"}.get(flag.group(1).upper(), flag.group(1).upper()) if flag else None,
                )
            )
        offset += len(line)
    return entities


def _result(mention, offset, value, unit=None, reference=None, flag=None, readable=True) -> dict[str, Any]:
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
        "position": offset + mention.start,
        "certainty": MENTIONED,
        "method": "rules",
        "confidence": None,  # filled from the report's OCR confidence when the summary is built
    }


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


def extract_entities(text: str, biobert_entities: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """All typed entities in one report's text (identifiers already removed), in text order."""
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
    ]
    entities.sort(key=lambda e: e["position"] if e["position"] is not None else 0)
    return entities + _biobert_suggestions(biobert_entities or [], entities)
