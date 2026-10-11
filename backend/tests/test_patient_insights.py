"""Cleaning of LLM output and the rule-based fallbacks (services/patient_insights.py)."""

from types import SimpleNamespace

import pytest

from services.patient_insights import (
    TIP_CATEGORIES,
    annotate_fallback,
    build_health_tips,
    build_risk_predictions,
    clean_ai_text,
    normalize_risk_level,
    validate_ai_health_tips,
    validate_ai_risk_predictions,
)


def document(text: str) -> SimpleNamespace:
    return SimpleNamespace(title="Report", category="General", notes=None, ocr_cleaned_text=text, ai_summary=None)


def test_clean_ai_text():
    assert clean_ai_text("  hello  ", "fallback") == "hello"
    assert clean_ai_text("", "fallback") == "fallback"
    assert clean_ai_text(None, "fallback") == "fallback"
    assert clean_ai_text(123, "fallback") == "fallback"
    assert clean_ai_text("x" * 50, "fallback", max_length=10) == "x" * 10


@pytest.mark.parametrize(
    ("raw", "expected"), [("low", "Low"), (" HIGH ", "High"), ("critical", "Medium"), (None, "Medium")]
)
def test_normalize_risk_level(raw, expected):
    assert normalize_risk_level(raw) == expected


@pytest.mark.parametrize("data", [None, "text", {"risk_title": "x"}, 42])
def test_risk_output_that_is_not_a_list_is_dropped(data):
    assert validate_ai_risk_predictions(data) == []


def test_risk_output_is_cleaned_and_capped():
    data = [{"risk_title": " Sugar ", "risk_level": "high", "reason": "r", "recommendation": "c"}, "junk", {}, {}, {}]
    cleaned = validate_ai_risk_predictions(data)
    assert len(cleaned) == 2  # only the first three entries are read, and the non-dict among them is skipped
    assert cleaned[0] == {"risk_title": "Sugar", "risk_level": "High", "reason": "r", "recommendation": "c"}
    assert all(set(item) == {"risk_title", "risk_level", "reason", "recommendation"} for item in cleaned)
    assert all(item["risk_title"] for item in cleaned)


def test_tip_categories_are_restricted():
    cleaned = validate_ai_health_tips(
        [{"category": "Miracle cures", "tip_text": "t"}, {"category": "Food to avoid", "tip_text": "u"}]
    )
    assert [tip["category"] for tip in cleaned] == [TIP_CATEGORIES[0], "Food to avoid"]
    assert validate_ai_health_tips("not a list") == []


def test_annotate_fallback():
    assert annotate_fallback("Text.", None) == "Text."
    assert annotate_fallback("Text.", "No key.").startswith("Text. Clinical AI was unavailable: No key.")


def test_rule_based_tips_cover_all_four_categories():
    tips = build_health_tips([document("HbA1c 8.1 and glucose high")], [])
    assert [tip["category"] for tip in tips] == TIP_CATEGORIES
    assert "sugary" in tips[1]["tip_text"]


def test_rule_based_risks_follow_the_report_text():
    predictions = build_risk_predictions(None, [document("creatinine raised, eGFR low")], [])
    assert predictions[0]["risk_title"] == "Possible kidney function follow-up risk"
    assert len(build_risk_predictions(None, [document("glucose cholesterol creatinine rash")], [])) == 3
