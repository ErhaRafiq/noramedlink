"""ICSE: the body measurements section of the physician summary (weight, height, BMI, weight trend).
Synthetic data only. No database, no network."""

import json
from datetime import date
from types import SimpleNamespace

from services import body_record
from services.ai_guard import numbers_not_in_source
from services.icse import versions
from services.icse.summary import SUMMARY_VERSION, build_content, render_text
from services.icse.wording import facts

TODAY = date(2026, 11, 20)
NOT_RECORDED = {"status": "not_recorded", "set_on": None, "set_by_role": None, "expired": False, "max_months": 10}


def reading(value, day, by="patient"):
    return {"value": value, "date": day, "added_by_role": by}


def body(weights=(), heights=(), age=40, pregnancy=None):
    return {"weights": list(weights), "heights": list(heights), "age": age, "pregnancy": pregnancy or NOT_RECORDED}


def summary(**kwargs):
    return build_content([], [], [], TODAY, body(**kwargs))


FULL = {"weights": [reading(72.0, "2026-11-10")], "heights": [reading(172.0, "2026-09-01", "doctor")]}


# --- latest values, BMI, dates and sources ---------------------------------------------------------------------


def test_the_latest_weight_height_and_bmi_carry_their_dates_and_who_entered_them():
    section = summary(**FULL)["body"]
    assert section["weight"] == {
        "value": 72.0, "date": "2026-11-10", "entered_by": "the patient",
        "source": "Weight and height entered in the app: entered by the patient on 2026-11-10",
    }  # fmt: skip
    assert section["height"]["entered_by"] == "a doctor" and section["height"]["date"] == "2026-09-01"
    bmi = section["bmi"]
    assert bmi["value"] == 24.3 and bmi["weight_date"] == "2026-11-10" and bmi["height_date"] == "2026-09-01"
    assert bmi["band"] == "18.5 to 24.9 (WHO adult band)" and "27.5" in bmi["asian_note"]


def test_the_rendered_summary_lists_the_figures_with_dates_and_the_asian_population_note():
    text = render_text(build_content([], [], [], TODAY, body(**FULL)))
    assert "Body measurements" in text
    assert "Weight: 72 kg on 2026-11-10, entered by the patient" in text
    assert "Height: 172 cm on 2026-09-01, entered by a doctor" in text
    assert "BMI: 24.3 kg/m2 (weight of 2026-11-10, height of 2026-09-01), 18.5 to 24.9 (WHO adult band)." in text
    assert "For Asian populations, WHO identifies increased risk from 23.0 and high risk from 27.5" in text


def test_the_summary_never_says_normal_or_safe_even_with_body_data():
    result = build_content(
        [],
        [],
        [],
        TODAY,
        body(
            weights=[reading(80.0, "2026-10-25"), reading(75.0, "2026-11-10")], heights=[reading(172.0, "2026-09-01")]
        ),
    )
    blob = json.dumps(result).lower() + render_text(result).lower()
    assert " safe" not in blob and "normal" not in blob.replace("abnormal", "") and "malnutrition" not in blob


def test_a_bmi_needs_both_values_and_says_so():
    only_weight = summary(weights=[reading(72.0, "2026-11-10")])
    assert only_weight["body"]["bmi"] is None
    assert "BMI: needs a height." in render_text(only_weight)


def test_under_18_and_pregnancy_show_the_number_with_category_not_applicable():
    child = summary(weights=[reading(30.0, "2026-11-10")], heights=[reading(130.0, "2026-11-10")], age=9)["body"]["bmi"]
    assert (
        child["value"] == 17.8
        and child["band"] is None
        and "under 18" in child["band_note"]
        and child["asian_note"] is None
    )
    pregnant = {
        "status": "pregnant",
        "set_on": "2026-10-01",
        "set_by_role": "patient",
        "expired": False,
        "max_months": 10,
    }
    mother = summary(**FULL, pregnancy=pregnant)
    assert mother["body"]["bmi"]["band"] is None and "pregnant" in mother["body"]["bmi"]["band_note"]
    assert "category not applicable" in render_text(mother)


# --- missing data ---------------------------------------------------------------------------------------------------


def test_no_weight_or_height_is_listed_under_missing_data_and_nothing_is_invented():
    result = summary()
    assert "Weight not recorded." in result["missing_data"] and "Height not recorded." in result["missing_data"]
    assert result["body"]["weight"] is None and result["body"]["bmi"] is None
    text = render_text(result)
    assert "Weight: not recorded." in text and "Height: not recorded." in text


def test_only_the_missing_one_is_listed():
    missing = summary(weights=[reading(72.0, "2026-11-10")])["missing_data"]
    assert "Height not recorded." in missing and "Weight not recorded." not in missing


def test_an_old_weight_is_listed_as_out_of_date_with_the_app_rule_label():
    old = summary(weights=[reading(72.0, "2026-07-01")], heights=[reading(172.0, "2026-07-01")])
    line = next(m for m in old["missing_data"] if m.startswith("Weight is out of date"))
    assert "2026-07-01" in line and "older than 90 days" in line and "app rule (demo)" in line
    assert old["body"]["weight_current"] is False
    assert not [m for m in summary(**FULL)["missing_data"] if m.startswith("Weight is out of date")]


def test_a_child_weight_goes_out_of_date_after_30_days():
    stale = summary(weights=[reading(20.0, "2026-10-01")], heights=[reading(110.0, "2026-10-01")], age=6)
    assert stale["body"]["weight_current"] is False and stale["body"]["weight_max_age_days"] == 30


def test_without_body_data_given_the_summary_is_unchanged():
    result = build_content([], [], [], TODAY)
    assert result["body"] is None and "Weight not recorded." not in result["missing_data"]
    assert "Body measurements" not in render_text(result)


# --- the weight trend and its flag ------------------------------------------------------------------------------------


LOSS = {
    "weights": [reading(80.0, "2026-11-01"), reading(76.0, "2026-11-20")],
    "heights": [reading(172.0, "2026-09-01")],
}


def test_a_significant_loss_is_flagged_for_physician_review_with_dates_and_source():
    result = summary(**LOSS)
    [flag] = [f for f in result["flags"] if f["kind"] == "weight_change"]
    assert flag["code"] == "WEIGHT_LOSS" and flag["severity"] == "CAUTION"
    assert "-5.0% in 19 days (80 kg on 2026-11-01 to 76 kg on 2026-11-20)" in flag["message"]
    assert "significant weight loss, for physician review" in flag["message"]
    assert "White 2012" in flag["rule"] and "30 days" in flag["reason"]
    assert flag["sources"][0]["kind"] == "body" and flag["sources"][0]["date"] == "2026-11-20"
    assert "1 weight change(s) flagged" in result["key_findings"]["text"]
    assert "significant weight loss, for physician review" in render_text(result)


def test_a_significant_gain_says_so_and_is_labelled_an_app_rule():
    result = summary(weights=[reading(60.0, "2026-11-01"), reading(63.0, "2026-11-15")], heights=[])
    [flag] = [f for f in result["flags"] if f["kind"] == "weight_change"]
    assert flag["code"] == "WEIGHT_GAIN" and "significant weight gain, for physician review" in flag["message"]
    assert "app rule (demo)" in flag["rule"]


def test_a_small_change_raises_no_flag_but_is_shown_as_the_change_since_the_previous_reading():
    result = summary(weights=[reading(80.0, "2026-11-01"), reading(79.0, "2026-11-20")], heights=[])
    assert not [f for f in result["flags"] if f["kind"] == "weight_change"]
    assert "Change since the previous reading: -1.2% (2026-11-01 to 2026-11-20)." in render_text(result)
    assert "weight change(s) flagged" not in result["key_findings"]["text"]


def test_the_history_is_listed_oldest_first_with_the_last_six_readings():
    weights = [reading(70.0 + i, f"2026-0{i + 1}-15") for i in range(8)]
    history = summary(weights=weights, heights=[])["body"]["weight_history"]
    assert [h["date"] for h in history] == [f"2026-0{i + 1}-15" for i in range(2, 8)]
    assert "Weight history: 72 kg (2026-03-15)" in render_text(summary(weights=weights, heights=[]))


# --- pregnancy line -----------------------------------------------------------------------------------------------------


def test_the_pregnancy_status_line_says_when_and_by_whom_or_that_it_expired():
    on = {"status": "not_pregnant", "set_on": "2026-10-01", "set_by_role": "doctor", "expired": False, "max_months": 10}
    assert "Pregnancy status: not pregnant (set 2026-10-01 by the doctor)." in render_text(
        summary(**FULL, pregnancy=on)
    )
    gone = {
        "status": "not_recorded",
        "set_on": "2025-01-05",
        "set_by_role": "patient",
        "expired": True,
        "max_months": 10,
    }
    assert "older than 10 months, app rule (demo)" in render_text(summary(**FULL, pregnancy=gone))
    assert "Pregnancy status: not recorded." in render_text(summary(**FULL))


# --- versions: the fingerprint and the trigger ---------------------------------------------------------------------------


def row(id_, weight=None, height=None, on=date(2026, 11, 10), by="patient", status="active"):
    return SimpleNamespace(id=id_, weight_kg=weight, height_cm=height, measured_on=on, added_by_role=by, status=status)


def fingerprint(monkeypatch, rows, dob=date(1986, 1, 1), pregnancy_status=None):
    monkeypatch.setattr(body_record, "rows_for", lambda db, patient_id: rows)
    profile = SimpleNamespace(
        date_of_birth=dob, pregnancy_status=pregnancy_status,
        pregnancy_status_set_at=None, pregnancy_status_set_by_role=None,
    )  # fmt: skip
    patient = SimpleNamespace(id=1, patient_profile=profile)
    data = versions._body_input(None, patient)
    return data, versions._hash(data)


def test_a_new_reading_changes_the_fingerprint_and_the_same_data_does_not(monkeypatch):
    _, base = fingerprint(monkeypatch, [row(1, 72.0)])
    assert fingerprint(monkeypatch, [row(1, 72.0)])[1] == base
    assert fingerprint(monkeypatch, [row(1, 72.0), row(2, 73.0)])[1] != base
    assert fingerprint(monkeypatch, [row(1, 72.5)])[1] != base  # a corrected value
    assert fingerprint(monkeypatch, [row(1, 72.0), row(2, 99.0, status="removed")])[1] == base  # a hidden reading


def test_the_body_input_is_oldest_first_and_holds_age_and_pregnancy_status(monkeypatch):
    rows = [row(2, 74.0, on=date(2026, 11, 15)), row(1, 72.0, on=date(2026, 11, 1)), row(3, height=170.0)]
    data, _ = fingerprint(monkeypatch, rows)
    assert [w["value"] for w in data["weights"]] == [72.0, 74.0] and data["heights"][0]["value"] == 170.0
    assert data["age"] >= 39 and data["pregnancy"]["status"] == "not_recorded"


def test_a_pregnancy_status_change_changes_the_fingerprint(monkeypatch):
    _, none = fingerprint(monkeypatch, [row(1, 72.0)])
    _, same = fingerprint(monkeypatch, [row(1, 72.0)], pregnancy_status="maybe")  # unknown word: not recorded
    assert same == none


def test_describe_change_names_a_weight_height_or_pregnancy_change():
    base = {"versions": {"summary": 2}, "reports": {}, "vitals": "v", "medications": "m", "body": "b1"}
    assert versions.describe_change(base, {**base, "body": "b2"}) == "weight, height or pregnancy status changed."
    assert versions.describe_change(base, base) == "No change in the patient's data."


def test_an_older_manifest_without_a_body_key_is_not_reported_as_a_body_change():
    old = {"versions": {"summary": 1}, "reports": {}, "vitals": "v", "medications": "m"}
    assert versions.describe_change(old, {**old}) == "No change in the patient's data."


def test_the_summary_version_was_raised_so_earlier_summaries_regenerate_with_the_new_section():
    assert SUMMARY_VERSION == 2
    old = {"versions": {"summary": 1}}
    new = {"versions": {"summary": SUMMARY_VERSION}, "reports": {}, "vitals": "v", "medications": "m"}
    assert "summary rules updated" in versions.describe_change(
        {**old, "reports": {}, "vitals": "v", "medications": "m"}, new
    )


# --- the AI may only explain: its numbers must come from the facts -------------------------------------------------------


def test_the_ai_facts_carry_the_weight_height_bmi_and_the_flag_so_the_guard_knows_every_number():
    result = build_content([], [], [], TODAY, body(**LOSS))
    source = facts(result)
    assert "- Weight 76 kg on 2026-11-20" in source and "- Height 172 cm on 2026-09-01" in source
    assert "- BMI 25.7 kg/m2" in source and "significant weight loss, for physician review" in source
    assert numbers_not_in_source("Weight fell from 80 kg to 76 kg and the BMI is 25.7.", source) == []
    assert numbers_not_in_source("The weight is 74 kg.", source) == ["74"]


def test_the_wording_instructions_forbid_interpreting_body_figures():
    from services.icse.wording import INSTRUCTIONS

    assert "do not interpret them" in INSTRUCTIONS
