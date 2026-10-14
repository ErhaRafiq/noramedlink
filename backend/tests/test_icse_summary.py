"""FE-2 and FE-4: the clinical summary's content, built by fixed rules (synthetic data only)."""

import json
from datetime import date

from services.icse.entities import extract_entities
from services.icse.flags import printed_date
from services.icse.summary import SECTION_LIMIT, build_content, render_text
from services.icse.versions import describe_change

TODAY = date(2026, 10, 15)


def report(report_id, text, title=None):
    entities = extract_entities(text)
    day = printed_date(entities)
    return {
        "report_id": report_id,
        "title": title or f"Report {report_id}",
        "kind": "report",
        "date": day,
        "date_source": "printed in report" if day else None,
        "entities": entities,
    }


SOURCES = [
    report(1, "Collected: 10-Jan-2026\nCreatinine 1.6 mg/dL\nHemoglobin 13.2 g/dL"),
    report(
        2,
        "Date: 05/02/2026\nKnown case of DM and HTN. No history of asthma. Family history of IHD.\n"
        "Allergies: penicillin\nTab Glucophage 500 mg BD\nTab Warfarin 5 mg OD\nAspirin stopped.",
    ),
    report(3, "Collected: 01-Mar-2026\nCreatinine 2.1 mg/dL\nHemoglobin 10.9 g/dL\nPotassium [?] mmol/L"),
]
MEDS = [
    {"name": "Amlodipine", "dosage": "5 mg", "end_date": None, "list": "medication schedule"},
    {"name": "Old antibiotic", "dosage": "250 mg", "end_date": "2026-01-01", "list": "medication schedule"},
]


def content():
    return build_content(SOURCES, MEDS, [], TODAY)


def test_abnormal_results_include_result_persistent_and_trend_flags_with_sources():
    abnormal = content()["abnormal_results"]
    kinds = {(f["subject"], f["kind"]) for f in abnormal}
    assert {("Creatinine", "result"), ("Creatinine", "persistent"), ("Creatinine", "trend")} <= kinds
    assert ("Hemoglobin", "trend") in kinds
    for flag in abnormal:
        assert flag["sources"] and all(s["title"] and s["kind"] == "report" for s in flag["sources"])


def test_conditions_are_mentioned_not_diagnosed_and_family_history_is_separate():
    result = content()
    names = [c["name"] for c in result["conditions"]]
    assert names == ["diabetes mellitus", "hypertension"]  # asthma was negated
    assert all(c["certainty"] == "mentioned in report" for c in result["conditions"])
    assert [f["name"] for f in result["family_history"]] == ["ischaemic heart disease"]
    assert result["conditions"][0]["sources"] == [
        {
            "report_id": 2,
            "title": "Report 2",
            "date": "2026-02-05",
            "date_source": "printed in report",
            "kind": "report",
        }
    ]


def test_medicines_from_the_app_and_from_the_latest_report_list():
    medicines = content()["medications"]
    assert [m["name"] for m in medicines["from_app"]] == ["Amlodipine"]  # the ended one is left out
    assert [m["medicine"] for m in medicines["from_reports"]] == ["metformin", "warfarin"]
    assert medicines["stopped_in_reports"] == ["aspirin"]


def test_allergies_and_conflicting_reports_are_both_shown():
    sources = [*SOURCES, report(4, "Allergies: NKDA")]
    allergies = build_content(sources, [], [], TODAY)["allergies"]
    assert allergies["status"] == "listed"
    assert [a["name"] for a in allergies["items"]] == ["penicillin"]
    assert [s["report_id"] for s in allergies["no_known_allergies_in"]] == [4]


def test_values_to_check_and_missing_data_are_honest():
    result = content()
    assert [c["subject"] for c in result["check_original"]] == ["Potassium"]
    assert "No vitals entered in the app." in result["missing_data"]
    assert any("could not be checked" in m for m in result["missing_data"])


def test_no_data_gives_an_honest_empty_summary():
    result = build_content([], [], [{"report_id": 9, "title": "scan", "kind": "report"}], TODAY)
    assert result["abnormal_results"] == [] and result["allergies"]["status"] == "not_recorded"
    assert "1 report(s) could not be read; their content is not in this summary." in result["missing_data"]
    assert "No allergy information in any report." in result["missing_data"]
    assert result["key_findings"]["text"].startswith("No rule alerts")


def test_key_findings_only_use_counts_from_the_content():
    text = content()["key_findings"]["text"]
    assert "long-term conditions mentioned: diabetes mellitus, hypertension" in text
    assert text.endswith("For physician review.")
    assert content()["key_findings"]["source"] == "rule_based"


def test_text_and_content_never_say_safe_or_normal():
    result = content()
    text = render_text(result).lower()
    assert "abnormal results" in text and "missing data" in text
    blob = json.dumps(result).lower() + text
    assert " safe" not in blob and "normal" not in blob.replace("abnormal", "")


def test_model_suggestions_never_appear_as_findings():
    sources = [report(1, "Has sarcoidosis.")]
    sources[0]["entities"].append(
        {"type": "condition", "name": "sarcoidosis", "negated": False, "method": "biobert", "chronic": True}
    )
    assert build_content(sources, [], [], TODAY)["conditions"] == []


def test_section_limit_is_recorded_for_the_page():
    assert content()["section_limit"] == SECTION_LIMIT == 5


def test_describe_change():
    base = {"versions": {"summary": 1}, "reports": {"1": "a", "2": "b"}, "vitals": "v", "medications": "m"}
    assert describe_change(None, base) == "First summary for this patient."
    after = {**base, "reports": {"1": "a", "2": "c", "3": "d"}, "medications": "m2"}
    assert describe_change(base, after) == "1 report(s) added; 1 report(s) edited or re-read; medicines changed."
    assert describe_change(base, {**base, "reports": {"1": "a"}}) == "1 report(s) deleted."
    assert describe_change(base, {**base, "versions": {"summary": 2}}) == "summary rules updated."
