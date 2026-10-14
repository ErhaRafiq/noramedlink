"""Everyday wording for patient-facing text (summaries and rule alerts).

The dictionary is services/knowledge/data/plain_terms.json (a demo knowledge base, not clinically
reviewed). A medical term becomes its everyday wording, with the term itself in brackets the first
time it appears, so the patient can find it on the printed report and say it to their doctor:

    "Creatinine 2.4 mg/dL" -> "Kidney waste level (Creatinine) 2.4 mg/dL"

Only whole words are changed, longest first; abbreviations must match exactly ("DM", "HTN"). Numbers,
units, "no"/"not" and the report's own H/L marks are never touched, text already in brackets is left
alone, and running the rewrite twice changes nothing more.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent / "knowledge" / "data" / "plain_terms.json"
GLOSSARY_HEADING = "Words you might see"
# The patient summary's section headings (AI and rule-based): never rewritten.
SECTION_HEADINGS = {
    "what this report is",
    "your results explained",
    "what may need attention",
    "what the report marks",
    "conditions mentioned in your report",
    "medicines mentioned in your report",
    "words you might see",
    "questions to ask your doctor",
}


@dataclass(frozen=True)
class PlainTerm:
    key: str  # the first alias or abbreviation: one entry, however it is written
    plain: str
    explain: str
    source: str


@cache
def _index() -> tuple[dict[str, PlainTerm], dict[str, PlainTerm], re.Pattern]:
    names: dict[str, PlainTerm] = {}
    abbreviations: dict[str, PlainTerm] = {}
    for item in json.loads(DATA.read_text(encoding="utf-8"))["terms"]:
        term = PlainTerm((item["aliases"] or item["abbreviations"])[0], item["plain"], item["explain"], item["source"])
        for alias in item["aliases"]:
            names[alias.lower()] = term
        for abbreviation in item["abbreviations"]:
            abbreviations[abbreviation] = term
    alternatives = sorted([*names, *abbreviations], key=len, reverse=True)
    pattern = re.compile(
        r"(?<![\w/-])(" + "|".join(re.escape(a) for a in alternatives) + r")(?![\w-])(?!/\w)", re.IGNORECASE
    )
    return names, abbreviations, pattern


def _lookup(found: str) -> PlainTerm | None:
    names, abbreviations, _ = _index()
    if found in abbreviations:
        return abbreviations[found]
    term = names.get(found.lower())
    # An abbreviation written in other letters ("dm", "Bd") is an ordinary word, not the abbreviation.
    return term


def find_terms(text: str) -> list[tuple[int, int, str, PlainTerm]]:
    """Medical terms in `text` outside brackets: (start, end, as written, entry)."""
    _, _, pattern = _index()
    found = []
    depth = 0
    position = 0
    for match in pattern.finditer(text or ""):
        segment = text[position : match.start()]
        depth = max(0, depth + segment.count("(") - segment.count(")"))
        position = match.start()
        if depth > 0:
            continue  # already in brackets: an earlier rewrite, or the report's own explanation
        term = _lookup(match.group(0))
        if term is None:
            continue
        found.append((match.start(), match.end(), match.group(0), term))
    return found


def _same_words(a: str, b: str) -> bool:
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def _contains(plain: str, written: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(written)}(?!\w)", plain, re.IGNORECASE))


def rewrite(text: str, seen: set[str] | None = None) -> str:
    """Everyday wording for every medical term; the term in brackets the first time.

    `seen` carries the terms already explained between calls (one summary, several sections)."""
    if not text:
        return text
    seen = set() if seen is None else seen
    out, last = [], 0
    for start, end, written, term in find_terms(text):
        if _same_words(written, term.plain):
            seen.add(term.key)
            continue
        already_explained = text[end : end + 2] == " ("  # "Creatinine (kidney waste)": the report explains it
        if already_explained:
            continue
        plain = term.plain
        at_start = (
            start == 0 or text[:start].rstrip().endswith((".", ":", "\n", "!", "?", "-")) or not text[:start].strip()
        )
        if at_start and plain[:1].islower():
            plain = plain[0].upper() + plain[1:]
        out.append(text[last:start])
        # The term once in brackets, unless the everyday wording already says it ("TB (a lung infection)").
        out.append(plain if term.key in seen or _contains(plain, written) else f"{plain} ({written})")
        seen.add(term.key)
        last = end
    out.append(text[last:])
    return "".join(out)


def rewrite_sections(text: str) -> str:
    """Rewrite a whole summary, leaving the "Words you might see" section as it is (it already pairs
    each term with its explanation)."""
    lines = (text or "").splitlines()
    seen: set[str] = set()
    result, in_glossary = [], False
    for line in lines:
        heading = line.strip().rstrip(":").lower()
        if heading in SECTION_HEADINGS:
            in_glossary = heading == GLOSSARY_HEADING.lower()
            result.append(line)
            continue
        result.append(line if in_glossary else rewrite(line, seen))
    return "\n".join(result)


def glossary(text: str, limit: int = 6) -> list[dict[str, str]]:
    """The medical terms in `text`, each once, with its everyday name and explanation."""
    entries: dict[str, dict[str, str]] = {}
    for _, _, written, term in find_terms(text):
        if term.key in entries or _same_words(written, term.plain) or term.source == "RX":
            continue  # prescription shorthand ("BD", "K/C/O") is rewritten in the text, not listed
        entries[term.key] = {"term": written, "plain": term.plain, "explain": term.explain}
        if len(entries) >= limit:
            break
    return list(entries.values())


def plain_name(name: str) -> str:
    """Everyday name for one term ("Creatinine" -> "kidney waste level"); the name itself if unknown."""
    term = _lookup(name) or _index()[0].get(name.lower())
    return term.plain if term else name


def named(name: str) -> str:
    """ "kidney waste level (Creatinine)": everyday wording with the term, for one name."""
    plain = plain_name(name)
    return plain if _same_words(plain, name) or _contains(plain, name) else f"{plain} ({name})"


def unexplained_terms(text: str) -> list[str]:
    """Terms still written without everyday wording (outside brackets and outside the glossary)."""
    left = []
    in_glossary = False
    for line in (text or "").splitlines():
        heading = line.strip().rstrip(":").lower()
        if heading in SECTION_HEADINGS:
            in_glossary = heading == GLOSSARY_HEADING.lower()
            continue
        if in_glossary:
            continue
        for _start, end, written, term in find_terms(line):
            if not _contains(term.plain, written) and line[end : end + 2] != " (":
                left.append(written)
    return left


# --- rule alerts in everyday words, for patients --------------------------------------------------


def patient_message(warning: dict[str, Any]) -> str:
    """A rule alert in words a patient understands. The doctor keeps the clinical message."""
    code = warning.get("code", "")
    severity = warning.get("severity")
    urgent = (
        " This needs prompt attention from a doctor."
        if severity == "HIGH_RISK"
        else " Please show this to your doctor."
    )
    test = warning.get("test")
    if test and warning.get("direction"):
        side = "above" if warning["direction"] == "high" else "below"
        reading = warning.get("value_text") or "this reading"
        return f"Your {named(test)} reading of {reading} is {side} the range the app checks against.{urgent}"
    if code == "VALUE_NEEDS_CHECK":
        return (
            f"The app could not read one value clearly{f' ({test})' if test else ''}, so it did not check it. "
            "Please compare it with your printed report and ask your doctor."
        )
    if code == "UNCERTAIN_OCR_VALUES":
        return "Some numbers were hard to read from the scan. Please compare them with your printed report."
    if code in {"DANGEROUS_MEDICINE_COMBINATION", "MEDICINE_COMBINATION_CAUTION"}:
        return f"Two medicines in this report may not go well together ({warning.get('evidence', '')}).{urgent}"
    if code == "DUPLICATE_MEDICINE":
        return "The same medicine seems to be listed more than once. Please check with your doctor."
    if code == "MISSING_ALLERGY_DATA":
        return "The report does not say whether you have any allergies. Tell your doctor about any you have."
    if code == "INCOMPLETE_OCR_TEXT":
        return "Only a little text could be read from this file. Please check it against your printed report."
    if code == "NO_RULE_ALERTS":
        return "The app's checks found nothing to point out. That does not mean everything is normal."
    return rewrite(str(warning.get("message", ""))) + ("" if severity not in {"CAUTION", "HIGH_RISK"} else urgent)
