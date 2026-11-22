"""The emergency gate: runs before any doctor is shown or anything is saved (AGENTS.md 6.3).

1. The red-flag rules (services/symptom_checker.red_flags) read the reason the patient wrote.
2. A fixed checklist (home_visit_checklist.csv) asks the patient to answer every question; one "yes" is an
   emergency. A missing answer is not an answer: the request is incomplete.
3. Only then is the reason matched to a specialty; one that is not for home visits points to a clinic visit.

Any emergency result carries only the 1122 notice and no doctor. Medical text is never logged here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from services.home_visits import suitability
from services.knowledge.tables import records
from services.symptom_checker import EMERGENCY_NOTICE, red_flags, suggest_specialties

CLEAR, EMERGENCY, INCOMPLETE, NOT_SUITABLE = "clear", "emergency", "incomplete", "not_suitable"
MIN_REASON_CHARS = 5
CLINIC_NOTICE = "This kind of problem is better seen in a clinic. Book an appointment with a doctor instead."


@dataclass
class GateResult:
    status: str
    message: str
    specialty: str | None = None
    red_flags: list[str] = field(default_factory=list)  # the warning signs found in the reason
    checklist_yes: list[str] = field(default_factory=list)  # ids of the checklist questions answered "yes"
    unanswered: list[str] = field(default_factory=list)  # ids not answered yet

    @property
    def allowed(self) -> bool:
        return self.status == CLEAR


def checklist() -> list[dict]:
    return [{"id": r["id"], "question": r["question"]} for r in records("home_visit_checklist")]


def assess(reason: str, answers: dict[str, bool]) -> GateResult:
    """Emergency first, then incomplete, then suitability. `answers` maps checklist id to True (yes) or False."""
    flags = [f.label for f in red_flags(reason or "")]
    ids = [q["id"] for q in checklist()]
    yes = [i for i in ids if answers.get(i) is True]
    if flags or yes:
        return GateResult(EMERGENCY, EMERGENCY_NOTICE, red_flags=flags, checklist_yes=yes)
    unanswered = [i for i in ids if answers.get(i) is not False]
    if len((reason or "").strip()) < MIN_REASON_CHARS:
        return GateResult(INCOMPLETE, "Describe the problem in a few words.", unanswered=unanswered)
    if unanswered:
        return GateResult(INCOMPLETE, "Answer every safety question before sending the request.", unanswered=unanswered)
    specialty = suggest_specialties(reason)[0].specialty
    if not suitability.is_suitable(specialty):
        return GateResult(NOT_SUITABLE, CLINIC_NOTICE, specialty=specialty)
    return GateResult(CLEAR, "", specialty=specialty)
