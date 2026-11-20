"""MSCIE: weight-based dose limits (table `dose_limits_per_kg.csv`, a DEMO knowledge base, not clinically reviewed).

For a medicine that has a row, the prescribed dose is checked against a per-kg limit times the patient's
recorded weight, never above the row's absolute adult maximum (so a heavy patient is not allowed more than an
adult). The weight comes from the patient's record only:

- no weight, for a patient the row applies to  -> "weight needed for dose check" (the per-kg check is skipped);
- a weight older than the app rule (demo) allows -> "weight is out of date, re-measure before dose check" (the old
  value is not used);
- otherwise the per-kg limit is applied. A patient at or above `applies_under_kg` is dosed as an adult: only the
  absolute maximum applies.

Nothing here assumes a weight, and no output says a dose is safe. Alerts are advisory, for physician review.
The absolute maximum alone does not need a weight, so it is checked whatever the weight status; for a medicine
that already has a row in dose_limits.csv those alerts come from there and are not repeated.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from services.knowledge.tables import records
from services.mscie.doses import dose_mg, times_per_day

if TYPE_CHECKING:
    from services.mscie.engine import Med, PatientContext, Proposed

APP_RULE = "app rule (demo)"
Alert = Callable[..., dict[str, Any]]


def _number(value: str) -> float | None:
    return float(value) if value not in ("", None) else None


def row_for(generic: str) -> dict | None:
    return {r["generic"]: r for r in records("dose_limits_per_kg")}.get(generic)


def _weight_line(weight: dict) -> str:
    return f"Weight {weight['value']:g} kg on {weight['date']} (entered by {weight['entered_by']})"


def _notice(make: Alert, rule: str, title: str, effect: str, item: Med, row: dict, evidence: list[str]) -> dict:
    return make(
        rule, "dose", "info", item, f"{item.label}: {title}", effect,
        "Record a current weight, then run the check again. No alert here does not mean the dose is right.",
        evidence, row["source"], "weight",
    )  # fmt: skip


def weight_dose_alerts(item: Med, proposed: Proposed, context: PatientContext, make: Alert) -> list[dict]:
    if not item.known or len(item.generics) != 1:
        return []
    row = row_for(item.generics[0])
    if row is None:
        return []
    age = context.age
    weight = context.weight
    adult_age = _number(row["applies_under_age"])
    kg_cutoff = _number(row["applies_under_kg"])
    is_child = age is None or (adult_age is not None and age < adult_age)
    alerts: list[dict] = []

    single = dose_mg(proposed.dose)
    per_day = times_per_day(proposed.frequency)
    prescribed = f"Prescribed: {proposed.dose or 'no dose'} {proposed.frequency or ''}".strip()
    has_old_rule = item.generics[0] in {r["generic"] for r in records("dose_limits")}

    # The absolute adult maximum, whatever the weight.
    abs_single, abs_daily = _number(row["max_single_mg"]), _number(row["max_daily_mg"])
    if not has_old_rule and single is not None:
        if abs_single is not None and single > abs_single:
            alerts.append(make(
                "DOSE-ABS-SINGLE", "dose", "major", item, f"{item.label}: single dose above the adult maximum",
                f"{proposed.dose} is more than the adult maximum single dose of {abs_single:g} mg "
                f"(demo knowledge base). Nobody is dosed above it by weight.",
                "Check the dose.", [prescribed], row["source"], "abs-single"))  # fmt: skip
        if abs_daily is not None and per_day and single * per_day > abs_daily:
            alerts.append(make(
                "DOSE-ABS-DAILY", "dose", "major", item, f"{item.label}: daily dose above the adult maximum",
                f"{proposed.dose} {proposed.frequency} is {single * per_day:g} mg a day, more than the adult "
                f"maximum of {abs_daily:g} mg a day (demo knowledge base).",
                "Check the dose and frequency.", [prescribed], row["source"], "abs-daily"))  # fmt: skip

    # Does the per-kg part apply to this patient, and is there a usable weight?
    if weight is None:
        if is_child:
            alerts.append(_notice(
                make, "WEIGHT-NEEDED", "weight needed for dose check",
                f"{item.label} is dosed by weight for children (demo knowledge base) and no weight is recorded, so "
                "the per-kg dose check was not done.", item, row, [prescribed]))  # fmt: skip
        return alerts
    if not weight["current"]:
        applies = is_child or (kg_cutoff is not None and weight["value"] < kg_cutoff)
        if applies:
            alerts.append(_notice(
                make, "WEIGHT-STALE", "weight is out of date, re-measure before dose check",
                f"The last weight is older than {weight['max_age_days']} days ({APP_RULE}), so it was not used "
                "and the per-kg dose check was not done.", item, row, [_weight_line(weight), prescribed]))  # fmt: skip
        return alerts
    if kg_cutoff is not None and weight["value"] >= kg_cutoff:
        return alerts  # dosed as an adult: the absolute maximum above is the limit
    if single is None:
        return alerts

    kg = weight["value"]
    evidence = [_weight_line(weight), prescribed]
    per_kg_single, per_kg_daily = _number(row["max_single_mg_per_kg"]), _number(row["max_daily_mg_per_kg"])
    if per_kg_single is not None:
        limit = per_kg_single * kg
        if limit < (abs_single if abs_single is not None else float("inf")) and single > limit:
            alerts.append(make(
                "DOSE-KG-SINGLE", "dose", "major", item, f"{item.label}: single dose above the per-kg limit",
                f"{proposed.dose} is {single / kg:.1f} mg/kg for {kg:g} kg; the usual maximum is "
                f"{per_kg_single:g} mg/kg ({limit:g} mg) per dose (demo knowledge base).",
                "Check the dose against the patient's weight.", evidence, row["source"], "kg-single"))  # fmt: skip
    if per_kg_daily is not None and per_day:
        limit = per_kg_daily * kg
        total = single * per_day
        if limit < (abs_daily if abs_daily is not None else float("inf")) and total > limit:
            alerts.append(make(
                "DOSE-KG-DAILY", "dose", "major", item, f"{item.label}: daily dose above the per-kg limit",
                f"{proposed.dose} {proposed.frequency} is {total:g} mg a day, {total / kg:.1f} mg/kg for {kg:g} kg; "
                f"the usual maximum is {per_kg_daily:g} mg/kg ({limit:g} mg) a day (demo knowledge base).",
                "Check the dose and frequency against the patient's weight.", evidence, row["source"], "kg-daily"))  # fmt: skip
    return alerts
