"""The deterministic rules behind the clinical-summary flags (FE-3): ranges, units and trends.

General adult ranges. Where the report rules (services/lab_ranges.py, rule_validation_service.py)
check the same test, the limits match. These rules also cover tests the report rules do not
(potassium, sodium, total cholesterol, TSH, BUN), and fasting sugar over 125 mg/dL, where the
report rules flag glucose only from 200. Each lab prints its own range; these are for physician
review only and never call a value normal or safe.

Units: a value is converted to the rule's unit only when its printed unit is one listed here. A
value with no unit is taken as the rule's unit only inside a narrow band where that is the only
sensible reading; anything else is shown as "check against the original report", never flagged.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

DEMO = "app rule (demo), not a clinical standard"
SEVERITY_RANK = {"INFO": 0, "CAUTION": 1, "HIGH_RISK": 2}


def _factor(k: float) -> Callable[[float], float]:
    return lambda value: value * k


SAME = _factor(1)
COUNT_UNITS = {
    "x10^9/l": SAME,
    "10^9/l": SAME,
    "x10^3/ul": SAME,
    "10^3/ul": SAME,
    "k/ul": SAME,
    "/ul": _factor(0.001),
    "cells/ul": _factor(0.001),
    "/cumm": _factor(0.001),
    "cells/cumm": _factor(0.001),
    "lakh/cumm": _factor(100),
    "lakhs/cumm": _factor(100),
}


@dataclass(frozen=True)
class Trend:
    direction: str  # "up" or "down": the worsening direction
    absolute: float | None = None  # change in the rule's unit
    relative: float | None = None  # fraction of the baseline (0.25 = 25%)
    basis: str = DEMO


@dataclass(frozen=True)
class TestRule:
    name: str  # the knowledge-base test name
    unit: str
    units: dict[str, Callable[[float], float]]
    plausible: tuple[float, float]  # outside this (in the rule's unit) the reading is not trusted
    unitless: tuple[float, float] | None  # a value with no unit is accepted only inside this band
    low: float | None = None
    high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    basis: str = "general adult range used by the app's report rules"
    trend: Trend | None = None


def _glucose(name: str, high: float, basis: str) -> TestRule:
    return TestRule(
        name, "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(18.0)}, (10, 2000), (40, 1000),
        low=70, high=high, critical_low=54, critical_high=300, basis=basis,
    )  # fmt: skip


RULES: dict[str, TestRule] = {
    rule.name: rule
    for rule in [
        TestRule(
            "Hemoglobin", "g/dL", {"g/dl": SAME, "g/l": _factor(0.1), "gm/dl": SAME, "gm%": SAME}, (2, 25), (3, 22),
            low=12.0, high=17.5, critical_low=7.0,
            trend=Trend("down", absolute=2.0, basis="a fall of 2 g/dL (the ISTH major-bleeding threshold); used here for review only"),
        ),
        TestRule("WBC Count", "x10^9/L", COUNT_UNITS, (0.1, 300), (0.5, 100), low=4.0, high=11.0),
        TestRule(
            "Platelet Count", "x10^9/L", COUNT_UNITS, (1, 3000), (5, 1500), low=150, high=450, critical_low=50,
            trend=Trend("down", relative=0.5),
        ),
        _glucose("Fasting Blood Sugar", 125, "ADA: fasting 126 mg/dL or more is in the diabetes range; under 70 low, under 54 very low"),
        _glucose("Random Blood Sugar", 199, "ADA: random 200 mg/dL or more is in the diabetes range; under 70 low, under 54 very low"),
        _glucose("Post Prandial Blood Sugar", 199, "ADA: 2-hour 200 mg/dL or more is in the diabetes range; under 70 low, under 54 very low"),
        TestRule(
            "HbA1c", "%", {"%": SAME, "mmol/mol": lambda v: v * 0.09148 + 2.152}, (3, 20), (3, 20),
            high=6.4, basis="ADA: 6.5% or more is in the diabetes range",
            trend=Trend("up", absolute=1.0),
        ),
        TestRule(
            "Creatinine", "mg/dL", {"mg/dl": SAME, "umol/l": _factor(1 / 88.4)}, (0.1, 30), (0.2, 15), high=1.3,
            trend=Trend("up", absolute=0.3, relative=0.5,
                        basis="KDIGO 2012 AKI criteria (a rise of 0.3 mg/dL, or 1.5 times baseline), applied here without their time window"),
        ),
        TestRule(
            "eGFR", "mL/min/1.73m2", {"ml/min/1.73m2": SAME, "ml/min/1.73m^2": SAME, "ml/min/1.73": SAME, "ml/min": SAME},
            (1, 200), (1, 200), low=60, critical_low=30, basis="KDIGO 2012: under 60 is reduced, under 30 severely reduced",
            trend=Trend("down", relative=0.25, basis="KDIGO 2012 CKD guideline: a fall of 25% or more from baseline"),
        ),
        TestRule("Urea", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(6.006)}, (1, 500), (5, 400), high=45),
        TestRule("Blood Urea Nitrogen", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(2.8)}, (1, 250), (2, 200), low=7, high=20),
        TestRule(
            "Potassium", "mmol/L", {"mmol/l": SAME, "meq/l": SAME}, (1.0, 12), (1.5, 9), low=3.5, high=5.1,
            critical_low=2.5, critical_high=6.5, basis=f"3.5–5.1 mmol/L; 6.5 and over or 2.5 and under as critical is an {DEMO}",
        ),
        TestRule(
            "Sodium", "mmol/L", {"mmol/l": SAME, "meq/l": SAME}, (90, 200), (100, 180), low=135, high=145,
            critical_low=120, critical_high=160, basis=f"135–145 mmol/L; 160 and over or 120 and under as critical is an {DEMO}",
        ),
        TestRule("Total Bilirubin", "mg/dL", {"mg/dl": SAME, "umol/l": _factor(1 / 17.1)}, (0.05, 50), (0.1, 30), high=1.2),
        TestRule("ALT", "U/L", {"u/l": SAME, "iu/l": SAME}, (1, 10000), (1, 5000), high=56),
        TestRule("AST", "U/L", {"u/l": SAME, "iu/l": SAME}, (1, 10000), (1, 5000), high=40),
        TestRule("Total Cholesterol", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(38.67)}, (40, 1000), (60, 700), high=200),
        TestRule("LDL Cholesterol", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(38.67)}, (10, 800), (20, 600), high=130),
        TestRule("HDL Cholesterol", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(38.67)}, (5, 200), (10, 150), low=40),
        TestRule("Triglycerides", "mg/dL", {"mg/dl": SAME, "mmol/l": _factor(88.57)}, (10, 5000), (20, 3000), high=150),
        TestRule("TSH", "mIU/L", {"miu/l": SAME, "uiu/ml": SAME}, (0.001, 200), (0.01, 100), low=0.4, high=4.0),
    ]
}  # fmt: skip


# Blood pressure (a vital, two numbers): the thresholds the report rules use.
BP_CAUTION = (140, 90)
BP_HIGH_RISK = (180, 120)
BP_BASIS = "140/90 mmHg and over is raised; 180/120 and over is a hypertensive crisis level"


def normalise_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    text = unit.strip().lower().replace("µ", "u").replace("μ", "u").replace(" ", "")
    text = text.replace("³", "^3").replace("²", "2").replace("cu.mm", "cumm").replace("mm3", "cumm")
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
