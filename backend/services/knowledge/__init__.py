"""Shared medical name matching: medications (generic and Pakistani brand names), conditions and
lab test names. DEMO KNOWLEDGE BASE, not a clinical reference: see data/*.json for every entry's
source. Used by the clinical summary (services/icse) and meant for Phase 3b prescription safety,
so both match names the same way.

Matching is deterministic: whole words, longest name first, case-insensitive for names and
case-sensitive for abbreviations ("DM", "HTN", "K"), so ordinary words are not mistaken for them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _alternation(names: list[str]) -> str:
    return "|".join(re.escape(name) for name in sorted(set(names), key=len, reverse=True))


def _word_pattern(names: list[str], ignore_case: bool = True) -> re.Pattern | None:
    if not names:
        return None
    return re.compile(rf"(?<![\w-])(?:{_alternation(names)})(?![\w-])", re.IGNORECASE if ignore_case else 0)


# --- medications --------------------------------------------------------------------------------


@dataclass(frozen=True)
class MedicationInfo:
    generics: tuple[str, ...]  # one, or more for a combination product
    brand: str | None
    classes: tuple[str, ...]
    high_alert: bool
    atc: tuple[str, ...]
    source: str

    @property
    def display_name(self) -> str:
        names = " + ".join(self.generics)
        return f"{names} ({self.brand})" if self.brand else names


@dataclass(frozen=True)
class Mention:
    start: int
    end: int
    text: str
    info: object = field(compare=False)


@cache
def _medication_index() -> tuple[dict[str, MedicationInfo], re.Pattern]:
    data = _load("medications.json")
    generics = {g["name"]: g for g in data["generics"]}
    index: dict[str, MedicationInfo] = {}

    def info_for(names: list[str], brand: str | None, source: str) -> MedicationInfo:
        entries = [generics[n] for n in names]
        return MedicationInfo(
            generics=tuple(names),
            brand=brand,
            classes=tuple(dict.fromkeys(c for e in entries for c in e.get("classes", []))),
            high_alert=any(e.get("high_alert") for e in entries),
            atc=tuple(e["atc"] for e in entries if e.get("atc")),
            source=source,
        )

    for generic in data["generics"]:
        info = info_for([generic["name"]], None, generic["source"])
        for name in [generic["name"], *generic.get("aliases", [])]:
            index[name.lower()] = info
    for brand in data["brands"]:
        missing = [g for g in brand["generics"] if g not in generics]
        if missing:
            raise ValueError(f"Brand {brand['brand']} maps to unknown generics {missing}")
        index[brand["brand"].lower()] = info_for(brand["generics"], brand["brand"], brand["source"])
    return index, _word_pattern(list(index))


def resolve_medication(name: str) -> MedicationInfo | None:
    """A medicine name (generic, alias or brand) -> what it is; None if not in the demo list."""
    index, _ = _medication_index()
    return index.get(" ".join((name or "").lower().split()))


def find_medications(text: str) -> list[Mention]:
    index, pattern = _medication_index()
    return [Mention(m.start(), m.end(), m.group(0), index[m.group(0).lower()]) for m in pattern.finditer(text or "")]


@cache
def allergy_classes() -> dict[str, tuple[str, ...]]:
    """Allergy words that name a drug class ("penicillin", "sulfa drugs") -> classes."""
    return {k: tuple(v) for k, v in _load("medications.json")["drug_classes_for_allergies"].items()}


# --- conditions ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class ConditionInfo:
    name: str
    icd10: str
    chronic: bool
    source: str


@cache
def _condition_index() -> tuple[dict[str, ConditionInfo], re.Pattern, dict[str, ConditionInfo], re.Pattern | None]:
    names: dict[str, ConditionInfo] = {}
    abbreviations: dict[str, ConditionInfo] = {}
    for item in _load("conditions.json")["conditions"]:
        info = ConditionInfo(item["name"], item["icd10"], item["chronic"], item["source"])
        for synonym in [item["name"], *item["synonyms"]]:
            names[synonym.lower()] = info
        for abbreviation in item.get("abbreviations", []):
            abbreviations[abbreviation] = info
    return names, _word_pattern(list(names)), abbreviations, _word_pattern(list(abbreviations), ignore_case=False)


def find_conditions(text: str) -> list[Mention]:
    names, pattern, abbreviations, abbreviation_pattern = _condition_index()
    found = [Mention(m.start(), m.end(), m.group(0), names[m.group(0).lower()]) for m in pattern.finditer(text or "")]
    if abbreviation_pattern:
        found += [
            Mention(m.start(), m.end(), m.group(0), abbreviations[m.group(0)])
            for m in abbreviation_pattern.finditer(text or "")
        ]
    return sorted(found, key=lambda mention: mention.start)


# --- lab tests ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class LabTestInfo:
    name: str
    panel: str


@cache
def _lab_index() -> tuple[dict[str, LabTestInfo], re.Pattern, re.Pattern]:
    index: dict[str, LabTestInfo] = {}
    row_only: dict[str, LabTestInfo] = {}
    for item in _load("lab_tests.json")["tests"]:
        info = LabTestInfo(item["name"], item["panel"])
        for alias in [item["name"], *item["aliases"]]:
            index[alias.lower()] = info
        for abbreviation in item.get("row_abbreviations", []):
            row_only[abbreviation] = info
    names = _word_pattern(list(index))
    # A row abbreviation counts only at the start of a line ("K 4.1 mmol/L"), case-sensitively.
    row_start = re.compile(rf"^\s*(?:{_alternation(list(row_only))})(?![\w-])", re.MULTILINE)
    _row_lookup.update(row_only)
    return index, names, row_start


_row_lookup: dict[str, LabTestInfo] = {}


def find_lab_tests(text: str) -> list[Mention]:
    """Lab test names: full names anywhere, short abbreviations only at the start of a line."""
    index, names, row_start = _lab_index()
    found = [Mention(m.start(), m.end(), m.group(0), index[m.group(0).lower()]) for m in names.finditer(text or "")]
    for match in row_start.finditer(text or ""):
        abbreviation = match.group(0).strip()
        start = match.end() - len(abbreviation)
        if not any(m.start <= start < m.end for m in found):
            found.append(Mention(start, match.end(), abbreviation, _row_lookup[abbreviation]))
    return sorted(found, key=lambda mention: mention.start)
