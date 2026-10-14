"""The one source of truth for lab ranges, thresholds and units.

Both the per-report rules (rule_validation_service) and the clinical-summary flags (icse/flags)
read values with the same reader (icse/entities) and grade them here, so a value is never flagged
in one place and passed in the other.

General adult ranges for physician review. Each lab prints its own range; these rules never call
a value normal or safe.

Units: a value is converted to the rule's unit only from a unit listed for that rule. A value
printed with no unit is accepted only where exactly one reading makes sense (e.g. a platelet
count of 2,50,000 can only be per microlitre); anything else, and anything unreadable, read with
low confidence or impossible, is "check against the original report" and is never graded.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

DEMO = "app rule (demo), not a clinical standard"
LAB_RULES_VERSION = 1  # bump when a range, unit or threshold changes: stored summaries go out of date
SEVERITY_RANK = {"INFO": 0, "CAUTION": 1, "HIGH_RISK": 2}
LOW_CONFIDENCE = 0.90
CHECK_ORIGINAL = "check against the original report"


def _factor(k: float) -> Callable[[float], float]:
    return lambda value: value * k


SAME = _factor(1)
PER_UL = _factor(0.001)
COUNT_UNITS = {
    "x10^9/l": SAME,
    "10^9/l": SAME,
    "x10^3/ul": SAME,
    "10^3/ul": SAME,
    "k/ul": SAME,
    "/ul": PER_UL,
    "cells/ul": PER_UL,
    "/cumm": PER_UL,
    "cells/cumm": PER_UL,
    "/cmm": PER_UL,
    "cells/cmm": PER_UL,
    "lakh": _factor(100),
    "lakhs": _factor(100),
    "lakh/cumm": _factor(100),
    "lakhs/cumm": _factor(100),
}


@dataclass(frozen=True)
class Unitless:
    """A band where a number printed without a unit can only be one unit."""

    low: float
    high: float
    convert: Callable[[float], float] = SAME
    label: str | None = None  # e.g. "per microlitre"; None means the rule's own unit


@dataclass(frozen=True)
class Trend:
    direction: str  # "up" or "down": the worsening direction
    absolute: float | None = None  # change in the rule's unit
    relative: float | None = None  # fraction of the baseline (0.25 = 25%)
    basis: str = DEMO


@dataclass(frozen=True)
class TestRule:
    name: str  # the knowledge-base test name
    code: str  # warning code prefix: HEMOGLOBIN -> HEMOGLOBIN_LOW / HEMOGLOBIN_HIGH
    unit: str
    units: dict[str, Callable[[float], float]]
    plausible: tuple[float, float]  # outside this (in the rule's unit) the reading is not trusted
    unitless: tuple[Unitless, ...] = ()
    low: float | None = None  # below is low
    high: float | None = None  # above is high
    critical_low: float | None = None  # below is HIGH_RISK
    critical_high: float | None = None  # at or above is HIGH_RISK
    basis: str = "general adult range used by the app's rules"
    trend: Trend | None = None
    high_code: str | None = None
    low_code: str | None = None

    def code_for(self, direction: str) -> str:
        custom = self.high_code if direction == "high" else self.low_code
        return custom or f"{self.code}_{direction.upper()}"


@dataclass(frozen=True)
class Grade:
    severity: str  # CAUTION or HIGH_RISK
    direction: str  # high or low
    limit: str  # "over 1.3 mg/dL"


@dataclass(frozen=True)
class Value:
    value: float  # in the rule's unit
    unit_note: str | None = None  # how a value printed without a unit was read


@dataclass(frozen=True)
class Problem:
    reason: str  # why the value cannot be used; shown with "check against the original report"


def _glucose(name: str, high: float, basis: str) -> TestRule:
    return TestRule(
        name, "GLUCOSE", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(18.0)}, (10, 2000),
        # 40-1000 can only be mg/dL; 2.5-20 can only be mmol/L. 20-40 could be either: checked by hand.
        (Unitless(40, 1000), Unitless(2.5, 20, _factor(18.0), "mmol/L")),
        low=70, high=high, critical_low=54, critical_high=300, basis=basis, high_code="HIGH_GLUCOSE",
    )  # fmt: skip


_HYPO = "under 70 low and under 54 very low (ADA)"
RULES: dict[str, TestRule] = {
    rule.name: rule
    for rule in [
        TestRule(
            "Hemoglobin", "HEMOGLOBIN", "g/dL", {"g/dl": SAME, "gm/dl": SAME, "gm%": SAME, "g/l": _factor(0.1)},
            (2, 25), (Unitless(3, 22), Unitless(30, 220, _factor(0.1), "g/L")),
            low=12.0, high=17.5, critical_low=7.0,
            basis=f"12-17.5 g/dL; under 7 g/dL as critical is an {DEMO}",
            trend=Trend("down", absolute=2.0, basis="a fall of 2 g/dL (the ISTH major-bleeding threshold); used here for review only"),
        ),
        TestRule(
            "WBC Count", "WBC", "x10^9/L", COUNT_UNITS, (0.1, 300),
            (Unitless(0.5, 100), Unitless(500, 300000, PER_UL, "per microlitre")), low=4.0, high=11.0,
        ),
        TestRule(
            "Platelet Count", "PLATELETS", "x10^9/L", COUNT_UNITS, (1, 3000),
            (Unitless(5, 1500), Unitless(5000, 3000000, PER_UL, "per microlitre")),
            low=150, high=450, critical_low=50, basis=f"150-450 x10^9/L; under 50 as critical is an {DEMO}",
            trend=Trend("down", relative=0.5),
        ),
        _glucose("Fasting Blood Sugar", 125, f"ADA: fasting 126 mg/dL or more is in the diabetes range; {_HYPO}"),
        _glucose("Random Blood Sugar", 199, f"ADA: random 200 mg/dL or more is in the diabetes range; {_HYPO}"),
        _glucose("Post Prandial Blood Sugar", 199, f"ADA: 2-hour 200 mg/dL or more is in the diabetes range; {_HYPO}"),
        # A glucose value that does not say fasting, random or after a meal: the random threshold,
        # since the higher fasting one would flag ordinary non-fasting values.
        _glucose("Blood Glucose", 199, f"ADA: a non-fasting 200 mg/dL or more is in the diabetes range; {_HYPO}"),
        TestRule(
            "HbA1c", "HBA1C", "%", {"%": SAME, "mmol/mol": lambda v: v * 0.09148 + 2.152}, (3, 20), (Unitless(3, 20),),
            high=6.4, basis="ADA: 6.5% or more is in the diabetes range", high_code="HIGH_HBA1C",
            trend=Trend("up", absolute=1.0),
        ),
        TestRule(
            "Creatinine", "CREATININE", "mg/dL", {"mg/dl": SAME, "umol/l": _factor(1 / 88.4)}, (0.1, 30),
            (Unitless(0.2, 15), Unitless(30, 2000, _factor(1 / 88.4), "umol/L")), high=1.3,
            high_code="KIDNEY_RISK_CREATININE",
            trend=Trend("up", absolute=0.3, relative=0.5,
                        basis="KDIGO 2012 AKI criteria (a rise of 0.3 mg/dL, or 1.5 times baseline), applied here without their time window"),
        ),
        TestRule(
            "eGFR", "EGFR", "mL/min/1.73m2",
            {"ml/min/1.73m2": SAME, "ml/min/1.73m^2": SAME, "ml/min/1.73": SAME, "ml/min": SAME},
            (1, 200), (Unitless(1, 200),), low=60, critical_low=30,
            basis="KDIGO 2012: under 60 is reduced, under 30 severely reduced", low_code="KIDNEY_RISK_EGFR",
            trend=Trend("down", relative=0.25, basis="KDIGO 2012 CKD guideline: a fall of 25% or more from baseline"),
        ),
        TestRule("Urea", "UREA", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(6.006)}, (1, 500), (Unitless(10, 400),), high=45),
        TestRule(
            "Blood Urea Nitrogen", "BUN", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(2.8)}, (1, 250), (Unitless(2, 200),),
            low=7, high=20,
        ),
        TestRule(
            "Potassium", "POTASSIUM", "mmol/L", {"mmol/l": SAME, "meq/l": SAME}, (1.0, 12), (Unitless(1.5, 9),),
            low=3.5, high=5.1, critical_low=2.5, critical_high=6.5,
            basis=f"3.5-5.1 mmol/L; 6.5 and over or 2.5 and under as critical is an {DEMO}",
        ),
        TestRule(
            "Sodium", "SODIUM", "mmol/L", {"mmol/l": SAME, "meq/l": SAME}, (90, 200), (Unitless(100, 180),),
            low=135, high=145, critical_low=120, critical_high=160,
            basis=f"135-145 mmol/L; 160 and over or 120 and under as critical is an {DEMO}",
        ),
        TestRule(
            "Total Bilirubin", "BILIRUBIN", "mg/dL", {"mg/dl": SAME, "umol/l": _factor(1 / 17.1)}, (0.05, 50),
            (Unitless(0.1, 30),), high=1.2,
        ),
        TestRule("ALT", "ALT", "U/L", {"u/l": SAME, "iu/l": SAME}, (1, 10000), (Unitless(1, 5000),), high=56),
        TestRule("AST", "AST", "U/L", {"u/l": SAME, "iu/l": SAME}, (1, 10000), (Unitless(1, 5000),), high=40),
        TestRule(
            "Total Cholesterol", "CHOLESTEROL", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(38.67)}, (40, 1000),
            (Unitless(60, 700),), high=200,
        ),
        TestRule(
            "LDL Cholesterol", "LDL", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(38.67)}, (10, 800), (Unitless(20, 600),),
            high=130,
        ),
        TestRule(
            "HDL Cholesterol", "HDL", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(38.67)}, (5, 200), (Unitless(10, 150),),
            low=40,
        ),
        TestRule(
            "Triglycerides", "TRIGLYCERIDES", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(88.57)}, (10, 5000),
            (Unitless(20, 3000),), high=150,
        ),
        TestRule("TSH", "TSH", "mIU/L", {"miu/l": SAME, "uiu/ml": SAME}, (0.001, 200), (Unitless(0.01, 100),), low=0.4, high=4.0),
        TestRule("Oxygen Saturation", "SPO2", "%", {"%": SAME}, (50, 100), (Unitless(50, 100),), low=95),
    ]
}  # fmt: skip


# Blood pressure (a vital, two numbers).
BP_BASIS = "systolic 140 or diastolic 90 mmHg and over is raised; 180 or 120 and over is a hypertensive crisis level"


def grade_blood_pressure(systolic: int, diastolic: int) -> Grade | None:
    if systolic >= 180 or diastolic >= 120:
        return Grade("HIGH_RISK", "high", "at a crisis level (systolic 180 or diastolic 120 mmHg, or more)")
    if systolic >= 140 or diastolic >= 90:
        return Grade("CAUTION", "high", "raised (systolic 140 or diastolic 90 mmHg, or more)")
    return None


def plausible_blood_pressure(systolic: int, diastolic: int) -> bool:
    return 60 <= systolic <= 260 and 30 <= diastolic <= 160 and systolic > diastolic


def normalise_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    text = unit.strip().lower().replace("µ", "u").replace("μ", "u").replace(" ", "").replace("×", "x")
    text = text.replace("³", "^3").replace("⁹", "^9").replace("²", "2").replace("cu.mm", "cumm").replace("mm3", "cumm")
    text = re.sub(r"^x?10\*", "x10^", text)
    return text.rstrip(".")


def to_number(value: str | None) -> float | None:
    """A printed value as a number; "<0.5" / ">90" (bounds, not readings) and blanks give None."""
    if not value or value.strip()[:1] in "<>":
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def read_value(
    rule: TestRule, printed: str | None, unit: str | None, readable: bool = True, confidence: float | None = None
) -> Value | Problem:
    """A printed value in the rule's unit, or the reason it cannot be used."""
    if not readable or not printed:
        return Problem("the value could not be read")
    if confidence is not None and confidence < LOW_CONFIDENCE:
        return Problem(f"the value was read with low confidence ({confidence:.0%})")
    number = to_number(printed)
    if number is None:
        return Problem("the value is a bound or not a plain number")
    normal_unit = normalise_unit(unit)
    if normal_unit is None:
        bands = [band for band in rule.unitless if band.low <= number <= band.high]
        if len(bands) != 1:
            return Problem(f"no unit is printed and the value does not clearly fit {rule.unit}")
        band = bands[0]
        value = band.convert(number)
        note = f"no unit printed; read as {band.label}" if band.label else f"no unit printed; read as {rule.unit}"
    elif normal_unit in rule.units:
        value, note = rule.units[normal_unit](number), None
    else:
        return Problem(f"the unit '{unit}' is not one this rule can convert")
    if not rule.plausible[0] <= value <= rule.plausible[1]:
        return Problem("the value is outside what is possible for this test; possibly a reading error")
    return Value(value, note)


def grade(rule: TestRule, value: float) -> Grade | None:
    """The most severe band a value falls in, or None inside the range."""
    if rule.critical_low is not None and value < rule.critical_low:
        return Grade("HIGH_RISK", "low", f"under {rule.critical_low:g} {rule.unit}")
    if rule.critical_high is not None and value >= rule.critical_high:
        return Grade("HIGH_RISK", "high", f"{rule.critical_high:g} {rule.unit} or more")
    if rule.low is not None and value < rule.low:
        return Grade("CAUTION", "low", f"under {rule.low:g} {rule.unit}")
    if rule.high is not None and value > rule.high:
        return Grade("CAUTION", "high", f"over {rule.high:g} {rule.unit}")
    return None


_KNOWN_UNITS = {u for rule in RULES.values() for u in rule.units} | {"mg", "g", "gm", "fl", "pg", "mmhg", "x10^12/l"}
_UNIT_SHAPE = re.compile(r"[/%^]|^(?:mg|g|gm|mmol|umol|meq|m?iu|u|uiu|lakhs?|fl|pg|cells|k)\b")


def looks_like_unit(token: str | None) -> bool:
    """True for "mg/dL", "%", "lakh", "U/L"; False for a word that follows a value ("today", "and")."""
    unit = normalise_unit(token)
    return bool(unit) and (unit in _KNOWN_UNITS or bool(_UNIT_SHAPE.search(unit)))


@dataclass(frozen=True)
class Assessment:
    """One reading, judged once, for both the per-report rules and the summary flags."""

    name: str
    code: str  # the warning code used when graded
    printed: str
    value: float | tuple[int, int] | None  # in the rule's unit; None when it cannot be used
    unit: str
    unit_note: str | None
    grade: Grade | None
    problem: str | None  # set: never graded, "check against the original report"
    basis: str
    entity: dict


def assess(entity: dict) -> Assessment | None:
    """A rule-read test result or blood pressure, judged against the shared rules. None for any
    other entity, a test these rules do not cover, or a model suggestion (never judged)."""
    if entity.get("method") == "biobert" or entity.get("certainty") == "model suggestion":
        return None
    printed = " ".join(str(p) for p in (entity.get("value") or "[?]", entity.get("unit") or "") if p).strip()
    if entity.get("type") == "vital" and entity.get("name") == "Blood Pressure":
        base = {"name": "Blood Pressure", "code": "HYPERTENSION_INDICATOR", "printed": printed, "unit": "mmHg",
                "unit_note": None, "basis": BP_BASIS, "entity": entity}  # fmt: skip
        if not entity.get("readable", True):
            return Assessment(
                **base, value=None, grade=None, problem="the two numbers are not a possible blood pressure"
            )
        systolic, diastolic = (int(n) for n in str(entity["value"]).split("/"))
        return Assessment(
            **base, value=(systolic, diastolic), grade=grade_blood_pressure(systolic, diastolic), problem=None
        )
    rule = RULES.get(entity.get("name")) if entity.get("type") == "test_result" else None
    if rule is None:
        return None
    reading = read_value(
        rule, entity.get("value"), entity.get("unit"), entity.get("readable", True), entity.get("confidence")
    )
    if isinstance(reading, Problem):
        return Assessment(
            rule.name, rule.code, printed, None, rule.unit, None, None, reading.reason, rule.basis, entity
        )
    graded = grade(rule, reading.value)
    code = rule.code_for(graded.direction) if graded else rule.code
    return Assessment(
        rule.name, code, printed, reading.value, rule.unit, reading.unit_note, graded, None, rule.basis, entity
    )


def show(value: float | tuple[int, int]) -> str:
    return f"{value[0]}/{value[1]}" if isinstance(value, tuple) else f"{round(value, 2):g}"


def warning_for(assessment: Assessment) -> dict[str, str] | None:
    """The per-report rule warning for one reading (None when it is inside the range)."""
    evidence = str(assessment.entity.get("evidence") or assessment.entity.get("text") or "")[:220]
    if assessment.problem:
        return {
            "code": "VALUE_NEEDS_CHECK",
            "severity": "CAUTION",
            "test": assessment.name,
            "message": f"{assessment.name} {assessment.printed} could not be checked ({assessment.problem}); "
            f"{CHECK_ORIGINAL}. For physician review.",
            "evidence": evidence,
        }
    if not assessment.grade:
        return None
    note = f" ({assessment.unit_note})" if assessment.unit_note else ""
    return {
        "code": assessment.code,
        "severity": assessment.grade.severity,
        # For the patient's wording (plain_language.patient_message): the test, as read, and which side.
        "test": assessment.name,
        "value_text": assessment.printed,
        "direction": assessment.grade.direction,
        "message": f"{assessment.name} {show(assessment.value)} {assessment.unit}{note} is {assessment.grade.limit}. "
        f"Rule: {assessment.basis}. Ranges differ between labs; for physician review.",
        "evidence": evidence,
    }
