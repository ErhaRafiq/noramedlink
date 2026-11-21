"""MSCIE: weight-based dose limits (table `dose_limits_per_kg.csv`, a DEMO knowledge base, not clinically reviewed).

Each medicine has tiers taken from its FDA label, chosen by the patient's age (in months) and, where the label
splits by weight, by the recorded weight:

- a `not_covered` tier (below the label's minimum age) gives "verify dose: not covered by demo table";
- a `limit` tier checks the prescribed dose against its per-kg limit times the weight, never above the tier's
  absolute maximum. Above the maximum the alert has the tier's severity (red for major). A tier may also have a
  `caution_single_mg` (mg), `caution_single_mg_per_kg` or `caution_daily_mg_per_kg`: a dose above it but within
  the maximum is a yellow caution, not red;
- the per-kg part needs a weight. With none, or one older than the app rule (demo) allows, the per-kg check is
  skipped with "weight needed for dose check": an old weight is never used and no weight is ever assumed. The
  absolute maximums are still checked (the widest tier for the patient's age), because they do not depend on weight;
- a tier may carry a note shown when the dose is within its limit (azithromycin: the dose depends on the
  indication, and the prescription form has no indication field).

A medicine that already has a row in dose_limits.csv keeps those absolute alerts; they are not repeated here.
Nothing here says a dose is safe. Alerts are advisory, for physician review.
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


def _number(value: str | None) -> float | None:
    return float(value) if value not in ("", None) else None


def tiers_for(generic: str) -> list[dict]:
    return [r for r in records("dose_limits_per_kg") if r["generic"] == generic]


def _age_matches(tier: dict, months: int) -> bool:
    low, high = _number(tier["age_from_months"]), _number(tier["age_to_months"])
    return (low is None or months >= low) and (high is None or months <= high)  # both ends inclusive


def _weight_matches(tier: dict, kg: float) -> bool:
    low, high = _number(tier["weight_from_kg"]), _number(tier["weight_to_kg"])
    return (low is None or kg >= low) and (high is None or kg < high)  # from inclusive, to exclusive


def _uses_weight(tier: dict) -> bool:
    columns = (
        "weight_from_kg", "weight_to_kg", "max_single_mg_per_kg", "max_daily_mg_per_kg",
        "caution_single_mg_per_kg", "caution_daily_mg_per_kg",
    )  # fmt: skip
    return any(tier[c] != "" for c in columns)


def _weight_line(weight: dict) -> str:
    return f"Weight {weight['value']:g} kg on {weight['date']} (entered by {weight['entered_by']})"


def _notice(
    make: Alert, rule: str, title: str, effect: str, management: str, item: Med, source: str, evidence: list[str]
):
    return make(
        rule, "dose", "info", item, f"{item.label}: {title}", effect, management, evidence, source, rule.lower()
    )


def _widest_absolute(tiers: list[dict]) -> dict | None:
    """For a patient whose tier cannot be chosen (no usable weight): the absolute maximums only, taken from the
    most permissive limit tier for the patient's age, so only a dose over every tier's maximum is flagged."""
    limit_tiers = [t for t in tiers if t["kind"] == "limit" and (t["max_single_mg"] or t["max_daily_mg"])]
    if not limit_tiers:
        return None
    top = max(limit_tiers, key=lambda t: _number(t["max_single_mg"]) or 0)
    daily = max((_number(t["max_daily_mg"]) or 0 for t in limit_tiers), default=0)
    return {
        **top,
        "max_single_mg_per_kg": "", "max_daily_mg_per_kg": "", "within_note": "",
        "max_daily_mg": f"{daily:g}" if daily else "",
    }  # fmt: skip


def _tier_alerts(
    make: Alert, item: Med, proposed: Proposed, tier: dict, kg: float | None, evidence: list[str], has_old_rule: bool
) -> list[dict]:
    """Alerts for one tier. `kg` is None when only the absolute maximums can be checked."""
    note = f" {tier['over_note']}" if tier["over_note"] else ""
    single, per_day = dose_mg(proposed.dose), times_per_day(proposed.frequency)
    alerts: list[dict] = []

    def limit(per_kg: str, absolute: str) -> tuple[float | None, bool]:
        """The binding limit and whether it is the per-kg one (the lower of the two, never above the absolute)."""
        by_weight = _number(per_kg) * kg if kg is not None and _number(per_kg) is not None else None
        top = _number(absolute)
        if by_weight is not None and (top is None or by_weight < top):
            return by_weight, True
        return top, False

    if single is None:
        return alerts
    cap, by_kg = limit(tier["max_single_mg_per_kg"], tier["max_single_mg"])
    caution = _number(tier["caution_single_mg"])
    if cap is not None and single > cap and (by_kg or not has_old_rule):
        if by_kg:
            what = (
                f"{single / kg:.1f} mg/kg for {kg:g} kg; the limit is {_number(tier['max_single_mg_per_kg']):g} mg/kg "
                f"({cap:g} mg)"
            )
        else:
            what = f"more than the maximum single dose of {cap:g} mg"
        alerts.append(make(
            "DOSE-KG-SINGLE" if by_kg else "DOSE-ABS-SINGLE", "dose", tier["severity"], item,
            f"{item.label}: single dose above the {'per-kg' if by_kg else 'adult'} limit",
            f"{proposed.dose} is {what} (demo knowledge base).{note}",
            "Check the dose against the patient's weight." if by_kg else "Check the dose.",
            evidence, tier["source"], "kg-single" if by_kg else "abs-single"))  # fmt: skip
    elif caution is not None and single > caution and not has_old_rule:
        alerts.append(make(
            "DOSE-ABS-CAUTION", "dose", "moderate", item, f"{item.label}: above the usual single dose",
            f"{proposed.dose} is more than {caution:g} mg (demo knowledge base). {tier['caution_note']}",
            "Check the indication and the dose.", evidence, tier["source"], "abs-caution"))  # fmt: skip
    elif (
        kg is not None
        and _number(tier["caution_single_mg_per_kg"]) is not None
        and single > _number(tier["caution_single_mg_per_kg"]) * kg
    ):
        alerts.append(make(
            "DOSE-KG-CAUTION", "dose", "moderate", item, f"{item.label}: above the usual single dose per kg",
            f"{proposed.dose} is {single / kg:.1f} mg/kg for {kg:g} kg; the usual limit is "
            f"{_number(tier['caution_single_mg_per_kg']):g} mg/kg (demo knowledge base). {tier['caution_note']}",
            "Check the dose against the patient's weight.", evidence, tier["source"], "kg-caution"))  # fmt: skip
    if per_day:
        cap, by_kg = limit(tier["max_daily_mg_per_kg"], tier["max_daily_mg"])
        total = single * per_day
        if cap is not None and total > cap and (by_kg or not has_old_rule):
            if by_kg:
                what = (
                    f"{total:g} mg a day, {total / kg:.1f} mg/kg for {kg:g} kg; the limit is "
                    f"{_number(tier['max_daily_mg_per_kg']):g} mg/kg ({cap:g} mg) a day"
                )
            else:
                what = f"{total:g} mg a day, more than the maximum of {cap:g} mg a day"
            alerts.append(make(
                "DOSE-KG-DAILY" if by_kg else "DOSE-ABS-DAILY", "dose", tier["severity"], item,
                f"{item.label}: daily dose above the {'per-kg' if by_kg else 'adult'} limit",
                f"{proposed.dose} {proposed.frequency} is {what} (demo knowledge base).{note}",
                "Check the dose and frequency.", evidence, tier["source"], "kg-daily" if by_kg else "abs-daily"))  # fmt: skip
        elif (
            kg is not None
            and _number(tier["caution_daily_mg_per_kg"]) is not None
            and total > _number(tier["caution_daily_mg_per_kg"]) * kg
        ):
            alerts.append(make(
                "DOSE-KG-CAUTION", "dose", "moderate", item, f"{item.label}: above the usual daily dose per kg",
                f"{proposed.dose} {proposed.frequency} is {total:g} mg a day, {total / kg:.1f} mg/kg for {kg:g} kg; "
                f"the usual limit is {_number(tier['caution_daily_mg_per_kg']):g} mg/kg a day (demo knowledge base). "
                f"{tier['caution_note']}",
                "Check the dose and frequency.", evidence, tier["source"], "kg-daily-caution"))  # fmt: skip
    return alerts


def weight_dose_alerts(item: Med, proposed: Proposed, context: PatientContext, make: Alert) -> list[dict]:
    if not item.known or len(item.generics) != 1:
        return []
    generic = item.generics[0]
    tiers = tiers_for(generic)
    if not tiers:
        return []
    source = tiers[0]["source"]
    prescribed = f"Prescribed: {proposed.dose or 'no dose'} {proposed.frequency or ''}".strip()
    months = context.age_months
    if months is None:
        return [_notice(
            make, "AGE-NEEDED", "age needed for dose check",
            "The patient's age is not known, so the weight-based dose check was not done (demo knowledge base).",
            "Check the date of birth on the profile.", item, source, [prescribed])]  # fmt: skip

    by_age = [t for t in tiers if _age_matches(t, months)]
    if not by_age:
        return []  # no tier for this age: an adult is covered by the absolute rule in dose_limits.csv, if any
    not_covered = [t for t in by_age if t["kind"] == "not_covered"]
    if not_covered:
        return [_notice(
            make, "NOT-COVERED", "verify dose: not covered by demo table", not_covered[0]["over_note"],
            "Check the dose in a full drug reference. No alert does not mean the dose is right.",
            item, not_covered[0]["source"], [prescribed])]  # fmt: skip

    has_old_rule = generic in {r["generic"] for r in records("dose_limits")}
    weight = context.weight
    if any(_uses_weight(t) for t in by_age):
        problem = None
        if weight is None:
            problem = _notice(
                make, "WEIGHT-NEEDED", "weight needed for dose check",
                f"{item.label} is dosed by weight for this patient's age (demo knowledge base) and no weight is "
                "recorded, so the per-kg dose check was not done. The absolute maximums were still checked.",
                "Record a current weight, then run the check again. No alert does not mean the dose is right.",
                item, source, [prescribed])  # fmt: skip
        elif not weight["current"]:
            problem = _notice(
                make, "WEIGHT-STALE", "weight needed for dose check: weight is out of date, re-measure before dose check",
                f"The last weight is older than {weight['max_age_days']} days ({APP_RULE}), so it was not used and "
                "the per-kg dose check was not done. The absolute maximums were still checked.",
                "Re-measure the weight, then run the check again. No alert does not mean the dose is right.",
                item, source, [_weight_line(weight), prescribed])  # fmt: skip
        if problem is not None:
            widest = _widest_absolute(by_age)
            absolute = _tier_alerts(make, item, proposed, widest, None, [prescribed], has_old_rule) if widest else []
            return [problem, *absolute]
        kg = float(weight["value"])
        by_age = [t for t in by_age if _weight_matches(t, kg)]
        if not by_age:
            return []
        tier = by_age[0]
        evidence = [_weight_line(weight), prescribed]
        alerts = _tier_alerts(make, item, proposed, tier, kg, evidence, has_old_rule)
    else:
        tier = by_age[0]
        evidence = [prescribed]
        alerts = _tier_alerts(make, item, proposed, tier, None, evidence, has_old_rule)
    if not alerts and tier["within_note"]:
        alerts.append(_notice(
            make, "INDICATION-NOTE", "check the dose for the indication", tier["within_note"],
            "Check the dose for the indication.", item, tier["source"], evidence))  # fmt: skip
    return alerts
