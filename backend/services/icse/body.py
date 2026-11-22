"""ICSE: the body measurements section of the physician summary (weight, height, BMI, weight trend).

Fixed rules only (services/body_measurements.py); the AI never sets or changes any of it. Every figure carries
its date and who entered it. When weight or height is missing the summary says "Weight not recorded" under
Missing data, never a default. The summary never says a value is normal, so a BMI band is shown as its range
("18.5 to 24.9 (WHO adult band)"). Everything is for physician review.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from services import body_measurements as bm

SOURCE = "Weight and height entered in the app"
HISTORY_POINTS = 6
BAND_TEXT = {
    "underweight": "below 18.5 (WHO adult band: underweight)",
    "normal range": "18.5 to 24.9 (WHO adult band)",
    "overweight": "25.0 to 29.9 (WHO adult band: overweight)",
    "obesity": "30.0 or more (WHO adult band: obesity)",
}
WHO = {"patient": "the patient", "doctor": "a doctor"}


def _readings(items: list[dict]) -> list[bm.Reading]:
    return [bm.Reading(i["value"], date.fromisoformat(i["date"]), i["added_by_role"]) for i in items]


def _line(reading: bm.Reading | None) -> dict[str, Any] | None:
    if reading is None:
        return None
    who = WHO.get(reading.added_by_role, "the patient")
    return {
        "value": reading.value,
        "date": reading.measured_on.isoformat(),
        "entered_by": who,
        "source": f"{SOURCE}: entered by {who} on {reading.measured_on.isoformat()}",
    }


def _change(change: bm.WeightChange | None) -> dict[str, Any] | None:
    if change is None:
        return None
    return {
        "percent": change.percent,
        "from_kg": change.from_kg,
        "from_date": change.from_date.isoformat(),
        "to_kg": change.to_kg,
        "to_date": change.to_date.isoformat(),
        "window_days": change.window_days,
        "threshold_percent": change.threshold_percent,
        "wording": change.wording,
        "basis": change.basis,
    }


def body_section(body: dict[str, Any], today: date) -> dict[str, Any]:
    """`body`: {"weights": [...], "heights": [...], "age", "pregnancy"}, oldest first (see versions.gather)."""
    weights, heights = _readings(body["weights"]), _readings(body["heights"])
    weight, height = bm.latest(weights), bm.latest(heights)
    age = body.get("age")
    pregnancy = body["pregnancy"]
    result = bm.bmi_result(
        weight.value if weight else None, height.value if height else None, age, pregnancy["status"] == "pregnant"
    )
    return {
        "source": SOURCE,
        "weight": _line(weight),
        "height": _line(height),
        "weight_current": bm.weight_is_current(weight.measured_on, age, today) if weight else None,
        "weight_max_age_days": bm.weight_max_age_days(age),
        "app_rule": bm.APP_RULE_LABEL,
        "bmi": {
            "value": result.value,
            "band": BAND_TEXT.get(result.category or ""),
            "band_note": result.category_note,
            "asian_note": result.asian_note,
            "weight_date": weight.measured_on.isoformat(),
            "height_date": height.measured_on.isoformat(),
        }
        if result and weight and height
        else None,
        "weight_history": [
            {"date": r.measured_on.isoformat(), "value": r.value, "entered_by": WHO.get(r.added_by_role, "the patient")}
            for r in weights[-HISTORY_POINTS:]
        ],
        "weight_change_flags": [_change(c) for c in bm.weight_change_flags(weights)],
        "change_since_previous": _change(bm.change_since_previous(weights)),
        "pregnancy": pregnancy,
    }


def body_flags(section: dict[str, Any]) -> list[dict[str, Any]]:
    """One flag per weight-change window that passed its threshold (shown under Flags, for physician review)."""
    flags = []
    for change in section["weight_change_flags"]:
        loss = change["percent"] < 0
        flags.append({
            "code": "WEIGHT_LOSS" if loss else "WEIGHT_GAIN",
            "kind": "weight_change",
            "severity": "CAUTION",
            "subject": "Body weight",
            "message": f"Weight changed {change['percent']:+.1f}% in {(date.fromisoformat(change['to_date']) - date.fromisoformat(change['from_date'])).days} days "
                       f"({change['from_kg']:g} kg on {change['from_date']} to {change['to_kg']:g} kg on {change['to_date']}): {change['wording']}.",
            "reason": f"the change within {change['window_days']} days is at least {change['threshold_percent']:g}%",
            "rule": change["basis"],
            "sources": [{
                "report_id": "body-measurements", "title": SOURCE, "kind": "body", "date": change["to_date"],
                "date_source": "recorded in the app", "printed": f"{change['to_kg']:g} kg",
                "value": change["to_kg"], "unit": "kg", "unit_assumed": False, "unit_note": None,
                "text": f"{change['from_kg']:g} kg on {change['from_date']}, {change['to_kg']:g} kg on {change['to_date']}",
            }],
        })  # fmt: skip
    return flags


def missing_lines(section: dict[str, Any]) -> list[str]:
    lines = []
    if section["weight"] is None:
        lines.append("Weight not recorded.")
    elif section["weight_current"] is False:
        lines.append(
            f"Weight is out of date: last recorded {section['weight']['date']}, older than "
            f"{section['weight_max_age_days']} days ({section['app_rule']})."
        )
    if section["height"] is None:
        lines.append("Height not recorded.")
    return lines


def _pregnancy_line(state: dict[str, Any]) -> str:
    status = state["status"]
    if status == "not_recorded":
        if state["expired"]:
            return (
                f"Pregnancy status: not recorded (a 'pregnant' status set {state['set_on']} is older than "
                f"{state['max_months']} months, {bm.APP_RULE_LABEL})."
            )
        return "Pregnancy status: not recorded."
    word = "pregnant" if status == "pregnant" else "not pregnant"
    return f"Pregnancy status: {word} (set {state['set_on']} by the {state['set_by_role']})."


def text_lines(section: dict[str, Any]) -> list[str]:
    lines = []
    for label, unit, line in (("Weight", "kg", section["weight"]), ("Height", "cm", section["height"])):
        lines.append(
            f"{label}: {line['value']:g} {unit} on {line['date']}, entered by {line['entered_by']}"
            if line
            else f"{label}: not recorded."
        )
    bmi = section["bmi"]
    if bmi:
        shown = f"BMI: {bmi['value']:g} kg/m2 (weight of {bmi['weight_date']}, height of {bmi['height_date']})"
        shown += f", {bmi['band']}." if bmi["band"] else f", {bmi['band_note']}."
        lines.append(shown)
        if bmi["asian_note"]:
            lines.append(bmi["asian_note"])
    elif section["weight"] and section["height"] is None:
        lines.append("BMI: needs a height.")
    if section["weight_current"] is False:
        lines.append(
            f"The weight is older than {section['weight_max_age_days']} days ({section['app_rule']}); re-measure before "
            "weight-based dose checks."
        )
    history = section["weight_history"]
    if len(history) > 1:
        lines.append("Weight history: " + ", ".join(f"{h['value']:g} kg ({h['date']})" for h in history) + ".")
    for change in section["weight_change_flags"]:
        lines.append(
            f"Weight change {change['percent']:+.1f}% within {change['window_days']} days: {change['wording']} "
            f"({change['basis']})."
        )
    if not section["weight_change_flags"] and section["change_since_previous"]:
        c = section["change_since_previous"]
        lines.append(f"Change since the previous reading: {c['percent']:+.1f}% ({c['from_date']} to {c['to_date']}).")
    lines.append(_pregnancy_line(section["pregnancy"]))
    return lines


def facts_lines(section: dict[str, Any]) -> list[str]:
    """The same figures as plain lines for the AI wording (so the guard knows every number)."""
    lines = []
    if section["weight"]:
        lines.append(f"- Weight {section['weight']['value']:g} kg on {section['weight']['date']}")
    if section["height"]:
        lines.append(f"- Height {section['height']['value']:g} cm on {section['height']['date']}")
    if section["bmi"]:
        lines.append(f"- BMI {section['bmi']['value']:g} kg/m2")
    return lines
