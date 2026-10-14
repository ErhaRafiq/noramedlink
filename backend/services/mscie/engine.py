"""MSCIE FE-1, FE-2, FE-5: check proposed medicines against the patient's history.

Checks, all from the CSV knowledge base: allergies (and class cross-reactivity), drug-drug
interactions, duplicate therapy, drug-disease and drug-lab contraindications, doses, and
high-alert medicines. Each alert says what it is, why (the rule, its source, and the exact item in
the patient's record that triggered it) and what to do. A medicine the knowledge base does not know
gets "no data", never "safe". Pure functions: the patient context is built elsewhere (context.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Any

from services import knowledge
from services.knowledge.tables import records
from services.mscie.doses import dose_mg, times_per_day

LEVEL = {"contraindicated": "HIGH_RISK", "major": "HIGH_RISK", "moderate": "CAUTION", "minor": "INFO", "info": "INFO"}
RANK = {"info": 0, "minor": 1, "moderate": 2, "major": 3, "contraindicated": 4}
NEEDS_JUSTIFICATION = {"contraindicated", "major"}


@dataclass(frozen=True)
class Med:
    """A medicine, resolved against the knowledge base where possible."""

    name: str  # as written or chosen
    generics: tuple[str, ...] = ()
    classes: tuple[str, ...] = ()
    high_alert: bool = False
    source: str = ""  # where it comes from in the record ("latest report list", "medication schedule", ...)
    ref: dict = field(default_factory=dict, compare=False, hash=False)  # report id, date

    @property
    def known(self) -> bool:
        return bool(self.generics)

    @property
    def label(self) -> str:
        return " + ".join(self.generics) if self.generics else self.name


@dataclass
class PatientContext:
    medicines: list[Med] = field(default_factory=list)  # ongoing
    previous: list[dict] = field(default_factory=list)  # {"generic", "problem": bool, "note"}
    conditions: list[dict] = field(default_factory=list)  # {"name", "source"}
    allergies: list[dict] = field(default_factory=list)  # {"name", "generics", "classes", "source"}
    allergy_status: str = "not_recorded"  # listed | none_recorded | not_recorded
    labs: dict[str, dict] = field(default_factory=dict)  # test -> {"value", "unit", "date", "source"}


@dataclass
class Proposed:
    medicine: str
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None


def resolve(name: str, source: str = "", ref: dict | None = None) -> Med:
    info = knowledge.resolve_medication(name)
    if info is None:
        return Med(name=" ".join(name.split()), source=source, ref=ref or {})
    return Med(
        name=info.display_name, generics=info.generics, classes=info.classes, high_alert=info.high_alert,
        source=source, ref=ref or {},
    )  # fmt: skip


@cache
def _sources() -> dict[str, str]:
    return {row["key"]: row["description"] for row in records("sources")}


def cite(source: str) -> list[dict[str, str]]:
    """'FDA-LABEL (warfarin); ONC-DDI' -> [{"label", "reference"}] with the full reference."""
    import re

    out = []
    for part in re.split(r";(?![^()]*\))", source or ""):
        part = part.strip()
        if not part:
            continue
        key = part.split(" ")[0]
        out.append({"label": part, "reference": _sources().get(key, "")})
    return out


def matches(reference: str, med: Med) -> bool:
    if reference.startswith("class:"):
        return reference.removeprefix("class:") in med.classes
    return reference in med.generics


def _alert(rule_id: str, kind: str, severity: str, item: Med, title: str, effect: str, management: str,
           evidence: list[str], source: str, about: str = "") -> dict[str, Any]:  # fmt: skip
    return {
        "id": f"{rule_id}:{item.label}:{about}".rstrip(":"),
        "rule_id": rule_id,
        "kind": kind,
        "severity": severity,
        "level": LEVEL[severity],
        "requires_justification": severity in NEEDS_JUSTIFICATION,
        "medicine": item.label,
        "title": title,
        "effect": effect,
        "management": management,
        "evidence": evidence,
        "sources": cite(source),
    }


def _where(med: Med) -> str:
    when = f", {med.ref['date']}" if med.ref.get("date") else ""
    return f"{med.label} ({med.source}{when})"


def _allergy_alerts(item: Med, context: PatientContext) -> list[dict]:
    alerts = []
    cross = records("allergy_cross_reactivity")
    for allergy in context.allergies:
        evidence = [f"Allergy recorded: {allergy['name']} ({allergy['source']})"]
        if set(allergy.get("generics") or ()) & set(item.generics):
            alerts.append(_alert("ALLERGY", "allergy", "contraindicated", item, f"Allergy to {item.label}",
                                 "The patient's record lists an allergy to this medicine.",
                                 "Do not use; choose a medicine from another class.", evidence, "AAAAI-2022", allergy["name"]))  # fmt: skip
            continue
        for row in cross:
            if row["allergy_class"] in allergy.get("classes", ()) and matches(row["target"], item):
                alerts.append(_alert(row["id"], "allergy", row["severity"], item,
                                     f"{allergy['name'].capitalize()} allergy: {item.label} ({row['target'].removeprefix('class:')})",
                                     row["effect"], row["management"], evidence, row["source"], allergy["name"]))  # fmt: skip
    return alerts


def _interaction_alerts(item: Med, others: list[Med]) -> list[dict]:
    alerts = []
    for other in others:
        if not other.known or other.generics == item.generics:
            continue
        for row in records("interactions"):
            if (matches(row["a"], item) and matches(row["b"], other)) or (
                matches(row["b"], item) and matches(row["a"], other)
            ):
                alerts.append(_alert(row["id"], "interaction", row["severity"], item,
                                     f"{item.label} with {other.label}", row["effect"], row["management"],
                                     [f"Also taking: {_where(other)}"], row["source"], other.label))  # fmt: skip
    return alerts


REACTION_WORDS = ("allerg", "rash", "swelling", "breath", "anaphyla", "hives", "itch", "reaction")


def _previous_alerts(item: Med, context: PatientContext) -> list[dict]:
    """A recorded reaction to, or stopping of, this medicine before."""
    alerts = []
    for previous in context.previous:
        if previous["generic"] not in item.generics or not previous.get("problem"):
            continue
        reaction = any(word in previous["note"].lower() for word in REACTION_WORDS)
        alerts.append(_alert("PREVIOUS", "previous_response", "major" if reaction else "moderate", item,
                             f"{item.label}: {'a previous reaction' if reaction else 'stopped before'}",
                             "The record shows a problem with this medicine before.",
                             "Check what happened before prescribing it again.",
                             [f"Recorded: {previous['note']}"], "", previous["note"][:40]))  # fmt: skip
    return alerts


def _duplicate_alerts(item: Med, others: list[Med]) -> list[dict]:
    alerts = []
    for other in others:
        if item.generics and other.generics == item.generics:
            alerts.append(_alert("DUP-SAME", "duplicate", "moderate", item, f"Duplicate: {item.label} is already taken",
                                 "The same medicine is already in the patient's current medicines.",
                                 "Check that a second supply or a dose change is intended.",
                                 [f"Already taking: {_where(other)}"], "", other.source))  # fmt: skip
    for row in records("duplicate_classes"):
        if row["class"] not in item.classes:
            continue
        for other in others:
            if row["class"] in other.classes and other.generics != item.generics:
                same = False
                alerts.append(_alert(f"DUP-{row['class']}", "duplicate", row["severity"], item,
                                     f"{'Same medicine' if same else 'Same class'}: {item.label} and {other.label} ({row['class']})",
                                     row["effect"], "Check that both are intended; usually use one.",
                                     [f"Also taking: {_where(other)}"], row["source"], other.label))  # fmt: skip
    return alerts


def _contraindication_alerts(item: Med, context: PatientContext) -> list[dict]:
    alerts = []
    conditions = {c["name"]: c for c in context.conditions}
    for row in records("contraindications"):
        if not matches(row["drug"], item) or (row["exclude"] and row["exclude"] in item.generics):
            continue
        if row["condition"]:
            found = conditions.get(row["condition"])
            if found:
                alerts.append(_alert(row["id"], "contraindication", row["severity"], item,
                                     f"{item.label} with {row['condition']}", row["effect"], row["management"],
                                     [f"Condition mentioned: {row['condition']} ({found['source']})"], row["source"], row["condition"]))  # fmt: skip
            continue
        lab = context.labs.get(row["lab_test"])
        if lab is None:
            continue
        limit = float(row["lab_value"])
        hit = lab["value"] < limit if row["lab_operator"] == "<" else lab["value"] > limit
        if hit:
            when = f" on {lab['date']}" if lab.get("date") else ""
            alerts.append(_alert(row["id"], "contraindication", row["severity"], item,
                                 f"{item.label} with {row['lab_test']} {row['lab_operator']} {row['lab_value']:s}",
                                 row["effect"], row["management"],
                                 [f"Latest {row['lab_test']}: {lab['value']:g} {lab.get('unit', '')}{when} ({lab['source']})".replace("  ", " ")],
                                 row["source"], row["lab_test"]))  # fmt: skip
    # Of several rules on the same lab test (eGFR < 30 and < 45), only the most severe one.
    best: dict[str, dict] = {}
    for alert in alerts:
        key = (alert["rule_id"].split("-")[0], alert["id"].split(":")[-1])
        if key not in best or RANK[alert["severity"]] > RANK[best[key]["severity"]]:
            best[key] = alert
    return [a for a in alerts if best[(a["rule_id"].split("-")[0], a["id"].split(":")[-1])] is a] if alerts else []


def _dose_alerts(item: Med, proposed: Proposed) -> list[dict]:
    if not item.known or len(item.generics) != 1:
        return []
    limits = {row["generic"]: row for row in records("dose_limits")}.get(item.generics[0])
    single = dose_mg(proposed.dose)
    if limits is None or single is None:
        return []
    alerts = []
    per_day = times_per_day(proposed.frequency)
    source = limits["source"]
    if limits["max_single_mg"] and single > float(limits["max_single_mg"]):
        alerts.append(_alert("DOSE-SINGLE", "dose", "major", item, f"{item.label}: single dose above the usual maximum",
                             f"{proposed.dose} is more than the usual maximum single dose of {float(limits['max_single_mg']):g} mg.",
                             "Check the dose.", [f"Prescribed: {proposed.dose} {proposed.frequency or ''}".strip()], source, "single"))  # fmt: skip
    if per_day and single * per_day > float(limits["max_daily_mg"]):
        alerts.append(_alert("DOSE-DAILY", "dose", "major", item, f"{item.label}: daily dose above the usual maximum",
                             f"{proposed.dose} {proposed.frequency} is {single * per_day:g} mg a day, more than the usual maximum "
                             f"of {float(limits['max_daily_mg']):g} mg a day.",
                             "Check the dose and frequency.", [f"Prescribed: {proposed.dose} {proposed.frequency}"], source, "daily"))  # fmt: skip
    return alerts


def check_item(item: Med, proposed: Proposed, others: list[Med], context: PatientContext) -> list[dict]:
    """Every alert for one proposed medicine, most severe first."""
    if not item.known:
        return [
            _alert(
                "NO-DATA",
                "no_data",
                "info",
                item,
                f"No data for {item.name}",
                "This medicine is not in the knowledge base, so no interaction, allergy or dose check was possible.",
                "Check it in a full drug reference. No data does not mean safe.",
                [],
                "",
            )
        ]
    alerts = [
        *_allergy_alerts(item, context),
        *_interaction_alerts(item, others),
        *_duplicate_alerts(item, others),
        *_contraindication_alerts(item, context),
        *_dose_alerts(item, proposed),
        *_previous_alerts(item, context),
    ]
    if item.high_alert:
        alerts.append(_alert("HIGH-ALERT", "high_alert", "info", item, f"{item.label} is a high-alert medicine",
                             "Errors with this medicine can cause serious harm.", "Double-check the dose, route and monitoring.",
                             [], "ISMP"))  # fmt: skip
    unique = {alert["id"]: alert for alert in alerts}
    return sorted(unique.values(), key=lambda a: -RANK[a["severity"]])


def worst(alerts: list[dict]) -> str | None:
    return max((a["severity"] for a in alerts), key=lambda s: RANK[s], default=None)


def check(context: PatientContext, items: list[Proposed]) -> list[dict[str, Any]]:
    """Each proposed medicine with its alerts; the other proposed medicines count as taken too."""
    resolved = [resolve(p.medicine, "this prescription") for p in items]
    results = []
    for index, (proposed, med) in enumerate(zip(items, resolved, strict=True)):
        others = [*context.medicines, *(m for i, m in enumerate(resolved) if i != index)]
        alerts = check_item(med, proposed, others, context)
        results.append({
            "medicine": proposed.medicine,
            "resolved": {"name": med.name, "generics": list(med.generics), "classes": list(med.classes),
                         "high_alert": med.high_alert, "known": med.known},
            "dose": proposed.dose, "frequency": proposed.frequency, "duration": proposed.duration,
            "alerts": alerts,
            "worst": worst(alerts),
        })  # fmt: skip
    return results
