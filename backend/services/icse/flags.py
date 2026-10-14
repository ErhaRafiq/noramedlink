"""FE-3: deterministic flags for the clinical summary, built from a patient's report entities.

Only rule entities count: a BioBERT "model suggestion" never creates, raises or lowers a flag.
An unreadable or low-confidence value, an unknown unit or an implausible number is never flagged;
it is listed as "check against the original report" instead.

- Result flags: every reading of a test in the most recent report that has it; the most severe counts.
- Persistent: the latest two or more dated reports all outside the range in the same direction.
- Trend: earliest to latest dated reading, in the rule's unit, past the rule's change threshold.
  Only dates printed in a report count; an upload date says nothing about when a sample was taken.
- Chronic conditions: long-term conditions mentioned, not negated, not family history.
- Ongoing treatment: medicines not marked stopped, from the most recent report that lists medicines.

Every flag says why it was raised and which report, date and value it came from. Flags are for
physician review; none of them says a value is normal or a medicine is safe.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from services.icse.entities import SUGGESTION
from services.lab_rules import CHECK_ORIGINAL, RULES, SEVERITY_RANK, Assessment, assess, show

# The same reader and the same judgement as the per-report rules (lab_rules.assess): a value is
# never flagged here and passed on the report, or the other way round.


@dataclass
class Reading:
    report_id: Any
    date: str | None  # printed in the report; None if the report has no date
    name: str
    printed: str  # value and unit as printed
    value: float | tuple[int, int]  # in the rule's unit (blood pressure: systolic, diastolic)
    unit: str
    unit_note: str | None  # how a value printed without a unit was read
    entity: dict[str, Any]
    basis: str
    severity: str | None = None  # None: inside the rule's range
    direction: str | None = None  # "high" or "low"
    limit: str | None = None

    @classmethod
    def of(cls, report: dict, assessment: Assessment) -> Reading:
        graded = assessment.grade
        return cls(
            report["report_id"], report.get("date"), assessment.name, assessment.printed, assessment.value,
            assessment.unit, assessment.unit_note, assessment.entity, assessment.basis,
            graded.severity if graded else None, graded.direction if graded else None, graded.limit if graded else None,
        )  # fmt: skip

    def source(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "printed": self.printed,
            "value": self.value if isinstance(self.value, tuple) else round(self.value, 3),
            "unit": self.unit,
            "unit_assumed": self.unit_note is not None,
            "unit_note": self.unit_note,
            "report_flag": self.entity.get("report_flag"),
            "reference_range_printed": self.entity.get("reference_range"),
            "text": self.entity.get("evidence") or self.entity.get("text"),
        }


def _is_rule_entity(entity: dict[str, Any]) -> bool:
    return entity.get("method") != "biobert" and entity.get("certainty") != SUGGESTION


def _check(report: dict, assessment: Assessment) -> dict[str, Any]:
    return {
        "code": "CHECK_ORIGINAL",
        "kind": "check_original",
        "severity": "INFO",
        "subject": assessment.name,
        "message": f"{assessment.name}: {CHECK_ORIGINAL} ({assessment.problem}). No flag was raised from this value.",
        "reason": assessment.problem,
        "sources": [{"report_id": report["report_id"], "date": report.get("date"), "printed": assessment.printed}],
    }


def _collect(reports: list[dict]) -> tuple[dict[str, list[list[Reading]]], list[dict], dict[str, set]]:
    """Per test: one list of readings per report (in report order). Also check-original items, and
    which reports mention each test at all (even with no usable value)."""
    by_test: dict[str, list[list[Reading]]] = defaultdict(list)
    checks: list[dict] = []
    mentioned: dict[str, set] = defaultdict(set)
    for report in reports:
        per_test: dict[str, list[Reading]] = defaultdict(list)
        for entity in report.get("entities") or []:
            assessment = assess(entity)
            if assessment is None:
                continue
            mentioned[assessment.name].add(report["report_id"])
            if assessment.problem:
                checks.append(_check(report, assessment))
            else:
                per_test[assessment.name].append(Reading.of(report, assessment))
        for name, readings in per_test.items():
            by_test[name].append(readings)
    return by_test, checks, mentioned


def _worst(readings: list[Reading]) -> Reading:
    """The most severe reading; among equals, the first in the report."""
    return max(readings, key=lambda r: SEVERITY_RANK.get(r.severity or "INFO", 0))


_show = show


# --- the flags ------------------------------------------------------------------------------------


def _result_flag(name: str, readings: list[Reading]) -> dict | None:
    abnormal = [r for r in readings if r.severity]
    if not abnormal:
        return None
    worst = _worst(abnormal)
    others = (
        f" ({len(abnormal)} of {len(readings)} readings in this report are outside the range)"
        if len(readings) > 1
        else ""
    )
    return {
        "code": f"RESULT_{worst.direction.upper()}",
        "kind": "result",
        "severity": worst.severity,
        "subject": name,
        "message": f"{name} {_show(worst.value)} {worst.unit} is {worst.limit}{others}. For physician review.",
        "reason": f"most severe reading in the most recent report with this test: {worst.printed} ({worst.limit})",
        "rule": worst.basis,
        "sources": [r.source() for r in abnormal],
    }


def _by_date(test_readings: list[list[Reading]]) -> list[Reading]:
    """One reading per printed date (the most severe), oldest first; undated readings are left out."""
    dated: dict[str, list[Reading]] = defaultdict(list)
    for readings in test_readings:
        for reading in readings:
            if reading.date:
                dated[reading.date].append(reading)
    return [_worst(dated[day]) for day in sorted(dated)]


def _persistent_flag(name: str, test_readings: list[list[Reading]]) -> dict | None:
    days = _by_date(test_readings)
    if len(days) < 2 or not days[-1].severity:
        return None
    direction = days[-1].direction
    run = []
    for reading in reversed(days):
        if reading.severity and reading.direction == direction:
            run.append(reading)
        else:
            break
    if len(run) < 2:
        return None
    run.reverse()
    severity = max((r.severity for r in run), key=lambda s: SEVERITY_RANK[s])
    shown = ", ".join(f"{_show(r.value)} {r.unit} on {r.date}" for r in run)
    return {
        "code": f"PERSISTENT_{direction.upper()}",
        "kind": "persistent",
        "severity": severity,
        "subject": name,
        "message": f"{name} has been {direction} on {len(run)} dated reports in a row ({shown}). For physician review.",
        "reason": f"the latest {len(run)} dated readings are all {direction} (outside the rule's range)",
        "rule": run[-1].basis,
        "sources": [r.source() for r in run],
    }


def _trend_flag(name: str, test_readings: list[list[Reading]]) -> dict | None:
    rule = RULES.get(name)
    if not rule or not rule.trend:
        return None
    dated: dict[str, list[Reading]] = defaultdict(list)
    for readings in test_readings:
        for reading in readings:
            if reading.date:
                dated[reading.date].append(reading)
    if len(dated) < 2:
        return None
    trend = rule.trend
    up = trend.direction == "up"
    first_day, last_day = min(dated), max(dated)
    # The earliest date's best value against the latest date's worst, so a real change is not missed.
    baseline = (min if up else max)(dated[first_day], key=lambda r: r.value)
    latest = (max if up else min)(dated[last_day], key=lambda r: r.value)
    change = (latest.value - baseline.value) if up else (baseline.value - latest.value)
    if change <= 0:
        return None
    by_absolute = trend.absolute is not None and change >= trend.absolute - 1e-9
    by_relative = trend.relative is not None and baseline.value > 0 and change / baseline.value >= trend.relative - 1e-9
    if not (by_absolute or by_relative):
        return None
    word = "risen" if up else "fallen"
    threshold = " or ".join(
        part
        for part in (
            f"{trend.absolute:g} {rule.unit}" if trend.absolute is not None else None,
            f"{trend.relative:.0%}" if trend.relative is not None else None,
        )
        if part
    )
    return {
        "code": "TREND_RISING" if up else "TREND_FALLING",
        "kind": "trend",
        "severity": "CAUTION",
        "subject": name,
        "message": f"{name} has {word} from {baseline.value:g} ({baseline.date}) to {latest.value:g} ({latest.date}) "
        f"{rule.unit}, a change of {change:.3g} {rule.unit} ({change / baseline.value:.0%}). For physician review.",
        "reason": f"change from the earliest to the latest dated reading is at least {threshold}",
        "rule": trend.basis,
        "sources": [baseline.source(), latest.source()],
    }


def _chronic_flags(reports: list[dict]) -> list[dict]:
    mentions: dict[str, list[dict]] = defaultdict(list)
    info: dict[str, dict] = {}
    for report in reports:
        for entity in report.get("entities") or []:
            if (
                entity.get("type") == "condition"  # family history is its own type and never counts
                and _is_rule_entity(entity)
                and entity.get("negated") is False
                and entity.get("chronic")
            ):
                info.setdefault(entity["name"], entity)
                mentions[entity["name"]].append(
                    {"report_id": report["report_id"], "date": report.get("date"), "text": entity.get("text")}
                )
    return [
        {
            "code": "CHRONIC_CONDITION",
            "kind": "chronic_condition",
            "severity": "INFO",
            "subject": name,
            "message": f"Long-term condition mentioned in {len({m['report_id'] for m in sources})} report(s): {name}"
            f" (ICD-10 {info[name].get('icd10')}). Mentioned in report; not a confirmed diagnosis.",
            "reason": "a long-term condition is mentioned and not negated",
            "rule": "condition list in the demo knowledge base (ICD-10)",
            "sources": sources,
        }
        for name, sources in mentions.items()
    ]


def _treatment_flags(reports: list[dict]) -> tuple[list[dict], list[str]]:
    for report in reversed(reports):
        medicines = [
            e
            for e in report.get("entities") or []
            if e.get("type") == "medication" and _is_rule_entity(e) and not e.get("negated")
        ]
        if medicines:
            break
    else:
        return [], []
    ongoing: dict[str, dict] = {}
    for medicine in medicines:
        if medicine.get("status") != "stopped":
            ongoing.setdefault(medicine["name"], medicine)
    stopped = sorted({m["name"] for m in medicines if m.get("status") == "stopped"} - set(ongoing))
    where = f"report {report['report_id']}" + (f", dated {report['date']}" if report.get("date") else "")
    if not ongoing:
        return [], [
            f"The most recent medicine list ({where}) has no medicine marked as ongoing; stopped: {', '.join(stopped)}."
        ]

    def source(medicine: dict) -> dict:
        return {
            "report_id": report["report_id"],
            "date": report.get("date"),
            "medicine": medicine["name"],
            "dose": medicine.get("dose"),
            "frequency": medicine.get("frequency"),
            "in_knowledge_base": medicine.get("known", True),
            "text": medicine.get("text"),
        }

    flags = [
        {
            "code": "ONGOING_TREATMENT",
            "kind": "ongoing_treatment",
            "severity": "INFO",
            "subject": "Medicines",
            "message": f"Ongoing treatment in the most recent medicine list ({where}): {', '.join(ongoing)}."
            + (f" Marked stopped: {', '.join(stopped)}." if stopped else ""),
            "reason": "medicines in the most recent report that lists medicines, not marked stopped",
            "rule": "medicine names from the demo knowledge base, or a prescription pattern (Tab/Cap/Inj)",
            "stopped": stopped,
            "sources": [source(m) for m in ongoing.values()],
        }
    ]
    for name, medicine in ongoing.items():
        if medicine.get("high_alert"):
            flags.append(
                {
                    "code": "HIGH_ALERT_MEDICINE",
                    "kind": "high_alert_medicine",
                    "severity": "CAUTION",
                    "subject": name,
                    "message": f"{name} is on the high-alert medicine list: errors with it can cause serious harm. "
                    "For physician review.",
                    "reason": "an ongoing medicine is marked high-alert in the knowledge base",
                    "rule": "ISMP high-alert medication list (demo knowledge base)",
                    "sources": [source(medicine)],
                }
            )
    return flags, []


def printed_date(entities: list[dict[str, Any]]) -> str | None:
    """The sample or visit date printed in a report (ISO), or None. Never the upload date."""
    return next((e["value"] for e in entities or [] if e.get("type") == "report_date"), None)


def build_flags(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Flags for one patient. `reports`: oldest first, each {"report_id", "date" (printed in the
    report, ISO, or None), "entities"}."""
    by_test, checks, mentioned = _collect(reports)
    flags: list[dict] = []
    notes: list[str] = []
    order = {report["report_id"]: index for index, report in enumerate(reports)}
    for name, test_readings in by_test.items():
        latest_report = max(mentioned[name], key=order.get)
        latest = [r for readings in test_readings for r in readings if r.report_id == latest_report]
        for flag in (
            _result_flag(name, latest),
            _persistent_flag(name, test_readings),
            _trend_flag(name, test_readings),
        ):
            if flag:
                flags.append(flag)
    flags += _chronic_flags(reports)
    treatment, treatment_notes = _treatment_flags(reports)
    flags += treatment
    notes += treatment_notes
    undated = [r["report_id"] for r in reports if not r.get("date")]
    if undated:
        notes.append(
            f"{len(undated)} report(s) have no printed date; their values are not used for persistent or trend flags."
        )
    flags.sort(key=lambda f: -SEVERITY_RANK[f["severity"]])
    return {"flags": flags, "check_original": checks, "notes": notes}
