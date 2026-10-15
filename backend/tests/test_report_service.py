"""Report response helpers (services/report_service.py)."""

from types import SimpleNamespace

import pytest

from services.report_service import (
    dict_field,
    health_status_for_department,
    highest_validation_status,
    list_field,
    preview_text,
    requested_department,
    risk_level_for_status,
)
from services.report_text import DEPARTMENTS, department_slug


def report(status=None, summary=None, formatted=None, extracted=None) -> SimpleNamespace:
    return SimpleNamespace(
        validation_status=status, summary=summary, formatted_text=formatted, extracted_text=extracted
    )


def test_highest_validation_status():
    assert highest_validation_status([report("CAUTION"), report("HIGH_RISK"), report("SAFE")]) == "HIGH_RISK"
    assert highest_validation_status([report("CAUTION"), report(None)]) == "CAUTION"
    assert highest_validation_status([report("SAFE"), report("NOT_VALIDATED")]) == "SAFE"


@pytest.mark.parametrize("reports", [[], [report(None)], [report("NOT_VALIDATED"), report(None)]])
def test_unchecked_reports_are_not_validated_never_safe(reports):
    assert highest_validation_status(reports) == "NOT_VALIDATED"


@pytest.mark.parametrize(
    ("status", "level"),
    [("HIGH_RISK", "High"), ("CAUTION", "Medium"), ("SAFE", "None flagged"), ("NOT_VALIDATED", "Unknown")],
)
def test_risk_level_for_status(status, level):
    assert risk_level_for_status(status) == level


@pytest.mark.parametrize(
    ("status", "label"),
    [
        ("HIGH_RISK", "Needs review"),
        ("CAUTION", "Monitor"),
        ("SAFE", "No rule alerts"),
        ("NOT_VALIDATED", "Not validated"),
    ],
)
def test_department_health_status_never_says_stable(status, label):
    assert health_status_for_department([report(status)], status) == label
    assert health_status_for_department([], status) == "No reports"


def test_preview_prefers_the_summary_and_trims():
    assert preview_text(report(summary="Short  summary", extracted="raw")) == "Short summary"
    assert preview_text(report(extracted="word " * 100), limit=20).endswith("...")
    assert preview_text(report()) is None


def test_json_field_guards():
    assert dict_field({"a": 1}) == {"a": 1}
    assert dict_field(["a"]) == {}
    assert list_field([1]) == [1]
    assert list_field(None) == []


@pytest.mark.parametrize("value", [None, "", "  ", "auto", "Detect"])
def test_no_department_means_detect_it(value):
    assert requested_department(value) is None


@pytest.mark.parametrize(
    ("value", "name", "slug"),
    [
        ("cardiology", "Heart", "heart"),
        ("Renal", "Kidney", "kidney"),
        ("orthopedic", "Ortho", "ortho"),
        ("pathology", "Lab", "lab"),
        ("prescription", "Medicine", "medicine"),
        ("general medicine", "General", "general"),
        ("astrology", "General", "general"),  # unknown names fall back to General
    ],
)
def test_department_aliases_map_to_the_six_departments(value, name, slug):
    assert requested_department(value) == name
    assert department_slug(value) == slug


def test_backend_departments_match_the_frontend_list():
    # lib/departments.ts mirrors this list; the acceptance tests check the API, this checks the source.
    assert {d["slug"] for d in DEPARTMENTS} == {"heart", "kidney", "ortho", "general", "medicine", "lab"}
