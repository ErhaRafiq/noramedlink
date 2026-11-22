"""Body weight and height: unit conversion, range checks, BMI, weight change, how old a weight may be and
Cockcroft-Gault. No database, no network."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from config import settings
from schemas import BodyMeasurementIn
from services import body_measurements as bm
from services.body_measurements import Reading

TODAY = date(2026, 11, 20)


def row(id_, on, weight=None, height=None, status="active", by="patient"):
    return SimpleNamespace(id=id_, measured_on=on, weight_kg=weight, height_cm=height, status=status, added_by_role=by)


def days_ago(n):
    return TODAY - timedelta(days=n)


# --- unit conversion and range validation ------------------------------------------------------------------


def test_pounds_are_converted_to_kg():
    assert bm.to_kg(154, "lb") == 69.85
    assert bm.to_kg(1, "lb") == 0.45
    assert bm.to_kg(70.456, "kg") == 70.46


def test_an_unknown_unit_is_refused():
    with pytest.raises(bm.MeasurementError):
        bm.to_kg(70, "stone")


@pytest.mark.parametrize("kg", [0, 1.99, 350.01, 1000, -5])
def test_impossible_weights_are_rejected(kg):
    with pytest.raises(bm.MeasurementError):
        bm.validate_input(kg, "kg", None, None, TODAY)


@pytest.mark.parametrize("kg", [2, 3.4, 70, 350])
def test_plausible_weights_are_accepted(kg):
    assert bm.validate_input(kg, "kg", None, None, TODAY)[0] == kg


def test_the_range_is_checked_after_conversion():
    with pytest.raises(bm.MeasurementError):
        bm.validate_input(800, "lb", None, None, TODAY)  # 362.87 kg
    assert bm.validate_input(150, "lb", None, None, TODAY)[0] == 68.04


@pytest.mark.parametrize("cm", [39.9, 250.1, 0, -1])
def test_impossible_heights_are_rejected(cm):
    with pytest.raises(bm.MeasurementError):
        bm.validate_input(None, "kg", cm, None, TODAY)


def test_height_is_kept_to_one_decimal():
    assert bm.validate_input(None, "kg", 172.46, None, TODAY)[1] == 172.5


def test_weight_or_height_is_needed_and_nothing_is_defaulted():
    with pytest.raises(bm.MeasurementError):
        bm.validate_input(None, "kg", None, None, TODAY)
    kg, cm, when = bm.validate_input(None, "kg", 170, None, TODAY)
    assert kg is None and cm == 170 and when == TODAY  # no weight is invented


def test_a_future_date_is_rejected_and_today_is_the_default():
    with pytest.raises(bm.MeasurementError):
        bm.validate_input(70, "kg", None, TODAY + timedelta(days=1), TODAY)
    assert bm.validate_input(70, "kg", None, None, TODAY)[2] == TODAY
    assert bm.validate_input(70, "kg", None, days_ago(3), TODAY)[2] == days_ago(3)


def test_the_request_model_refuses_zero_negative_and_nonsense():
    for bad in ({"weight": 0}, {"weight": -1}, {"weight": float("nan")}, {"weight_unit": "st", "weight": 5}):
        with pytest.raises(ValidationError):
            BodyMeasurementIn(**bad)
    with pytest.raises(ValidationError):
        BodyMeasurementIn(weight=70, measured_on=date.today() + timedelta(days=1))
    assert BodyMeasurementIn(weight=150, weight_unit="lb").weight_unit == "lb"


# --- the latest value --------------------------------------------------------------------------------------


def test_latest_ignores_removed_rows_and_rows_without_the_value():
    rows = [
        row(1, days_ago(30), weight=70),
        row(2, days_ago(10), height=170),
        row(3, days_ago(5), weight=99, status="removed"),
    ]
    assert bm.latest(bm.readings(rows, "weight_kg")).value == 70
    assert bm.latest(bm.readings(rows, "height_cm")).value == 170
    assert bm.latest(bm.readings([], "weight_kg")) is None


def test_two_readings_on_one_day_the_last_entered_wins():
    rows = [row(5, days_ago(1), weight=71), row(4, days_ago(1), weight=70)]
    assert bm.latest(bm.readings(rows, "weight_kg")).value == 71


def test_a_back_dated_entry_does_not_become_the_latest():
    rows = [row(1, days_ago(2), weight=70), row(2, days_ago(40), weight=80)]
    assert bm.latest(bm.readings(rows, "weight_kg")).value == 70


# --- BMI ---------------------------------------------------------------------------------------------------


def test_bmi_is_weight_over_height_squared():
    assert bm.bmi(70, 175) == 22.9
    assert bm.bmi(100, 180) == 30.9
    assert bm.bmi(50, 160) == 19.5


def test_bmi_needs_both_values():
    assert bm.bmi(None, 170) is None
    assert bm.bmi(70, None) is None
    assert bm.bmi(0, 170) is None


@pytest.mark.parametrize(
    ("value", "word"),
    [
        (18.4, "underweight"),
        (18.5, "normal range"),
        (24.9, "normal range"),
        (25.0, "overweight"),
        (29.9, "overweight"),
        (30.0, "obesity"),
    ],
)
def test_the_who_adult_bands(value, word):
    assert bm.bmi_category(value, 40) == word


def test_no_band_when_marked_pregnant():
    assert bm.bmi_category(22.0, 30, pregnant=True) is None
    result = bm.bmi_result(70, 170, 30, pregnant=True)
    assert result.value == 24.2 and result.category is None and "pregnant" in result.category_note
    assert result.asian_note is None


def test_the_doctor_view_has_the_asian_population_note_with_its_citation():
    result = bm.bmi_result(70, 175, 40)
    assert (result.value, result.category, result.category_note) == (22.9, "normal range", None)
    assert "23.0" in result.asian_note and "27.5" in result.asian_note
    assert (
        "Lancet. 2004;363(9403):157-163" in result.asian_note and "10.1016/S0140-6736(03)15268-3" in result.asian_note
    )


def test_a_child_gets_the_number_and_category_not_applicable():
    result = bm.bmi_result(30, 130, 9)
    assert result.value == 17.8 and result.category is None
    assert result.category_note == "category not applicable (under 18: needs BMI-for-age)"
    assert bm.bmi_result(None, 130, 9) is None
    assert bm.bmi_result(30, 130, None).category_note == "category not applicable (age not known)"


def test_no_band_for_a_child_an_unknown_age_or_no_bmi():
    assert bm.bmi_category(22.0, 12) is None
    assert bm.bmi_category(22.0, 17) is None
    assert bm.bmi_category(22.0, None) is None
    assert bm.bmi_category(None, 40) is None


# --- weight change -----------------------------------------------------------------------------------------


def history(*pairs):
    return [Reading(kg, days_ago(d)) for d, kg in pairs]  # oldest first: larger d first


def test_percent_change():
    assert bm.percent_change(80, 76) == -5.0
    assert bm.percent_change(60, 63) == 5.0
    with pytest.raises(bm.MeasurementError):
        bm.percent_change(0, 5)


def test_five_percent_loss_in_a_month_is_flagged_and_just_under_is_not():
    flagged = bm.weight_change_flags(history((20, 80.0), (0, 76.0)))
    assert len(flagged) == 1
    assert flagged[0].percent == -5.0 and flagged[0].window_days == 30 and "White 2012" in flagged[0].basis
    assert bm.weight_change_flags(history((20, 80.0), (0, 76.1))) == []


def test_a_slow_loss_is_judged_against_the_longer_windows():
    # 8 % over 80 days passes the 3-month figure (7.5 %) but not the 6-month one (10 %)
    flagged = bm.weight_change_flags(history((80, 100.0), (0, 92.0)))
    assert [f.window_days for f in flagged] == [90]
    # 6 % over 80 days passes no window
    assert bm.weight_change_flags(history((80, 100.0), (0, 94.0))) == []


def test_twenty_percent_in_a_year():
    flagged = bm.weight_change_flags(history((300, 100.0), (0, 80.0)))
    assert [f.window_days for f in flagged] == [365]
    assert bm.weight_change_flags(history((300, 100.0), (0, 80.1))) == []


def test_the_wording_never_says_malnutrition_and_names_the_direction():
    loss = bm.weight_change_flags(history((20, 80.0), (0, 76.0)))[0]
    gain = bm.weight_change_flags(history((10, 60.0), (0, 63.0)))[0]
    assert loss.wording == "significant weight loss, for physician review"
    assert gain.wording == "significant weight gain, for physician review"
    assert "malnutrition" not in loss.wording + gain.wording


def test_ten_percent_in_six_months():
    flagged = bm.weight_change_flags(history((170, 100.0), (0, 90.0)))
    assert [f.window_days for f in flagged] == [180]


def test_a_gain_is_flagged_as_an_app_rule():
    flagged = bm.weight_change_flags(history((10, 60.0), (0, 63.0)))
    assert flagged and flagged[0].percent == 5.0 and bm.APP_RULE_LABEL in flagged[0].basis


def test_readings_older_than_the_longest_window_are_not_compared():
    assert bm.weight_change_flags(history((400, 100.0), (0, 60.0))) == []


def test_fewer_than_two_readings_give_no_flag_and_no_change():
    assert bm.weight_change_flags([]) == []
    assert bm.weight_change_flags(history((0, 70.0))) == []
    assert bm.change_since_previous(history((0, 70.0))) is None


def test_the_change_since_the_previous_reading():
    change = bm.change_since_previous(history((10, 70.0), (0, 73.5)))
    assert change.percent == 5.0 and change.window_days == 10


def test_the_same_day_twice_is_not_a_change_window():
    both = [Reading(80.0, TODAY), Reading(70.0, TODAY)]
    assert bm.weight_change_flags(both) == []


# --- how old a weight may be (app rule, from config) ---------------------------------------------------------


def test_an_adult_weight_is_current_for_90_days_a_child_for_30():
    assert (settings.weight_max_age_days_adult, settings.weight_max_age_days_child) == (90, 30)
    assert bm.weight_is_current(days_ago(90), 40, TODAY)
    assert not bm.weight_is_current(days_ago(91), 40, TODAY)
    assert bm.weight_is_current(days_ago(30), 8, TODAY)
    assert not bm.weight_is_current(days_ago(31), 8, TODAY)
    assert bm.weight_max_age_days(17) == 30 and bm.weight_max_age_days(18) == 90


def test_an_unknown_age_uses_the_stricter_window():
    assert bm.weight_max_age_days(None) == 30


# --- Cockcroft-Gault -----------------------------------------------------------------------------------------


def cg(**changes):
    inputs = {
        "age": 60,
        "gender": "male",
        "weight": Reading(80.0, days_ago(5)),
        "creatinine_mg_dl": 1.0,
        "creatinine_date": days_ago(10),
        "today": TODAY,
    }
    inputs.update(changes)
    return bm.creatinine_clearance(**inputs)


def test_cockcroft_gault_formula():
    assert bm.cockcroft_gault(60, "male", 80, 1.0) == 88.9  # (140-60) x 80 / 72
    assert bm.cockcroft_gault(60, "female", 80, 1.0) == 75.6  # x 0.85
    assert bm.cockcroft_gault(150, "male", 80, 1.0) == 0.0  # never negative


def test_the_estimate_with_every_input_present():
    result = cg()
    assert result.value == 88.9 and result.missing == []
    assert result.inputs["weight_date"] == days_ago(5).isoformat() and result.inputs["creatinine_date"]
    assert "eGFR" in result.note


def test_gender_is_read_in_any_case_and_other_is_not_usable():
    assert cg(gender="Female").value == 75.6
    result = cg(gender="other")
    assert result.value is None and result.missing == ["sex recorded as male or female"]


@pytest.mark.parametrize(
    ("change", "word"),
    [
        ({"weight": None}, "body weight"),
        ({"age": None}, "age"),
        ({"gender": None}, "sex recorded as male or female"),
        ({"creatinine_mg_dl": None, "creatinine_date": None}, "serum creatinine"),
        ({"creatinine_mg_dl": 0}, "serum creatinine"),
    ],
)
def test_each_missing_input_is_named(change, word):
    result = cg(**change)
    assert result.value is None
    assert result.missing == [word]


def test_several_missing_inputs_are_all_listed():
    result = cg(weight=None, creatinine_mg_dl=None, creatinine_date=None)
    assert result.missing == ["body weight", "serum creatinine"] and result.value is None


def test_an_old_creatinine_is_missing_and_labelled_an_app_rule():
    assert cg(creatinine_date=days_ago(90)).value == 88.9
    result = cg(creatinine_date=days_ago(91))
    assert result.value is None
    assert "last 90 days" in result.missing[0] and bm.APP_RULE_LABEL in result.missing[0]


def test_a_child_gets_no_estimate():
    result = cg(age=12)
    assert result.value is None and "18 or over" in result.missing[0]
