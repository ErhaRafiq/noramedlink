"""MSCIE weight-based dose limits and the Cockcroft-Gault panel.

The knowledge-base table ships empty until the team has verified every row, so these tests inject TEST-ONLY rows
(`ROWS`): their numbers are arbitrary and are not the project's knowledge base. No database, no network.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from services.mscie import context as mscie_context
from services.mscie import weight_doses
from services.mscie.engine import PatientContext, Proposed, check

TODAY = date(2026, 11, 20)

# TEST-ONLY values. paracetamol already has an adult row in dose_limits.csv; amoxicillin has none.
ROWS = [
    {
        "generic": "paracetamol", "applies_under_age": "12", "applies_under_kg": "50",
        "max_single_mg_per_kg": "15", "max_daily_mg_per_kg": "60", "max_single_mg": "1000", "max_daily_mg": "4000",
        "indication_note": "test", "source": "FDA-LABEL (acetaminophen)",
    },
    {
        "generic": "amoxicillin", "applies_under_age": "12", "applies_under_kg": "60",
        "max_single_mg_per_kg": "25", "max_daily_mg_per_kg": "50", "max_single_mg": "1000", "max_daily_mg": "3000",
        "indication_note": "test", "source": "FDA-LABEL (amoxicillin)",
    },
]  # fmt: skip


@pytest.fixture(autouse=True)
def test_rows(monkeypatch):
    real = weight_doses.records
    monkeypatch.setattr(weight_doses, "records", lambda name: ROWS if name == "dose_limits_per_kg" else real(name))


def weight(kg, on="2026-11-10", current=True, by="the patient"):
    return {"value": kg, "date": on, "entered_by": by, "current": current, "max_age_days": 90}


def alerts(medicine, dose, frequency=None, *, age=8, kg=None, current=True):
    context = PatientContext(age=age, weight=weight(kg, current=current) if kg is not None else None)
    [result] = check(context, [Proposed(medicine, dose, frequency)])
    return {a["rule_id"]: a for a in result["alerts"] if a["kind"] == "dose"}


# --- the shipped table is empty: nothing fires until it is verified ----------------------------------------------


def test_the_real_table_is_empty_so_no_weight_alert_can_fire(monkeypatch):
    monkeypatch.undo()
    assert weight_doses.records("dose_limits_per_kg") == []
    context = PatientContext(age=5, weight=None)
    [result] = check(context, [Proposed("paracetamol", "5000 mg", "TDS")])
    assert not [a for a in result["alerts"] if a["rule_id"].startswith(("WEIGHT", "DOSE-KG", "DOSE-ABS"))]


# --- per-kg limits -------------------------------------------------------------------------------------------


def test_a_dose_within_the_per_kg_limit_raises_nothing():
    assert alerts("paracetamol", "270 mg", "TDS", kg=18) == {}  # 15 mg/kg, 810 mg a day


def test_a_single_dose_over_the_per_kg_limit():
    found = alerts("paracetamol", "300 mg", kg=18)  # 16.7 mg/kg; limit 15 mg/kg = 270 mg
    assert set(found) == {"DOSE-KG-SINGLE"}
    alert = found["DOSE-KG-SINGLE"]
    assert alert["severity"] == "major" and alert["requires_justification"]
    assert "16.7 mg/kg" in alert["effect"] and "270" in alert["effect"] and "demo knowledge base" in alert["effect"]
    assert any("18 kg on 2026-11-10 (entered by the patient)" in line for line in alert["evidence"])


def test_a_daily_dose_over_the_per_kg_limit():
    found = alerts("paracetamol", "150 mg", "every 4 hours", kg=14)  # 900 mg a day; limit 60 x 14 = 840 mg
    assert set(found) == {"DOSE-KG-DAILY"} and "64.3 mg/kg" in found["DOSE-KG-DAILY"]["effect"]


def test_the_limit_scales_with_the_weight():
    assert alerts("paracetamol", "300 mg", kg=25) == {}  # 12 mg/kg
    assert "DOSE-KG-SINGLE" in alerts("paracetamol", "300 mg", kg=19)


def test_the_boundary_is_not_an_alert():
    assert alerts("paracetamol", "270 mg", kg=18) == {}


# --- never above the adult maximum ---------------------------------------------------------------------------


def test_a_heavy_child_is_never_allowed_more_than_the_adult_maximum():
    # 55 kg: 25 mg/kg would be 1375 mg, but the adult single maximum is 1000 mg. Amoxicillin has no old rule row.
    found = alerts("amoxicillin", "1250 mg", "BD", age=11, kg=55)
    assert "DOSE-ABS-SINGLE" in found and "DOSE-KG-SINGLE" not in found
    assert "1000 mg" in found["DOSE-ABS-SINGLE"]["effect"]
    assert "DOSE-ABS-DAILY" not in found  # 2 x 1250 = 2500 mg a day is under the 3000 mg maximum


def test_the_absolute_maximum_applies_without_any_weight():
    found = alerts("amoxicillin", "1500 mg", "TDS", age=40, kg=None)  # adult, no weight recorded
    assert set(found) == {"DOSE-ABS-SINGLE", "DOSE-ABS-DAILY"}


def test_a_medicine_with_an_old_adult_row_does_not_repeat_the_absolute_alert():
    found = alerts("paracetamol", "1500 mg", "TDS", age=40, kg=70)
    assert "DOSE-ABS-SINGLE" not in found and "DOSE-ABS-DAILY" not in found
    assert "DOSE-SINGLE" in found  # the existing rule in dose_limits.csv


def test_an_adult_at_or_above_the_weight_cutoff_gets_only_the_absolute_rule():
    assert alerts("amoxicillin", "1000 mg", "TDS", age=40, kg=80) == {}
    # 59 kg is under the 60 kg cutoff: per-kg applies. 3 x 1000 = 3000 mg is over 50 x 59 = 2950 mg a day.
    assert set(alerts("amoxicillin", "1000 mg", "TDS", age=40, kg=59)) == {"DOSE-KG-DAILY"}


def test_an_adult_under_the_cutoff_weight_is_checked_per_kg():
    found = alerts("paracetamol", "800 mg", age=40, kg=45)  # 17.8 mg/kg, limit 675 mg
    assert set(found) == {"DOSE-KG-SINGLE"}


# --- weight missing or out of date: skip the check, say why, never assume ------------------------------------------


def test_a_child_with_no_weight_gets_weight_needed_and_no_per_kg_check():
    found = alerts("paracetamol", "5000 mg", "TDS", age=6, kg=None)
    assert set(found) == {
        "DOSE-SINGLE",
        "DOSE-DAILY",
        "WEIGHT-NEEDED",
    }  # the first two: the adult rule, no weight needed
    notice = found["WEIGHT-NEEDED"]
    assert notice["severity"] == "info" and not notice["requires_justification"]
    assert "weight needed for dose check" in notice["title"].lower()
    assert "does not mean the dose is right" in notice["management"]


def test_an_unknown_age_with_no_weight_also_needs_a_weight():
    assert "WEIGHT-NEEDED" in alerts("paracetamol", "100 mg", age=None, kg=None)


def test_an_adult_with_no_weight_gets_no_notice():
    assert "WEIGHT-NEEDED" not in alerts("paracetamol", "500 mg", "TDS", age=40, kg=None)


def test_a_stale_weight_is_not_used_and_the_notice_says_to_re_measure():
    found = alerts("paracetamol", "300 mg", age=8, kg=18, current=False)  # would be over the limit if it were used
    assert set(found) == {"WEIGHT-STALE"}
    notice = found["WEIGHT-STALE"]
    assert "re-measure before dose check" in notice["title"] and "app rule (demo)" in notice["effect"]
    assert "90 days" in notice["effect"] and notice["severity"] == "info"


def test_a_stale_adult_weight_above_the_cutoff_raises_no_notice():
    assert "WEIGHT-STALE" not in alerts("paracetamol", "500 mg", age=40, kg=80, current=False)


def test_an_unreadable_dose_gives_no_per_kg_alert_but_the_weight_notices_remain():
    assert alerts("paracetamol", "5 ml", age=8, kg=18) == {}
    assert "WEIGHT-NEEDED" in alerts("paracetamol", "5 ml", age=8, kg=None)


def test_a_medicine_without_a_row_is_untouched():
    assert not [a for a in alerts("metformin", "500 mg", "BD", age=8, kg=None) if a.startswith(("WEIGHT", "DOSE-KG"))]


# --- the patient context (age, sex, latest weight) -------------------------------------------------------------


def test_the_context_reads_age_sex_and_the_latest_weight(monkeypatch):
    rows = [
        SimpleNamespace(id=1, status="active", weight_kg=70.0, measured_on=date(2026, 5, 1), added_by_role="patient"),
        SimpleNamespace(id=2, status="active", weight_kg=72.5, measured_on=date(2026, 11, 1), added_by_role="doctor"),
        SimpleNamespace(
            id=3, status="removed", weight_kg=99.0, measured_on=date(2026, 11, 15), added_by_role="patient"
        ),
    ]
    monkeypatch.setattr(mscie_context.body_record, "rows_for", lambda db, patient_id: rows)
    patient = SimpleNamespace(id=1, patient_profile=SimpleNamespace(date_of_birth=date(1990, 12, 1), gender="Female"))
    context = PatientContext()
    mscie_context._add_body(None, patient, context, TODAY)
    assert context.age == 35 and context.sex == "female"
    assert context.weight == {
        "value": 72.5, "date": "2026-11-01", "entered_by": "a doctor", "current": True, "max_age_days": 90,
    }  # fmt: skip


def test_the_context_marks_an_old_weight_not_current_and_a_child_gets_the_shorter_window(monkeypatch):
    rows = [
        SimpleNamespace(id=1, status="active", weight_kg=20.0, measured_on=date(2026, 9, 1), added_by_role="patient")
    ]
    monkeypatch.setattr(mscie_context.body_record, "rows_for", lambda db, patient_id: rows)
    child = SimpleNamespace(id=1, patient_profile=SimpleNamespace(date_of_birth=date(2018, 1, 1), gender="male"))
    context = PatientContext()
    mscie_context._add_body(None, child, context, TODAY)
    assert context.age == 8 and context.weight["current"] is False and context.weight["max_age_days"] == 30


def test_no_weight_stays_none_never_a_default(monkeypatch):
    monkeypatch.setattr(mscie_context.body_record, "rows_for", lambda db, patient_id: [])
    patient = SimpleNamespace(id=1, patient_profile=SimpleNamespace(date_of_birth=date(1990, 1, 1), gender="other"))
    context = PatientContext()
    mscie_context._add_body(None, patient, context, TODAY)
    assert context.weight is None and context.sex is None


# --- Cockcroft-Gault next to eGFR: information only ----------------------------------------------------------------


def labs(value=1.0, on="2026-11-01"):
    return {"Creatinine": {"value": value, "unit": "mg/dL", "date": on, "source": "report 1"}}


def test_the_panel_shows_the_estimate_with_its_inputs():
    context = PatientContext(age=60, sex="male", weight=weight(80.0, on="2026-11-10"), labs=labs())
    panel = mscie_context._creatinine_clearance(context)
    assert panel["value"] == 88.9 and panel["missing"] == []
    assert panel["inputs"]["weight_date"] == "2026-11-10" and panel["inputs"]["creatinine_date"] == "2026-11-01"
    assert "eGFR" in panel["note"]


def test_the_panel_names_what_is_missing():
    panel = mscie_context._creatinine_clearance(PatientContext(age=60, sex="male"))
    assert panel["value"] is None and panel["missing"] == ["body weight", "serum creatinine"]


def test_the_summary_carries_the_panel_the_weight_and_the_age():
    summary = mscie_context.context_summary(PatientContext(age=60, sex="male", weight=weight(80.0), labs=labs()))
    assert summary["creatinine_clearance"]["value"] == 88.9 and summary["weight"]["value"] == 80.0
    assert summary["age"] == 60 and summary["pregnancy"] == "not_recorded"


def test_creatinine_clearance_never_changes_an_alert():
    plain = PatientContext(age=60, sex="male", labs=labs(5.0))
    rich = PatientContext(age=60, sex="male", weight=weight(30.0), labs=labs(5.0))  # a very low clearance
    items = [Proposed("metformin", "1000 mg", "BD"), Proposed("ibuprofen", "400 mg", "TDS")]
    assert check(plain, items) == check(rich, items)
