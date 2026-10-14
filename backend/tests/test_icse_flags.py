"""FE-3: deterministic clinical-summary flags (synthetic text only)."""

import json

import pytest

from services.icse.entities import extract_entities
from services.icse.flags import build_flags, printed_date


def report(report_id, text, day=None):
    entities = extract_entities(text)
    return {"report_id": report_id, "date": day if day is not None else printed_date(entities), "entities": entities}


def flags_of(result, kind=None, subject=None):
    return [
        f
        for f in result["flags"]
        if (kind is None or f["kind"] == kind) and (subject is None or f["subject"] == subject)
    ]


# --- result flags ---------------------------------------------------------------------------------


def test_random_sugar_230_with_a_normal_fasting_value_is_flagged():
    result = build_flags([report(1, "Fasting Blood Sugar 92 mg/dL\nRandom Blood Sugar 230 mg/dL")])
    [flag] = flags_of(result, "result")
    assert (flag["subject"], flag["code"], flag["severity"]) == ("Random Blood Sugar", "RESULT_HIGH", "CAUTION")
    assert flag["sources"][0]["printed"] == "230 mg/dL"


def test_every_reading_of_a_repeated_test_is_checked_and_the_most_severe_counts():
    result = build_flags([report(1, "Hemoglobin 13.5 g/dL\nHemoglobin 10.9 g/dL\nRepeat Hemoglobin 6.8 g/dL")])
    [flag] = flags_of(result, "result", "Hemoglobin")
    assert flag["severity"] == "HIGH_RISK"
    assert "6.8" in flag["message"]
    assert [s["printed"] for s in flag["sources"]] == ["10.9 g/dL", "6.8 g/dL"]


def test_units_are_converted_before_comparing():
    result = build_flags([report(1, "Random Blood Sugar 13.0 mmol/L\nCreatinine 88 umol/L\nHemoglobin 128 g/L")])
    [flag] = flags_of(result, "result")
    assert flag["subject"] == "Random Blood Sugar"  # 234 mg/dL; creatinine 1.0 mg/dL and Hb 12.8 g/dL are in range
    assert flag["sources"][0]["value"] == 234.0


def test_only_the_most_recent_report_with_a_test_gives_its_result_flag():
    result = build_flags(
        [report(1, "Potassium 6.0 mmol/L", "2026-01-01"), report(2, "Potassium 4.2 mmol/L", "2026-02-01")]
    )
    assert flags_of(result, "result") == []


@pytest.mark.parametrize(
    ("text", "severity"),
    [("BP 150/95 mmHg", "CAUTION"), ("BP 120/80, repeat BP 190/110 mmHg", "HIGH_RISK"), ("BP 128/82", None)],
)
def test_blood_pressure(text, severity):
    flags = flags_of(build_flags([report(1, text)]), "result", "Blood Pressure")
    assert [f["severity"] for f in flags] == ([severity] if severity else [])


# --- values that are never flagged ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Creatinine [?] mg/dL 0.6 - 1.3", "could not be read"),
        ("Hemoglobin 9.1 %", "unit"),  # not a hemoglobin unit
        ("Random Blood Sugar 30", "no unit"),  # 30 mg/dL or 30 mmol/L: cannot tell
        ("Creatinine 20", "no unit"),  # 20 mg/dL or 20 umol/L: cannot tell
        ("Hemoglobin 95 g/dL", "possible"),  # a misread number
    ],
)
def test_unusable_values_are_shown_to_check_and_never_flagged(text, reason):
    result = build_flags([report(1, text)])
    assert result["flags"] == []
    [check] = result["check_original"]
    assert reason in check["reason"]
    assert "check against the original report" in check["message"]


def test_low_confidence_value_is_not_flagged():
    entities = extract_entities("Potassium 6.9 mmol/L")
    entities[0]["confidence"] = 0.62
    result = build_flags([{"report_id": 1, "date": None, "entities": entities}])
    assert result["flags"] == []
    assert "low confidence" in result["check_original"][0]["reason"]


def test_a_value_without_a_unit_is_used_only_where_it_cannot_be_another_unit():
    [flag] = flags_of(build_flags([report(1, "FBS 132")]), "result")
    assert flag["sources"][0]["unit_assumed"] is True


def test_model_suggestions_never_create_or_change_a_flag():
    entities = extract_entities("Hemoglobin 13.5 g/dL")
    entities += [
        {"type": "test_result", "name": "Hemoglobin", "value": "5.0", "unit": "g/dL", "method": "biobert",
         "certainty": "model suggestion", "confidence": 0.4},
        {"type": "condition", "name": "hypertension", "negated": None, "chronic": True, "method": "biobert",
         "certainty": "model suggestion", "confidence": 0.45},
    ]  # fmt: skip
    result = build_flags([{"report_id": 1, "date": None, "entities": entities}])
    assert result["flags"] == [] and result["check_original"] == []


# --- persistent and trend -------------------------------------------------------------------------


def test_one_high_creatinine_then_normal_is_not_persistent():
    result = build_flags(
        [
            report(1, "Collected: 10-Jan-2026\nCreatinine 1.8 mg/dL"),
            report(2, "Collected: 10-Feb-2026\nCreatinine 1.0 mg/dL"),
        ]
    )
    assert flags_of(result, "persistent") == []
    assert flags_of(result, "result") == []


def test_two_dated_high_readings_in_a_row_are_persistent_with_their_dates():
    result = build_flags(
        [
            report(1, "Collected: 10-Jan-2026\nCreatinine 1.0 mg/dL"),
            report(2, "Collected: 10-Feb-2026\nCreatinine 1.6 mg/dL"),
            report(3, "Collected: 12-Mar-2026\nCreatinine 159 umol/L"),  # 1.8 mg/dL
        ]
    )
    [flag] = flags_of(result, "persistent")
    assert flag["code"] == "PERSISTENT_HIGH"
    assert [(s["report_id"], s["date"]) for s in flag["sources"]] == [(2, "2026-02-10"), (3, "2026-03-12")]


def test_high_then_high_then_normal_is_not_persistent():
    days = ["2026-01-01", "2026-02-01", "2026-03-01"]
    values = ["7.5", "7.9", "5.4"]
    reports = [report(i, f"HbA1c {v} %", d) for i, (v, d) in enumerate(zip(values, days, strict=True))]
    assert flags_of(build_flags(reports), "persistent") == []


def test_persistent_and_trend_need_printed_dates():
    result = build_flags([report(1, "Creatinine 1.6 mg/dL"), report(2, "Creatinine 2.4 mg/dL")])
    assert flags_of(result, "persistent") == [] and flags_of(result, "trend") == []
    assert any("no printed date" in note for note in result["notes"])


def test_creatinine_rise_is_a_trend_after_converting_units():
    result = build_flags(
        [
            report(1, "Collected: 01-Jan-2026\nCreatinine 70 umol/L"),  # 0.79 mg/dL
            report(2, "Collected: 01-Mar-2026\nCreatinine 1.2 mg/dL"),
        ]
    )
    [flag] = flags_of(result, "trend")
    assert flag["code"] == "TREND_RISING"
    assert "KDIGO" in flag["rule"]
    assert [s["date"] for s in flag["sources"]] == ["2026-01-01", "2026-03-01"]


@pytest.mark.parametrize(
    ("name", "first", "second", "expected"),
    [
        ("eGFR", "eGFR 80 mL/min/1.73m2", "eGFR 58 mL/min/1.73m2", "TREND_FALLING"),  # -27.5%
        ("eGFR", "eGFR 80 mL/min/1.73m2", "eGFR 70 mL/min/1.73m2", None),  # -12.5%
        ("Hemoglobin", "Hemoglobin 13.0 g/dL", "Hemoglobin 10.8 g/dL", "TREND_FALLING"),
        ("Hemoglobin", "Hemoglobin 13.0 g/dL", "Hemoglobin 14.5 g/dL", None),
        ("Creatinine", "Creatinine 1.0 mg/dL", "Creatinine 0.7 mg/dL", None),  # a fall is not worsening
    ],
)
def test_trend_thresholds(name, first, second, expected):
    result = build_flags([report(1, first, "2026-01-01"), report(2, second, "2026-04-01")])
    assert [f["code"] for f in flags_of(result, "trend", name)] == ([expected] if expected else [])


def test_blood_pressure_persistent():
    result = build_flags([report(1, "BP 150/95 mmHg", "2026-01-01"), report(2, "BP 146/92 mmHg", "2026-02-01")])
    assert [f["code"] for f in flags_of(result, "persistent")] == ["PERSISTENT_HIGH"]


# --- conditions and medicines ---------------------------------------------------------------------


def test_family_history_of_diabetes_gives_no_chronic_condition_flag():
    result = build_flags([report(1, "Family history of diabetes. Mother has HTN.")])
    assert flags_of(result, "chronic_condition") == []


def test_chronic_flags_only_from_mentioned_not_negated_long_term_conditions():
    result = build_flags([report(1, "Known case of DM. No history of asthma. Treated for pneumonia.", "2026-01-05")])
    [flag] = flags_of(result, "chronic_condition")
    assert flag["subject"] == "diabetes mellitus"
    assert "not a confirmed diagnosis" in flag["message"]
    assert flag["sources"] == [{"report_id": 1, "date": "2026-01-05", "text": "DM"}]


def test_ongoing_treatment_comes_from_the_most_recent_medicine_list():
    result = build_flags(
        [
            report(1, "Tab Glucophage 500 mg BD\nTab Lipitor 20 mg at night"),
            report(2, "Hemoglobin 13.0 g/dL"),  # no medicines: not a medicine list
            report(3, "Tab Norvasc 5 mg OD\nWarfarin 5 mg OD\nLipitor stopped last month."),
        ]
    )
    [treatment] = flags_of(result, "ongoing_treatment")
    assert [s["medicine"] for s in treatment["sources"]] == ["amlodipine", "warfarin"]
    assert {s["report_id"] for s in treatment["sources"]} == {3}
    assert treatment["stopped"] == ["atorvastatin"]
    [high_alert] = flags_of(result, "high_alert_medicine")
    assert high_alert["subject"] == "warfarin"


def test_only_stopped_medicines_in_the_latest_list_gives_a_note_not_a_flag():
    result = build_flags([report(1, "Tab Glucophage 500 mg BD"), report(2, "Glucophage stopped.")])
    assert flags_of(result, "ongoing_treatment") == []
    assert any("no medicine marked as ongoing" in note for note in result["notes"])


def test_every_flag_has_a_reason_a_source_and_no_reassuring_words():
    result = build_flags(
        [
            report(1, "Collected: 01-Jan-2026\nCreatinine 1.6 mg/dL\nK/C/O HTN\nTab Warfarin 5 mg OD\nBP 150/95 mmHg"),
            report(2, "Collected: 01-Mar-2026\nCreatinine 2.1 mg/dL\nRandom Blood Sugar 320 mg/dL"),
        ]
    )
    assert {f["kind"] for f in result["flags"]} >= {
        "result",
        "persistent",
        "trend",
        "chronic_condition",
        "ongoing_treatment",
    }
    for flag in result["flags"]:
        assert flag["reason"] and flag["sources"] and flag["rule"]
        assert all("report_id" in s for s in flag["sources"])
    text = json.dumps(result).lower()
    assert " safe" not in text and "normal" not in text
    assert result["flags"][0]["severity"] == "HIGH_RISK"  # the most severe first


def test_no_reports():
    assert build_flags([]) == {"flags": [], "check_original": [], "notes": []}
