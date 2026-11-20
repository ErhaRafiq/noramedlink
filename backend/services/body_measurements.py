"""Body weight and height: input rules and the calculations that use them (no database, no network).

Every function here is deterministic. Nothing assumes a weight: when an input is missing the result says
which one. These results are advisory and for physician review (AGENTS.md section 6); the modules that
show them add that wording. Thresholds named "app rule (demo)" are this project's own settings, not a
clinical standard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from config import settings

APP_RULE_LABEL = "app rule (demo)"

LB_TO_KG = 0.45359237  # international avoirdupois pound, exactly
# Plausible ranges. Anything outside is rejected as a typing mistake (the database repeats these checks).
WEIGHT_MIN_KG, WEIGHT_MAX_KG = 2.0, 350.0
HEIGHT_MIN_CM, HEIGHT_MAX_CM = 40.0, 250.0
ADULT_AGE = 18


class MeasurementError(ValueError):
    """An impossible or unusable value; the message is safe to show the person."""


# --- input -----------------------------------------------------------------------------------------------


def to_kg(value: float, unit: str) -> float:
    """A weight in kg, rounded to 0.01 kg. `unit` is "kg" or "lb"."""
    if unit == "kg":
        return round(value, 2)
    if unit == "lb":
        return round(value * LB_TO_KG, 2)
    raise MeasurementError("The weight unit must be kg or lb.")


def check_weight_kg(kg: float) -> float:
    if not WEIGHT_MIN_KG <= kg <= WEIGHT_MAX_KG:
        raise MeasurementError(
            f"That weight is not possible. Enter between {WEIGHT_MIN_KG:g} and {WEIGHT_MAX_KG:g} kg "
            "(or the same in pounds)."
        )
    return kg


def check_height_cm(cm: float) -> float:
    if not HEIGHT_MIN_CM <= cm <= HEIGHT_MAX_CM:
        raise MeasurementError(
            f"That height is not possible. Enter between {HEIGHT_MIN_CM:g} and {HEIGHT_MAX_CM:g} cm."
        )
    return round(cm, 1)


def validate_input(
    weight: float | None,
    weight_unit: str,
    height_cm: float | None,
    measured_on: date | None,
    today: date | None = None,
) -> tuple[float | None, float | None, date]:
    """(weight_kg, height_cm, measured_on) ready to store. At least one of weight and height is needed;
    nothing is defaulted, and the date cannot be in the future."""
    today = today or date.today()
    if weight is None and height_cm is None:
        raise MeasurementError("Enter a weight, a height, or both.")
    when = measured_on or today
    if when > today:
        raise MeasurementError("The date cannot be in the future.")
    kg = check_weight_kg(to_kg(weight, weight_unit)) if weight is not None else None
    cm = check_height_cm(height_cm) if height_cm is not None else None
    return kg, cm, when


# --- the latest value --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Reading:
    value: float
    measured_on: date
    added_by_role: str = "patient"


def readings(rows: list[Any], attribute: str) -> list[Reading]:
    """Active rows that hold `attribute` ("weight_kg" or "height_cm"), oldest first. Rows on the same day
    keep the order they were entered in (ascending id), so the last one entered is the latest."""
    kept = [r for r in rows if r.status == "active" and getattr(r, attribute) is not None]
    kept.sort(key=lambda r: (r.measured_on, r.id))
    return [Reading(float(getattr(r, attribute)), r.measured_on, r.added_by_role) for r in kept]


def latest(history: list[Reading]) -> Reading | None:
    return history[-1] if history else None


# --- BMI ---------------------------------------------------------------------------------------------------


def bmi(weight_kg: float | None, height_cm: float | None) -> float | None:
    """Body mass index in kg/m2, rounded to 0.1; None unless both are known.
    Source: WHO Technical Report Series 894, Obesity: preventing and managing the global epidemic (2000)."""
    if not weight_kg or not height_cm:
        return None
    return round(weight_kg / (height_cm / 100) ** 2, 1)


ASIAN_BMI_NOTE = (
    "For Asian populations, WHO identifies increased risk from 23.0 and high risk from 27.5 kg/m2 "
    "(WHO Expert Consultation. Appropriate body-mass index for Asian populations and its implications for "
    "policy and intervention strategies. Lancet. 2004;363(9403):157-163. doi:10.1016/S0140-6736(03)15268-3)."
)


def bmi_category(value: float | None, age: int | None, pregnant: bool = False) -> str | None:
    """The WHO international adult band (cut-offs 18.5, 25 and 30; TRS 894), shown to the doctor only.
    None when it does not apply: no BMI, under 18 or an unknown age (children need BMI-for-age, which this
    app does not have) and pregnancy (a pregnant woman's weight is not read against adult bands)."""
    if value is None or age is None or age < ADULT_AGE or pregnant:
        return None
    if value < 18.5:
        return "underweight"
    if value < 25:
        return "normal range"
    if value < 30:
        return "overweight"
    return "obesity"


def bmi_category_note(age: int | None, pregnant: bool = False) -> str | None:
    """Why there is no category, in words for the doctor; None when a category applies."""
    if pregnant:
        return "category not applicable (marked pregnant)"
    if age is None:
        return "category not applicable (age not known)"
    if age < ADULT_AGE:
        return "category not applicable (under 18: needs BMI-for-age)"
    return None


@dataclass(frozen=True)
class BmiResult:
    value: float
    category: str | None
    category_note: str | None  # set when the category does not apply
    asian_note: str | None  # set when a category applies: the doctor reads both scales


def bmi_result(
    weight_kg: float | None, height_cm: float | None, age: int | None, pregnant: bool = False
) -> BmiResult | None:
    """The BMI with its category for the doctor's view; None when weight or height is missing."""
    value = bmi(weight_kg, height_cm)
    if value is None:
        return None
    category = bmi_category(value, age, pregnant)
    return BmiResult(
        value, category, bmi_category_note(age, pregnant), ASIAN_BMI_NOTE if category is not None else None
    )


# --- weight change -----------------------------------------------------------------------------------------

# (window in days, percent): the chronic-illness criteria of White JV, Guenter P, Jensen G, Malone A,
# Schofield M. Consensus statement: Academy of Nutrition and Dietetics and ASPEN: characteristics recommended
# for the identification and documentation of adult malnutrition (undernutrition). JPEN J Parenter Enteral
# Nutr. 2012;36(3):275-283. doi:10.1177/0148607112440285 -- 5 % in 1 month, 7.5 % in 3 months, 10 % in
# 6 months, 20 % in 1 year. These are one criterion among several in that paper: a flag here is only
# "significant weight loss, for physician review" and never says malnutrition. The same figures are applied to
# a gain as an app rule (demo).
CHANGE_WINDOWS: tuple[tuple[int, float], ...] = ((30, 5.0), (90, 7.5), (180, 10.0), (365, 20.0))
LOSS_BASIS = "White 2012, AND/ASPEN consensus (chronic-illness criteria)"
LOSS_WORDING = "significant weight loss, for physician review"
GAIN_WORDING = "significant weight gain, for physician review"


@dataclass(frozen=True)
class WeightChange:
    percent: float  # negative for a loss
    from_kg: float
    from_date: date
    to_kg: float
    to_date: date
    window_days: int
    threshold_percent: float
    basis: str

    @property
    def wording(self) -> str:
        return LOSS_WORDING if self.percent < 0 else GAIN_WORDING


def percent_change(old: float, new: float) -> float:
    """(new - old) / old x 100, rounded to 0.1. `old` must be above zero."""
    if old <= 0:
        raise MeasurementError("A starting weight must be above zero.")
    return round((new - old) / old * 100, 1)


def weight_change_flags(history: list[Reading]) -> list[WeightChange]:
    """Windows in which the weight moved by at least the threshold, shortest window first. For each window
    the baseline is the oldest reading no more than `window` days before the latest, so the change is the
    largest one inside that window. Empty with fewer than two readings."""
    if len(history) < 2:
        return []
    end = history[-1]
    flagged: list[WeightChange] = []
    for days, threshold in CHANGE_WINDOWS:
        inside = [r for r in history[:-1] if 0 < (end.measured_on - r.measured_on).days <= days]
        if not inside:
            continue
        start = min(inside, key=lambda r: r.measured_on)
        pct = percent_change(start.value, end.value)
        if abs(pct) >= threshold:
            basis = LOSS_BASIS if pct < 0 else f"{APP_RULE_LABEL}, same figures as the loss criteria"
            flagged.append(
                WeightChange(pct, start.value, start.measured_on, end.value, end.measured_on, days, threshold, basis)
            )
    return flagged


def change_since_previous(history: list[Reading]) -> WeightChange | None:
    """The change between the last two readings, whether or not it passes a threshold (for display)."""
    if len(history) < 2:
        return None
    before, end = history[-2], history[-1]
    return WeightChange(
        percent_change(before.value, end.value),
        before.value,
        before.measured_on,
        end.value,
        end.measured_on,
        (end.measured_on - before.measured_on).days,
        0.0,
        "difference between the last two readings",
    )


# --- is the weight recent enough ---------------------------------------------------------------------------


def weight_max_age_days(age: int | None) -> int:
    """How old a weight may be before a check that needs it is skipped: an app rule (demo), set in config.
    An unknown age uses the stricter (child) window."""
    if age is not None and age >= ADULT_AGE:
        return settings.weight_max_age_days_adult
    return settings.weight_max_age_days_child


def weight_is_current(measured_on: date, age: int | None, today: date | None = None) -> bool:
    return ((today or date.today()) - measured_on).days <= weight_max_age_days(age)


# --- creatinine clearance (Cockcroft-Gault) ----------------------------------------------------------------


@dataclass(frozen=True)
class CreatinineClearance:
    value: float | None  # mL/min; None when something is missing
    missing: list[str]  # plain words for each missing or unusable input
    inputs: dict[str, Any]  # what was used, with dates, so the physician can check it
    note: str


CG_NOTE = (
    "Cockcroft-Gault estimate using actual body weight, for physician review. Information only: "
    "renal dose alerts are based on eGFR, not on this number."
)


def sex_for_formula(gender: str | None) -> str | None:
    """ "male" or "female" from the profile's gender; None for "other" or blank (the formula has no term for it)."""
    value = (gender or "").strip().lower()
    return value if value in {"male", "female"} else None


def cockcroft_gault(age: int, sex: str, weight_kg: float, creatinine_mg_dl: float) -> float:
    """CrCl (mL/min) = (140 - age) x weight / (72 x serum creatinine), x 0.85 for a woman.
    Source: Cockcroft DW, Gault MH. Prediction of creatinine clearance from serum creatinine.
    Nephron 1976;16:31-41. Never below zero."""
    value = (140 - age) * weight_kg / (72 * creatinine_mg_dl)
    if sex == "female":
        value *= 0.85
    return round(max(value, 0.0), 1)


def creatinine_clearance(
    *,
    age: int | None,
    gender: str | None,
    weight: Reading | None,
    creatinine_mg_dl: float | None,
    creatinine_date: date | None,
    today: date | None = None,
) -> CreatinineClearance:
    """The estimate when weight, age, sex and a recent creatinine are all known; otherwise `missing` says which."""
    today = today or date.today()
    missing: list[str] = []
    sex = sex_for_formula(gender)
    if age is None:
        missing.append("age")
    elif age < ADULT_AGE:
        missing.append("age 18 or over (the formula is for adults)")
    if sex is None:
        missing.append("sex recorded as male or female")
    if weight is None:
        missing.append("body weight")
    if creatinine_mg_dl is None or creatinine_date is None or creatinine_mg_dl <= 0:
        missing.append("serum creatinine")
    elif (today - creatinine_date).days > settings.creatinine_max_age_days:
        missing.append(f"serum creatinine from the last {settings.creatinine_max_age_days} days ({APP_RULE_LABEL})")
    inputs = {
        "age": age,
        "sex": sex,
        "weight_kg": weight.value if weight else None,
        "weight_date": weight.measured_on.isoformat() if weight else None,
        "creatinine_mg_dl": creatinine_mg_dl,
        "creatinine_date": creatinine_date.isoformat() if creatinine_date else None,
    }
    if missing or age is None or sex is None or weight is None or creatinine_mg_dl is None:
        return CreatinineClearance(None, missing, inputs, CG_NOTE)
    return CreatinineClearance(cockcroft_gault(age, sex, weight.value, creatinine_mg_dl), [], inputs, CG_NOTE)
