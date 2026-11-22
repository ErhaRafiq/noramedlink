"""MSCIE weight-based dose limits (the verified, FDA-label demo table) and the Cockcroft-Gault panel.

Every tier of `dose_limits_per_kg.csv` has its own test below. These run on the real table. No database, no network.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from services.mscie import context as mscie_context
from services.mscie import weight_doses
from services.mscie.engine import PatientContext, Proposed, check

TODAY = date(2026, 11, 20)
NOT_COVERED = "verify dose: not covered by demo table"


def weight(kg, on="2026-11-10", current=True, by="the patient"):
    return {"value": kg, "date": on, "entered_by": by, "current": current, "max_age_days": 90}


def run(medicine, dose, frequency=None, *, months=None, kg=None, current=True):
    """The dose alerts for one prescription for a patient `months` old."""
    context = PatientContext(
        age=None if months is None else months // 12,
        age_months=months,
        weight=weight(kg, current=current) if kg is not None else None,
    )
    [result] = check(context, [Proposed(medicine, dose, frequency)])
    return {a["rule_id"]: a for a in result["alerts"] if a["kind"] == "dose"}


def new_rules(found):
    return {r for r in found if r.startswith(("DOSE-KG", "DOSE-ABS", "WEIGHT", "NOT-COVERED", "AGE", "INDICATION"))}


# --- the table itself -----------------------------------------------------------------------------------------


def test_the_table_covers_exactly_the_verified_medicines_and_no_co_amoxiclav():
    generics = {r["generic"] for r in weight_doses.records("dose_limits_per_kg")}
    assert generics == {"paracetamol", "amoxicillin", "azithromycin", "ibuprofen", "cefixime"}
    assert "amoxicillin and clavulanic acid" not in generics  # future work: "500/125" strengths are not parsed


def test_every_tier_is_labelled_demo_and_cites_a_label_with_a_url_in_sources():
    sources = {r["key"]: r["description"] for r in weight_doses.records("sources")}
    for row in weight_doses.records("dose_limits_per_kg"):
        text = sources[row["source"]]
        assert text.startswith("Demo knowledge base.") and (
            "accessdata.fda.gov" in text or "dailymed.nlm.nih.gov" in text
        ), row["tier"]
        assert "BNF" not in text


# --- paracetamol: FDA acetaminophen injection label ---------------------------------------------------------------


def test_paracetamol_under_two_years_is_not_covered():
    for months in (0, 11, 23):
        found = run("paracetamol", "100 mg", months=months, kg=8)
        assert NOT_COVERED in found["NOT-COVERED"]["title"].lower() and found["NOT-COVERED"]["severity"] == "info"
        assert new_rules(found) == {"NOT-COVERED"}


def test_paracetamol_two_years_and_under_50_kg_single_dose_limit_is_15_mg_per_kg():
    assert new_rules(run("paracetamol", "270 mg", months=60, kg=18)) == set()  # 15 mg/kg: at the limit
    found = run("paracetamol", "300 mg", months=60, kg=18)  # 16.7 mg/kg
    assert set(found) == {"DOSE-KG-SINGLE"} and found["DOSE-KG-SINGLE"]["severity"] == "major"
    assert "16.7 mg/kg" in found["DOSE-KG-SINGLE"]["effect"] and "270 mg" in found["DOSE-KG-SINGLE"]["effect"]
    assert "all paracetamol-containing products" in found["DOSE-KG-SINGLE"]["effect"]


def test_paracetamol_single_dose_is_capped_at_750_mg_at_the_top_of_the_band():
    assert new_rules(run("paracetamol", "745 mg", months=200, kg=49.9)) == set()  # 15 x 49.9 = 748.5
    assert "DOSE-KG-SINGLE" in run("paracetamol", "750 mg", months=200, kg=49.9)


def test_paracetamol_two_years_and_under_50_kg_daily_limit_is_75_mg_per_kg():
    assert new_rules(run("paracetamol", "180 mg", "every 4 hours", months=60, kg=15)) == set()  # 1080 < 1125
    found = run("paracetamol", "200 mg", "every 4 hours", months=60, kg=15)  # 1200 mg a day, 80 mg/kg
    assert set(found) == {"DOSE-KG-DAILY"} and "80.0 mg/kg" in found["DOSE-KG-DAILY"]["effect"]


def test_paracetamol_daily_limit_is_capped_at_3750_mg_under_50_kg():
    found = run("paracetamol", "700 mg", "every 4 hours", months=200, kg=49.9)  # 4200 mg; 75 x 49.9 = 3742.5
    assert "DOSE-KG-DAILY" in found


def test_paracetamol_there_is_no_four_doses_a_day_rule():
    # six doses a day inside the per-kg daily limit raise nothing: the label does not say "up to 4 doses a day"
    assert new_rules(run("paracetamol", "150 mg", "every 4 hours", months=60, kg=15)) == set()  # 900 < 1125


def test_paracetamol_50_kg_and_over_uses_the_adult_limits_from_the_existing_rule():
    assert new_rules(run("paracetamol", "1000 mg", "QID", months=400, kg=50)) == set()
    found = run("paracetamol", "1500 mg", "TDS", months=400, kg=50)
    assert {"DOSE-SINGLE", "DOSE-DAILY"} <= set(found) and not new_rules(found)  # reported once, by dose_limits.csv


def test_paracetamol_boundaries_at_2_years_and_at_50_kg():
    assert "NOT-COVERED" in run("paracetamol", "100 mg", months=23, kg=10)
    assert "NOT-COVERED" not in run("paracetamol", "100 mg", months=24, kg=10)
    assert "DOSE-KG-SINGLE" in run("paracetamol", "760 mg", months=300, kg=49.99)  # still the per-kg tier
    assert "DOSE-KG-SINGLE" not in run("paracetamol", "760 mg", months=300, kg=50)  # adult tier


# --- amoxicillin: FDA label ---------------------------------------------------------------------------------------


def test_amoxicillin_under_three_months_daily_limit_is_30_mg_per_kg_and_red():
    assert new_rules(run("amoxicillin", "50 mg", "BD", months=2, kg=4)) == set()  # 25 mg/kg a day
    found = run("amoxicillin", "80 mg", "BD", months=2, kg=4)  # 40 mg/kg a day
    assert set(found) == {"DOSE-KG-DAILY"} and found["DOSE-KG-DAILY"]["severity"] == "major"
    assert "40.0 mg/kg" in found["DOSE-KG-DAILY"]["effect"] and found["DOSE-KG-DAILY"]["requires_justification"]


def test_amoxicillin_three_months_and_under_40_kg_above_45_mg_per_kg_is_yellow_not_red():
    assert new_rules(run("amoxicillin", "225 mg", "BD", months=36, kg=10)) == set()  # 45 mg/kg: at the limit
    found = run("amoxicillin", "300 mg", "BD", months=36, kg=10)  # 60 mg/kg a day
    alert = found["DOSE-KG-DAILY"]
    assert set(found) == {"DOSE-KG-DAILY"} and alert["severity"] == "moderate" and alert["level"] == "CAUTION"
    assert not alert["requires_justification"]
    assert (
        "Above labelled dose; high-dose regimens are used for some ear infections, verify indication."
        in alert["effect"]
    )


def test_amoxicillin_under_40_kg_has_no_per_dose_limit():
    assert new_rules(run("amoxicillin", "800 mg", "OD", months=120, kg=30)) == set()  # 26.7 mg/kg a day


def test_amoxicillin_boundaries_at_3_months_and_40_kg():
    assert "DOSE-KG-DAILY" in run("amoxicillin", "80 mg", "BD", months=2, kg=4)  # the infant tier ends after month 2
    assert run("amoxicillin", "80 mg", "BD", months=3, kg=4) == {}  # 40 mg/kg: under the 45 mg/kg tier
    assert "DOSE-KG-DAILY" in run("amoxicillin", "1000 mg", "BD", months=60, kg=39.9)  # 2000 mg a day = 50.1 mg/kg
    assert run("amoxicillin", "1000 mg", "BD", months=60, kg=40) == {}  # adult tier: 1000 mg, 2000 mg a day is fine


# --- azithromycin: FDA Zithromax label -------------------------------------------------------------------------------


def test_azithromycin_under_six_months_is_not_covered():
    assert set(run("azithromycin", "50 mg", months=5, kg=6)) == {"NOT-COVERED"}


def test_azithromycin_child_alert_only_above_30_mg_per_kg_and_never_a_daily_alert():
    assert set(run("azithromycin", "540 mg", months=60, kg=18)) == {"INDICATION-NOTE"}  # 30 mg/kg: at the limit
    found = run("azithromycin", "600 mg", months=60, kg=18)  # 33.3 mg/kg
    assert set(found) == {"DOSE-KG-SINGLE"} and "33.3 mg/kg" in found["DOSE-KG-SINGLE"]["effect"]
    assert set(run("azithromycin", "200 mg", "QID", months=60, kg=18)) == {"INDICATION-NOTE"}  # no daily rule


def test_azithromycin_child_dose_is_capped_at_1500_mg():
    found = run("azithromycin", "1600 mg", months=200, kg=70)  # 30 mg/kg would be 2100 mg
    assert set(found) == {"DOSE-ABS-SINGLE"} and "1500 mg" in found["DOSE-ABS-SINGLE"]["effect"]
    assert set(run("azithromycin", "1500 mg", months=200, kg=70)) == {"INDICATION-NOTE"}


def test_azithromycin_adult_alert_above_2000_mg_and_needs_no_weight():
    found = run("azithromycin", "2500 mg", months=400, kg=None)
    assert set(found) == {"DOSE-ABS-SINGLE"} and "2000 mg" in found["DOSE-ABS-SINGLE"]["effect"]
    assert set(run("azithromycin", "2000 mg", months=400, kg=None)) == {"INDICATION-NOTE"}


def test_azithromycin_within_the_limit_says_the_dose_depends_on_the_indication():
    note = run("azithromycin", "500 mg", months=400)["INDICATION-NOTE"]
    assert note["severity"] == "info" and not note["requires_justification"]
    assert "Dose depends on indication; the prescription form has no indication field." in note["effect"]


def test_azithromycin_boundaries_at_6_months_and_18_years():
    assert "NOT-COVERED" in run("azithromycin", "50 mg", months=5, kg=6)
    assert "NOT-COVERED" not in run("azithromycin", "50 mg", months=6, kg=6)
    assert "DOSE-KG-SINGLE" in run("azithromycin", "1300 mg", months=215, kg=40)  # a child: 32.5 mg/kg
    assert "DOSE-KG-SINGLE" not in run("azithromycin", "1300 mg", months=216, kg=40)  # an adult: under 2000 mg


# --- ibuprofen: FDA label ------------------------------------------------------------------------------------------


def test_ibuprofen_under_six_months_is_not_covered():
    assert set(run("ibuprofen", "50 mg", months=5, kg=6)) == {"NOT-COVERED"}


def test_ibuprofen_per_kg_limits_apply_from_6_months_up_to_12_years():
    assert new_rules(run("ibuprofen", "100 mg", "QID", months=12, kg=10)) == set()  # 10 mg/kg, 40 mg/kg a day
    found = run("ibuprofen", "110 mg", months=12, kg=10)  # 11 mg/kg a dose
    assert set(found) == {"DOSE-KG-CAUTION"} and "11.0 mg/kg" in found["DOSE-KG-CAUTION"]["effect"]
    assert found["DOSE-KG-CAUTION"]["severity"] == "moderate" and not found["DOSE-KG-CAUTION"]["requires_justification"]


def test_ibuprofen_age_boundaries_6_months_and_12_years():
    assert "NOT-COVERED" in run("ibuprofen", "50 mg", months=5, kg=6)  # 5 months
    assert "NOT-COVERED" not in run("ibuprofen", "50 mg", months=6, kg=7)  # 6 months
    assert "DOSE-KG-CAUTION" in run("ibuprofen", "110 mg", months=143, kg=10)  # 11 years 11 months: per-kg applies
    assert new_rules(run("ibuprofen", "110 mg", months=144, kg=10)) == set()  # 12 years: the adult rule only


def test_ibuprofen_single_dose_10_0_and_10_1_mg_per_kg():
    assert new_rules(run("ibuprofen", "300 mg", months=60, kg=30)) == set()  # exactly 10.0 mg/kg
    found = run("ibuprofen", "303 mg", months=60, kg=30)  # 10.1 mg/kg
    assert set(found) == {"DOSE-KG-CAUTION"}


def test_ibuprofen_daily_40_0_and_40_1_mg_per_kg_a_day():
    assert new_rules(run("ibuprofen", "200 mg", "every 4 hours", months=60, kg=30)) == set()  # 1200 mg, 40.0 mg/kg
    found = run("ibuprofen", "200.5 mg", "every 4 hours", months=60, kg=30)  # 1203 mg, 40.1 mg/kg
    assert set(found) == {"DOSE-KG-CAUTION"} and "40.1 mg/kg" in found["DOSE-KG-CAUTION"]["effect"]
    assert found["DOSE-KG-CAUTION"]["severity"] == "moderate"


def test_ibuprofen_daily_50_0_and_50_1_mg_per_kg_a_day_is_red_above_50():
    found = run("ibuprofen", "250 mg", "every 4 hours", months=60, kg=30)  # 1500 mg, 50.0 mg/kg: caution only
    assert set(found) == {"DOSE-KG-CAUTION"}
    found = run("ibuprofen", "250.5 mg", "every 4 hours", months=60, kg=30)  # 1503 mg, 50.1 mg/kg
    assert set(found) == {"DOSE-KG-DAILY"} and found["DOSE-KG-DAILY"]["severity"] == "major"
    assert found["DOSE-KG-DAILY"]["requires_justification"]
    assert "40 mg/kg" in found["DOSE-KG-DAILY"]["effect"]  # the label's note on serious adverse events


def test_ibuprofen_never_above_the_adult_maximum_even_for_a_child():
    found = run("ibuprofen", "900 mg", months=120, kg=90)  # 10 mg/kg, but over 800 mg: the existing red rule
    assert "DOSE-SINGLE" in found and found["DOSE-SINGLE"]["severity"] == "major"


def test_ibuprofen_child_without_weight_gets_the_notice_and_the_adult_maximum_only():
    found = run("ibuprofen", "400 mg", "TDS", months=60, kg=None)
    assert set(new_rules(found)) == {"WEIGHT-NEEDED"}
    assert "DOSE-SINGLE" in run("ibuprofen", "900 mg", months=60, kg=None)


def test_ibuprofen_adult_only_the_existing_rule_applies():
    assert new_rules(run("ibuprofen", "800 mg", "QID", months=400, kg=None)) == set()
    assert "DOSE-DAILY" in run("ibuprofen", "1000 mg", "QID", months=400, kg=70)  # 4000 mg a day


# --- cefixime: FDA label -------------------------------------------------------------------------------------------


def test_cefixime_under_six_months_is_not_covered():
    assert set(run("cefixime", "20 mg", months=5, kg=6)) == {"NOT-COVERED"}


def test_cefixime_child_up_to_45_kg_is_8_mg_per_kg_a_day():
    assert new_rules(run("cefixime", "160 mg", "OD", months=60, kg=20)) == set()  # 8 mg/kg: at the limit
    assert new_rules(run("cefixime", "80 mg", "BD", months=60, kg=20)) == set()  # 4 mg/kg twice a day
    found = run("cefixime", "200 mg", "OD", months=60, kg=20)  # 10 mg/kg
    assert set(found) == {"DOSE-KG-SINGLE", "DOSE-KG-DAILY"}


def test_cefixime_child_over_45_kg_gets_the_adult_dose_of_400_mg():
    assert new_rules(run("cefixime", "400 mg", "OD", months=120, kg=50)) == set()
    assert set(run("cefixime", "500 mg", "OD", months=120, kg=50)) == {"DOSE-ABS-SINGLE", "DOSE-ABS-DAILY"}


def test_cefixime_older_than_12_years_gets_the_adult_dose_whatever_the_weight():
    assert new_rules(run("cefixime", "400 mg", "OD", months=180, kg=None)) == set()  # no weight needed
    assert "DOSE-ABS-SINGLE" in run("cefixime", "500 mg", "OD", months=180, kg=None)


def test_cefixime_boundaries_at_45_kg_and_12_years():
    assert "DOSE-KG-SINGLE" in run("cefixime", "380 mg", "OD", months=120, kg=45)  # 8 mg/kg is 360 mg at 45 kg
    assert new_rules(run("cefixime", "380 mg", "OD", months=120, kg=45.1)) == set()  # adult tier: 400 mg is fine
    assert "DOSE-KG-SINGLE" in run("cefixime", "200 mg", "OD", months=144, kg=20)  # exactly 12 years: still a child
    assert "DOSE-KG-SINGLE" not in run("cefixime", "200 mg", "OD", months=145, kg=20)  # older than 12


# --- amoxicillin-clavulanate is excluded; medicines without rows are untouched --------------------------------------


def test_amoxicillin_clavulanate_has_no_weight_rule_yet():
    assert not new_rules(run("co-amoxiclav", "625 mg", "TDS", months=60, kg=5))


def test_a_medicine_without_a_tier_is_untouched():
    assert not new_rules(run("metformin", "500 mg", "BD", months=60, kg=None))


# --- weight missing or out of date: skip the check, never assume ----------------------------------------------------


def test_a_stale_weight_is_not_used_and_still_says_weight_needed():
    found = run("paracetamol", "300 mg", months=60, kg=18, current=False)  # would be over the limit if it were used
    assert set(found) == {"WEIGHT-STALE"}
    title = found["WEIGHT-STALE"]["title"].lower()
    assert "weight needed for dose check" in title and "weight is out of date, re-measure before dose check" in title
    assert "app rule (demo)" in found["WEIGHT-STALE"]["effect"] and "90 days" in found["WEIGHT-STALE"]["effect"]


def test_a_missing_age_skips_the_check():
    context = PatientContext(age=None, age_months=None, weight=weight(18))
    [result] = check(context, [Proposed("paracetamol", "300 mg", None)])
    assert [a["rule_id"] for a in result["alerts"] if a["kind"] == "dose"] == ["AGE-NEEDED"]


def test_an_unreadable_dose_gives_no_dose_alert_but_the_weight_notice_remains():
    assert new_rules(run("paracetamol", "5 ml", months=60, kg=18)) == set()
    assert "WEIGHT-NEEDED" in run("paracetamol", "5 ml", months=60, kg=None)


# --- the patient context (age, sex, latest weight) -----------------------------------------------------------------


def test_the_context_reads_age_months_sex_and_the_latest_weight(monkeypatch):
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
    assert context.age == 35 and context.age_months == 431 and context.sex == "female"
    assert context.weight == {
        "value": 72.5, "date": "2026-11-01", "entered_by": "a doctor", "current": True, "max_age_days": 90,
    }  # fmt: skip


@pytest.mark.parametrize(
    ("born", "months"),
    [
        (date(2026, 11, 20), 0),
        (date(2026, 8, 20), 3),
        (date(2026, 8, 21), 2),
        (date(2026, 5, 20), 6),
        (date(2024, 11, 20), 24),
        (date(2024, 11, 21), 23),
    ],
)
def test_age_in_whole_months_counts_the_day_of_the_month(monkeypatch, born, months):
    monkeypatch.setattr(mscie_context.body_record, "rows_for", lambda db, patient_id: [])
    patient = SimpleNamespace(id=1, patient_profile=SimpleNamespace(date_of_birth=born, gender="male"))
    context = PatientContext()
    mscie_context._add_body(None, patient, context, TODAY)
    assert context.age_months == months


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
    plain = PatientContext(age=60, age_months=720, sex="male", labs=labs(5.0))
    rich = PatientContext(age=60, age_months=720, sex="male", weight=weight(30.0), labs=labs(5.0))
    items = [Proposed("metformin", "1000 mg", "BD"), Proposed("ibuprofen", "400 mg", "TDS")]
    assert check(plain, items) == check(rich, items)


# --- amoxicillin adult single dose: yellow from 1000 mg, red above 3000 mg --------------------------------------------


@pytest.mark.parametrize(
    ("dose", "rule", "severity"),
    [("1000 mg", None, None), ("1001 mg", "DOSE-ABS-CAUTION", "moderate"), ("3000 mg", "DOSE-ABS-CAUTION", "moderate"),
     ("3001 mg", "DOSE-ABS-SINGLE", "major")],
)  # fmt: skip
def test_amoxicillin_adult_single_dose_bands(dose, rule, severity):
    found = run("amoxicillin", dose, months=400, kg=70)  # no frequency: only the single dose is judged
    if rule is None:
        assert new_rules(found) == set()
        return
    assert set(found) == {rule} and found[rule]["severity"] == severity
    if severity == "moderate":
        alert = found[rule]
        assert alert["level"] == "CAUTION" and not alert["requires_justification"]
        assert "a 3 g single dose appears in some labels for specific indications, verify indication" in alert["effect"]
    else:
        assert found[rule]["level"] == "HIGH_RISK" and found[rule]["requires_justification"]


def test_amoxicillin_adult_daily_maximum_is_3000_mg_and_red():
    assert new_rules(run("amoxicillin", "1000 mg", "TDS", months=400, kg=70)) == set()  # 3000 mg a day
    found = run("amoxicillin", "1000 mg", "QID", months=400, kg=70)  # 4000 mg a day
    assert set(found) == {"DOSE-ABS-DAILY"} and found["DOSE-ABS-DAILY"]["severity"] == "major"
    assert "DOSE-ABS-DAILY" in run("amoxicillin", "1001 mg", "TDS", months=400, kg=70)  # 3003 mg a day


# --- the absolute maximums are checked with no weight; only the per-kg part is skipped --------------------------------


def test_adult_with_no_weight_paracetamol_1200_mg_alerts_and_500_mg_is_a_notice_only():
    over = run("paracetamol", "1200 mg", months=400, kg=None)
    assert set(over) == {"WEIGHT-NEEDED", "DOSE-SINGLE"} and over["DOSE-SINGLE"]["severity"] == "major"
    assert set(run("paracetamol", "500 mg", months=400, kg=None)) == {"WEIGHT-NEEDED"}
    assert set(run("paracetamol", "1000 mg", "QID", months=400, kg=None)) == {"WEIGHT-NEEDED"}  # 4000 mg a day
    assert set(run("paracetamol", "1000 mg", "every 4 hours", months=400, kg=None)) == {"WEIGHT-NEEDED", "DOSE-DAILY"}


def test_adult_with_no_weight_amoxicillin_keeps_the_yellow_and_red_bands_and_the_daily_maximum():
    assert set(run("amoxicillin", "500 mg", "TDS", months=400, kg=None)) == {"WEIGHT-NEEDED"}
    assert set(run("amoxicillin", "1000 mg", "TDS", months=400, kg=None)) == {"WEIGHT-NEEDED"}  # 3000 mg a day
    assert set(run("amoxicillin", "1500 mg", months=400, kg=None)) == {"WEIGHT-NEEDED", "DOSE-ABS-CAUTION"}
    assert set(run("amoxicillin", "3500 mg", months=400, kg=None)) == {"WEIGHT-NEEDED", "DOSE-ABS-SINGLE"}
    assert set(run("amoxicillin", "1001 mg", "TDS", months=400, kg=None)) == {
        "WEIGHT-NEEDED",
        "DOSE-ABS-CAUTION",
        "DOSE-ABS-DAILY",
    }


def test_a_stale_weight_also_keeps_the_absolute_maximums_but_never_the_per_kg_part():
    found = run("amoxicillin", "3500 mg", months=400, kg=70, current=False)
    assert set(found) == {"WEIGHT-STALE", "DOSE-ABS-SINGLE"}
    found = run("paracetamol", "300 mg", months=60, kg=18, current=False)  # over 15 mg/kg, but the old weight is unused
    assert set(found) == {"WEIGHT-STALE"}
    assert set(run("paracetamol", "1200 mg", months=60, kg=18, current=False)) == {"WEIGHT-STALE", "DOSE-SINGLE"}


def test_a_child_with_no_weight_still_gets_the_absolute_maximum_and_never_a_per_kg_alert():
    found = run("azithromycin", "1600 mg", months=60, kg=None)
    assert set(found) == {"WEIGHT-NEEDED", "DOSE-ABS-SINGLE"} and "1500 mg" in found["DOSE-ABS-SINGLE"]["effect"]
    assert set(run("azithromycin", "1000 mg", months=60, kg=None)) == {"WEIGHT-NEEDED"}  # 33 mg/kg at 30 kg: not judged
    assert "DOSE-ABS-SINGLE" in run("cefixime", "500 mg", "OD", months=72, kg=None)
    assert set(run("cefixime", "200 mg", "OD", months=72, kg=None)) == {"WEIGHT-NEEDED"}
    assert set(run("amoxicillin", "80 mg", "BD", months=2, kg=None)) == {"WEIGHT-NEEDED"}  # infants: no adult maximum


@pytest.mark.parametrize(
    ("medicine", "months"),
    [
        ("paracetamol", 60), ("paracetamol", 400), ("amoxicillin", 2), ("amoxicillin", 60), ("amoxicillin", 400),
        ("azithromycin", 60), ("ibuprofen", 12), ("cefixime", 60),
    ],
)  # fmt: skip
def test_no_weight_skips_the_per_kg_check_and_says_weight_needed(medicine, months):
    found = run(medicine, "5000 mg", "QID", months=months, kg=None)
    notice = found["WEIGHT-NEEDED"]
    assert "weight needed for dose check" in notice["title"].lower() and notice["severity"] == "info"
    assert not notice["requires_justification"]
    assert not {r for r in found if r.startswith("DOSE-KG")}  # nothing is checked against a guessed weight
