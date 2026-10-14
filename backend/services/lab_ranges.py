"""Reference-range rules for common lab values: part of the deterministic report rules.

A value outside the range raises a CAUTION "for physician review"; these rules never call
a value normal or safe (AGENTS.md 6.1, 6.2). The ranges are general adult ranges; each lab
prints its own, which take precedence, so every message says ranges differ between labs.

Values are converted to one unit before comparing. Reports here mix units (g/L and g/dL,
per µL and x10^9/L, mmol/L and mg/dL, lakh notation), and a value read in the wrong unit
would raise a false alert. The unit is the one written directly after the number.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

# A value after the test name. An optional printed range in brackets right after the name
# is skipped; the gap before the number may not contain digits or run on for long, and the
# number may not be glued to a letter ("Hb A1c 7.0" has no hemoglobin value).
_READING = (
    r"\b{alias}\b(?:\s*\([^)]*\))?(?P<gap>[^\d\n]{{0,25}}?)"
    r"(?<![A-Za-z])(?P<value>\d+(?:\.\d+)?)(?P<unit>\s*[a-zA-Zµμ%/^\d.]{{0,14}})"
)


_TIME_UNIT = re.compile(r"^(?:hrs?|hours?|h|mins?|minutes?)\b")
# Words between a test name and a number that show the number belongs to a different test:
# "LDL/HDL ratio 3.1", "Creatinine Clearance 95", "Hb electrophoresis: HbA 97 %".
_OTHER_TEST = re.compile(r"ratio|clearance|electrophoresis|excretion|index|\bhb[a-z]", re.IGNORECASE)

# Every way reports name a blood glucose reading. All of them are checked, not just the first.
GLUCOSE_ALIASES = [
    "fasting blood sugar",
    "random blood sugar",
    "post prandial",
    "postprandial",
    "blood sugar",
    "blood glucose",
    "glucose",
    "sugar",
    "fbs",
    "rbs",
    "ppbs",
    "fpg",
]


@dataclass(frozen=True)
class Reading:
    value: float  # already converted to the rule's unit
    evidence: str


def _clean(text: str) -> str:
    """One line, and digit-group commas removed ("2,50,000" -> "250000", "13,200" -> "13200")."""
    return re.sub(r"(?<=\d),(?=\d)", "", " ".join((text or "").split()))


def _readings(text: str, aliases: list[str], convert: Callable[[float, str], float]):
    """Every value written after one of `aliases`, as (position of the number, Reading), alias by alias."""
    compact = _clean(text)
    for alias in aliases:
        pattern = _READING.format(alias=re.escape(alias))
        for match in re.finditer(pattern, compact, flags=re.IGNORECASE):
            if _OTHER_TEST.search(match.group("gap")):
                continue  # a ratio, a clearance or an electrophoresis fraction is not this test's value
            unit = match.group("unit").strip().lower()
            if _TIME_UNIT.match(unit):
                continue  # "Blood sugar 2 hours after meal": 2 is a time, not a reading
            raw = float(match.group("value"))
            evidence = compact[match.start() : min(len(compact), match.end() + 20)].strip()
            yield match.start("value"), Reading(value=round(convert(raw, unit), 2), evidence=evidence)


def read_value(
    text: str, aliases: list[str], convert: Callable[[float, str], float] = lambda v, _: v
) -> Reading | None:
    """The first value written after one of `aliases`, converted with `convert(value, unit)`."""
    return next((reading for _, reading in _readings(text, aliases, convert)), None)


def read_values(
    text: str, aliases: list[str], convert: Callable[[float, str], float] = lambda v, _: v
) -> list[Reading]:
    """Every value of a test in the report (e.g. fasting and random sugar), in reading order.

    A number reached through two aliases ("Fasting Blood Sugar" via "blood sugar" and "sugar")
    counts once.
    """
    by_position: dict[int, Reading] = {}
    for position, reading in _readings(text, aliases, convert):
        by_position.setdefault(position, reading)
    return [by_position[position] for position in sorted(by_position)]


# Unit conversions to the unit each rule uses.
def hemoglobin_g_dl(value: float, unit: str) -> float:
    if ("g/l" in unit and "g/dl" not in unit) or value > 30:
        return value / 10  # g/L
    return value


def per_nanolitre(value: float, unit: str) -> float:
    """x10^9/L (= thousands per µL). Counts written per µL (e.g. 6500, 250000) are divided by 1000."""
    if "lakh" in unit:
        return value * 100
    return value / 1000 if value >= 1000 else value


def glucose_mg_dl(value: float, unit: str) -> float:
    return value * 18.0 if "mmol" in unit else value


def creatinine_mg_dl(value: float, unit: str) -> float:
    if "mol" in unit or value > 20:  # µmol/L
        return value / 88.4
    return value


def urea_mg_dl(value: float, unit: str) -> float:
    return value * 6.006 if "mmol" in unit else value


def bilirubin_mg_dl(value: float, unit: str) -> float:
    return value / 17.1 if "mol" in unit else value


def cholesterol_mg_dl(value: float, unit: str) -> float:
    return value * 38.67 if "mmol" in unit else value


def triglycerides_mg_dl(value: float, unit: str) -> float:
    return value * 88.57 if "mmol" in unit else value


@dataclass(frozen=True)
class LabRange:
    code: str
    name: str
    aliases: list[str]
    unit: str
    low: float | None = None
    high: float | None = None
    convert: Callable[[float, str], float] = lambda value, _unit: value
    # Check every reading of this test in the report (the most severe counts), not only the first.
    all_readings: bool = False


LAB_RANGES = [
    LabRange("HEMOGLOBIN", "Hemoglobin", ["hemoglobin", "haemoglobin", "hb"], "g/dL", 12.0, 17.5, hemoglobin_g_dl, all_readings=True),
    LabRange("WBC", "White blood cells", ["white blood cells", "white blood cell count", "wbc", "tlc"], "x10^9/L", 4.0, 11.0, per_nanolitre),
    LabRange("PLATELETS", "Platelets", ["platelet count", "platelets", "plt"], "x10^9/L", 150.0, 450.0, per_nanolitre),
    LabRange("GLUCOSE", "Glucose", GLUCOSE_ALIASES, "mg/dL", low=70.0, convert=glucose_mg_dl, all_readings=True),
    LabRange("UREA", "Urea", ["blood urea", "urea"], "mg/dL", high=45.0, convert=urea_mg_dl),
    LabRange("BILIRUBIN", "Bilirubin", ["total bilirubin", "bilirubin"], "mg/dL", high=1.2, convert=bilirubin_mg_dl),
    LabRange("ALT", "ALT", ["alt", "sgpt"], "U/L", high=56.0),
    LabRange("AST", "AST", ["ast", "sgot"], "U/L", high=40.0),
    LabRange("LDL", "LDL cholesterol", ["ldl"], "mg/dL", high=130.0, convert=cholesterol_mg_dl),
    LabRange("HDL", "HDL cholesterol", ["hdl"], "mg/dL", low=40.0, convert=cholesterol_mg_dl),
    LabRange("TRIGLYCERIDES", "Triglycerides", ["triglycerides", "triglyceride", "tg"], "mg/dL", high=150.0, convert=triglycerides_mg_dl),
    LabRange("SPO2", "Oxygen saturation", ["oxygen saturation", "spo2"], "%", low=95.0),
]  # fmt: skip


def _range_text(lab: LabRange) -> str:
    if lab.low is not None and lab.high is not None:
        return f"{lab.low:g}–{lab.high:g} {lab.unit}"
    return f"{'at least' if lab.low is not None else 'up to'} {(lab.low if lab.low is not None else lab.high):g} {lab.unit}"


def check_lab_ranges(text: str) -> list[dict[str, str]]:
    """CAUTION warnings for values outside the ranges above, in the rule-warning shape."""
    warnings: list[dict[str, str]] = []
    for lab in LAB_RANGES:
        if lab.all_readings:
            readings = read_values(text, lab.aliases, lab.convert)
        else:
            first = read_value(text, lab.aliases, lab.convert)
            readings = [first] if first else []
        for reading in readings:
            warning = _range_warning(lab, reading)
            if warning:
                warnings.append(warning)
    return warnings


def _range_warning(lab: LabRange, reading: Reading) -> dict[str, str] | None:
    if lab.low is not None and reading.value < lab.low:
        direction, code = "below", f"{lab.code}_LOW"
    elif lab.high is not None and reading.value > lab.high:
        direction, code = "above", f"{lab.code}_HIGH"
    else:
        return None
    return {
        "code": code,
        "severity": "CAUTION",
        "message": (
            f"{lab.name} {reading.value:g} {lab.unit} is {direction} the range these rules use "
            f"({_range_text(lab)}). Ranges differ between labs; for physician review."
        ),
        "evidence": reading.evidence[:220],
    }
