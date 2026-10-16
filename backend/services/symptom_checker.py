"""Symptom checker (Module 7): which kind of doctor to see first. Advisory only, never a diagnosis.

1. Red flags first (pure rules, no AI). Any warning sign gives the emergency message and nothing else:
   no specialist, no booking. Signs the patient says they do NOT have ("no chest pain") do not count;
   everything unclear is treated as a warning sign, because a missed emergency is worse than an
   unneeded alert.
2. Otherwise the symptom words are matched to specialties by a fixed table (data/symptom_specialties.csv);
   no match, or a tie that cannot be split, falls back to a general physician.
3. Verified doctors of those specialties are ranked: soonest opening, then rating, then fee.

Tables: services/knowledge/data/red_flags.csv, specialties.csv, symptom_specialties.csv (demo knowledge
base, not clinically reviewed). English only. Medical text is never logged.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from schemas import AppointmentDoctorOut
from services.knowledge.tables import records

EMERGENCY_NOTICE = "Call 1122 or go to the nearest emergency department."
FALLBACK = "General Physician"
NEGATORS = {
    "no", "not", "never", "without", "denies", "deny", "denied", "dont", "don't", "didnt", "didn't",
    "hasnt", "hasn't", "havent", "haven't", "isnt", "isn't", "negative",
}  # fmt: skip
NEGATION_WINDOW = 3  # a negator this close before a phrase cancels it ("no chest pain", "never had a seizure")
SUBJECTS = {"i", "he", "she", "we", "they"}  # "no I have chest pain": that "no" answers a question, it negates nothing
MAX_SUGGESTIONS = 3
MAX_DOCTORS = 5
BREAK = "|"  # a sentence or clause end (. ; ! ? , newline): negation never crosses it


def tokenize(text: str) -> list[str]:
    text = text.lower().replace("’", "'")
    return [t if t not in {".", ";", "!", "?", ",", "\n"} else BREAK for t in re.findall(r"[a-z0-9']+|[.;!?,\n]", text)]


def _find(tokens: list[str], phrase: list[str], taken: set[int] | None = None) -> list[int]:
    """Start positions where `phrase` occurs in `tokens` (skipping positions already used)."""
    n = len(phrase)
    hits = []
    for i in range(len(tokens) - n + 1):
        if tokens[i : i + n] == phrase and not (taken and any(j in taken for j in range(i, i + n))):
            hits.append(i)
    return hits


def _negated(tokens: list[str], start: int) -> bool:
    before = tokens[max(0, start - NEGATION_WINDOW) : start]
    if BREAK in before:
        before = before[len(before) - before[::-1].index(BREAK) :]
    return any(t in NEGATORS and not (i + 1 < len(before) and before[i + 1] in SUBJECTS) for i, t in enumerate(before))


@dataclass(frozen=True)
class RedFlag:
    id: str
    label: str


def red_flags(text: str) -> list[RedFlag]:
    """The warning signs written in `text` (not the ones the patient says they do not have)."""
    tokens = tokenize(text)
    found = []
    for rule in records("red_flags"):
        patterns = [tokenize(p) for p in rule["patterns"]]
        companions = [tokenize(p) for p in rule["also"]]
        if companions and not any(
            _find(tokens, c) and any(not _negated(tokens, i) for i in _find(tokens, c)) for c in companions
        ):
            continue
        if any(not _negated(tokens, i) for p in patterns for i in _find(tokens, p)):
            found.append(RedFlag(rule["id"], rule["label"]))
    return found


@dataclass
class Suggestion:
    specialty: str
    plain: str
    matched: list[str]
    score: int
    aliases: list[str] = field(default_factory=list)
    fallback: bool = False


def suggest_specialties(text: str) -> list[Suggestion]:
    """Up to three specialties, best first, each with the words that pointed to it."""
    tokens = tokenize(text)
    rules = []
    for row in records("symptom_specialties"):
        for term in row["terms"]:
            rules.append((tokenize(term), term, row["specialty"], int(row["weight"])))
    rules.sort(key=lambda r: -len(r[0]))  # longest phrase first, so "high blood pressure" beats "blood pressure"

    taken: set[int] = set()
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}
    for phrase, term, specialty, weight in rules:
        for i in _find(tokens, phrase, taken):
            if _negated(tokens, i):
                continue
            taken.update(range(i, i + len(phrase)))
            scores[specialty] = scores.get(specialty, 0) + weight
            if term not in matched.setdefault(specialty, []):
                matched[specialty].append(term)

    info = {row["name"]: row for row in records("specialties")}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0] == FALLBACK, kv[0]))
    if not ranked:
        general = info[FALLBACK]
        return [Suggestion(FALLBACK, general["plain"], [], 0, general["doctor_aliases"], fallback=True)]
    top = ranked[0][1]
    chosen = [(name, score) for name, score in ranked if score * 2 >= top][:MAX_SUGGESTIONS]
    return [Suggestion(n, info[n]["plain"], matched[n], s, info[n]["doctor_aliases"]) for n, s in chosen]


def rank_doctors(doctors: list[AppointmentDoctorOut], aliases: list[str]) -> list[AppointmentDoctorOut]:
    """Doctors whose listed specialty matches, soonest opening first, then rating, then fee."""
    far = datetime.max.replace(tzinfo=UTC)
    fits = [d for d in doctors if any(a in d.specialty.lower() for a in aliases)]
    return sorted(
        fits,
        key=lambda d: (
            d.next_available or far,
            -(d.rating or 0),
            d.consultation_fee if d.consultation_fee is not None else 10**9,
            d.name.lower(),
        ),
    )[:MAX_DOCTORS]
