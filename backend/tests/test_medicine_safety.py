"""The patient's medicine-safety check (services/medicine_safety.py) on the MSCIE engine, AGENTS.md 6.1, 6.2."""

from types import SimpleNamespace

import pytest

from services.medicine_safety import SAFETY_SEVERITY, check_medicine_safety


def history(*names: str, side_effects: str | None = None) -> list[SimpleNamespace]:
    return [SimpleNamespace(medicine_name=name, side_effects=side_effects) for name in names]


def check(name: str, dosage: str | None = None, allergies: str | None = None, saved=()):
    return check_medicine_safety(name, dosage, allergies, list(saved))


def test_no_matching_rule_is_no_data_never_safe():
    status, reason, warnings = check("Paracetamol")
    assert status == "No data"
    assert "does not mean the medicine is safe" in reason
    assert len(warnings) == 1


@pytest.mark.parametrize(
    ("name", "dosage", "allergies", "saved"),
    [
        ("Paracetamol", None, None, ()),
        ("Amoxicillin", "500 mg", "none", history("Metformin")),
        ("Aspirin", None, None, history("Ibuprofen")),
        ("Penicillin", None, "penicillin", ()),
    ],
)
def test_status_is_never_safe(name, dosage, allergies, saved):
    status, _, _ = check(name, dosage, allergies, saved)
    assert status in SAFETY_SEVERITY
    assert status.lower() != "safe"


def test_medicine_in_allergy_text_is_high_risk():
    status, _, warnings = check("Penicillin", allergies="Penicillin - rash")
    assert status == "High Risk"
    assert any("allergy text" in w for w in warnings)


def test_duplicate_of_saved_medicine_is_caution():
    status, _, warnings = check("Metformin", saved=history("metformin"))
    assert status == "Caution"
    assert any("Duplicate" in w for w in warnings)


def test_names_are_compared_case_and_space_insensitively():
    status, _, _ = check("  METFORMIN ", saved=history("metformin"))
    assert status == "Caution"


def test_previous_reaction_to_the_medicine_is_high_risk():
    saved = history("Ibuprofen", side_effects="ibuprofen caused swelling")
    status, _, warnings = check("Ibuprofen", saved=saved)
    assert status == "High Risk"
    assert any("reaction" in w for w in warnings)


@pytest.mark.parametrize(
    ("requested", "saved_name", "expected"),
    [
        ("Warfarin", "Aspirin", "High Risk"),
        ("Aspirin", "Warfarin", "High Risk"),
        ("Warfarin", "Ibuprofen", "High Risk"),
        ("Sildenafil", "Glyceryl trinitrate", "High Risk"),  # contraindicated (ONC list)
        # Two NSAIDs: a major duplicate in the shared MSCIE rules (it was "Caution" in the old, smaller list).
        ("Aspirin", "Ibuprofen", "High Risk"),
        ("Insulin", "Glimepiride", "Caution"),
        # Curated rule: moderate; DDInter rates it major (as the FDA label advises avoiding it): the higher wins.
        ("Clopidogrel", "Omeprazole", "High Risk"),
        ("Lisinopril", "Spironolactone", "High Risk"),
    ],
)
def test_listed_interactions(requested, saved_name, expected):
    status, _, _ = check(requested, saved=history(saved_name))
    assert status == expected


def test_high_risk_is_not_lowered_by_a_later_caution():
    # Aspirin with warfarin (two high-risk rules: NSAID and antiplatelet), with ibuprofen (a major NSAID
    # duplicate), DDInter's major rating of aspirin with ibuprofen (higher than the curated rule), and
    # the moderate antiplatelet + NSAID caution, listed last.
    status, _, warnings = check("Aspirin", saved=history("Warfarin", "Ibuprofen"))
    assert status == "High Risk"
    assert len(warnings) == 5
    assert "time the doses apart" in warnings[-1]


@pytest.mark.parametrize("dosage", ["double dose", "take EXTRA at night", "repeat if needed"])
def test_unclear_dosage_wording_is_caution(dosage):
    status, _, _ = check("Paracetamol", dosage=dosage)
    assert status == "Caution"


def test_reason_joins_the_warnings():
    status, reason, warnings = check("Paracetamol", dosage="double", saved=history("Metformin"))
    assert status == "Caution"
    assert reason == " ".join(warnings)
