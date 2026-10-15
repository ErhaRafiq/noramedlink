"""MSCIE (Module 4) engine: explicit safety cases for every rule type, alternatives and ranking."""

import json

import pytest

from services.mscie.alternatives import alternatives_for, weights
from services.mscie.doses import dose_mg, times_per_day
from services.mscie.engine import PatientContext, Proposed, check, resolve
from services.mscie.names import search
from services.mscie.prescribing import run_check


def ctx(medicines=(), conditions=(), allergies=(), labs=None, previous=()):
    return PatientContext(
        medicines=[resolve(m, "latest report's medicine list", {"date": "2026-03-01"}) for m in medicines],
        conditions=[{"name": c, "source": "report 1, 2026-03-01"} for c in conditions],
        allergies=[
            {
                "name": a,
                "generics": list(resolve(a).generics),
                "classes": [a] if not resolve(a).known else list(resolve(a).classes),
                "source": "report 1",
            }
            for a in allergies
        ],
        labs={k: {"value": v, "unit": "", "date": "2026-03-01", "source": "report 1"} for k, v in (labs or {}).items()},
        previous=list(previous),
    )


def alerts_for(context, medicine, dose=None, frequency=None):
    [result] = check(context, [Proposed(medicine, dose, frequency)])
    return result["alerts"]


def kinds(alerts):
    return {(a["kind"], a["severity"]) for a in alerts}


# --- allergies ------------------------------------------------------------------------------------


def test_allergy_to_the_medicine_itself_is_contraindicated():
    alerts = alerts_for(ctx(allergies=["aspirin"]), "Disprin")
    assert ("allergy", "contraindicated") in kinds(alerts)


@pytest.mark.parametrize(
    ("allergy", "medicine", "severity"),
    [
        ("penicillin", "Augmentin", "contraindicated"),  # same class
        ("penicillin", "Cefixime", "moderate"),  # cross-reactivity, uncommon
        ("NSAID", "Aspirin", "contraindicated"),
        ("sulfonamide", "Furosemide", "minor"),  # non-antibiotic sulfonamide: unlikely
    ],
)
def test_allergy_classes_and_cross_reactivity(allergy, medicine, severity):
    assert ("allergy", severity) in kinds(alerts_for(ctx(allergies=[allergy]), medicine))


# --- interactions and duplicates ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "proposed", "severity"),
    [
        ("Glyceryl trinitrate", "Sildenafil", "contraindicated"),
        ("Warfarin", "Brufen", "major"),
        ("Warfarin", "Flagyl", "major"),
        ("Lisinopril", "Spironolactone", "major"),
        ("Clopidogrel", "Omeprazole", "major"),  # DDInter rates it above the curated moderate rule
        ("Levothyroxine", "Calcium carbonate", "moderate"),
    ],
)
def test_drug_drug_interactions(current, proposed, severity):
    alerts = alerts_for(ctx(medicines=[current]), proposed)
    hit = [a for a in alerts if a["kind"] == "interaction"]
    assert hit and hit[0]["severity"] == severity
    assert hit[0]["evidence"][0].startswith("Also taking:") and hit[0]["sources"]


def test_interactions_between_two_new_medicines_are_found_too():
    results = check(ctx(), [Proposed("Warfarin"), Proposed("Ibuprofen")])
    assert all(any(a["kind"] == "interaction" for a in r["alerts"]) for r in results)


def test_duplicates_same_medicine_and_same_class():
    assert ("duplicate", "moderate") in kinds(alerts_for(ctx(medicines=["Glucophage"]), "Metformin"))
    assert ("duplicate", "moderate") in kinds(alerts_for(ctx(medicines=["Atorvastatin"]), "Rosuvastatin"))
    assert ("duplicate", "major") in kinds(alerts_for(ctx(medicines=["Ibuprofen"]), "Diclofenac"))


# --- contraindications: conditions and lab values -------------------------------------------------


@pytest.mark.parametrize(
    ("egfr", "expected"),
    [(25, "contraindicated"), (40, "moderate"), (60, None)],
)
def test_metformin_by_kidney_function(egfr, expected):
    alerts = [a for a in alerts_for(ctx(labs={"eGFR": egfr}), "Metformin") if a["kind"] == "contraindication"]
    assert [a["severity"] for a in alerts] == ([expected] if expected else [])
    if expected:
        assert f"Latest eGFR: {egfr}" in alerts[0]["evidence"][0]


def test_nsaid_with_kidney_disease_but_low_dose_aspirin_is_excluded():
    assert ("contraindication", "major") in kinds(alerts_for(ctx(conditions=["chronic kidney disease"]), "Ibuprofen"))
    aspirin = [
        a for a in alerts_for(ctx(conditions=["chronic kidney disease"]), "Aspirin") if a["kind"] == "contraindication"
    ]
    assert aspirin == []


def test_spironolactone_with_high_potassium_is_contraindicated():
    assert ("contraindication", "contraindicated") in kinds(alerts_for(ctx(labs={"Potassium": 5.7}), "Spironolactone"))


def test_beta_blocker_with_asthma():
    assert ("contraindication", "moderate") in kinds(alerts_for(ctx(conditions=["asthma"]), "Concor"))


# --- doses ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dose", "frequency", "expected"),
    [
        ("1 g", "QID", set()),  # 4 g a day: the maximum, not over it
        ("1 g", "every 4 hours", {"DOSE-DAILY"}),  # 6 g a day
        ("1500 mg", "OD", {"DOSE-SINGLE"}),
        ("500 mg", "PRN", set()),  # as needed: only the single dose is checked
    ],
)
def test_paracetamol_doses(dose, frequency, expected):
    alerts = alerts_for(ctx(), "Panadol", dose, frequency)
    assert {a["rule_id"] for a in alerts if a["kind"] == "dose"} == expected


@pytest.mark.parametrize(
    ("text", "mg"), [("500 mg", 500), ("1 g", 1000), ("0.5g", 500), ("50 mcg", 0.05), ("10 ml", None), ("", None)]
)
def test_dose_parsing(text, mg):
    assert dose_mg(text) == mg


@pytest.mark.parametrize(
    ("text", "times"), [("BD", 2), ("tds", 3), ("1+0+1", 2), ("every 8 hours", 3), ("PRN", None), ("weekly", None)]
)
def test_frequency_parsing(text, times):
    assert times_per_day(text) == times


# --- history, unknown medicines, wording ----------------------------------------------------------


def test_a_previous_reaction_is_major():
    context = ctx(
        previous=[{"generic": "ibuprofen", "problem": True, "note": "side effect recorded: rash and swelling"}]
    )
    assert ("previous_response", "major") in kinds(alerts_for(context, "Ibuprofen"))


def test_an_unknown_medicine_is_no_data_never_safe():
    [alert] = alerts_for(ctx(), "Rifaximin")
    assert alert["kind"] == "no_data" and "does not mean safe" in alert["management"]


def test_high_alert_medicines_are_marked():
    assert ("high_alert", "info") in kinds(alerts_for(ctx(), "Warfarin"))


def test_no_alert_ever_calls_a_medicine_safe():
    results = check(
        ctx(medicines=["Warfarin", "Lisinopril"], conditions=["asthma"], allergies=["penicillin"], labs={"eGFR": 25}),
        [Proposed(m) for m in ["Brufen", "Augmentin", "Metformin", "Paracetamol", "Rifaximin", "Concor"]],
    )
    text = json.dumps(results).lower().replace("does not mean safe", "")
    assert " safe" not in text


# --- alternatives and ranking ---------------------------------------------------------------------


def test_contraindicated_alternatives_are_never_suggested():
    context = ctx(allergies=["penicillin"])
    names = [c["medicine"] for c in alternatives_for(Proposed("Ciprofloxacin"), resolve("Ciprofloxacin"), [], context)]
    assert "amoxicillin" not in names and "azithromycin" in names


def test_ranking_uses_safety_kidney_fit_history_and_simplicity_transparently():
    context = ctx(
        labs={"eGFR": 40}, previous=[{"generic": "sitagliptin", "problem": True, "note": "stopped: side effect"}]
    )
    ranked = alternatives_for(Proposed("Glimepiride"), resolve("Glimepiride"), [], context)
    assert [c["medicine"] for c in ranked] == ["empagliflozin", "metformin", "sitagliptin"]
    for candidate in ranked:
        assert candidate["score"] == pytest.approx(sum(b["contribution"] for b in candidate["breakdown"]), abs=1e-3)
        assert {b["factor"] for b in candidate["breakdown"]} == set(weights())
    assert [c["rank"] for c in ranked] == [1, 2, 3]


def test_clopidogrel_with_omeprazole_suggests_pantoprazole():
    result = run_check(ctx(medicines=["Clopidogrel"]), [Proposed("Omeprazole", "20 mg", "OD")])
    [item] = result["items"]
    assert item["alternatives"][0]["medicine"] == "pantoprazole"


def test_only_high_risk_alerts_need_a_justification():
    result = run_check(ctx(medicines=["Warfarin"]), [Proposed("Brufen"), Proposed("Omeprazole")])
    assert result["requires_justification"]
    assert all(a["severity"] in {"contraindicated", "major"} for a in result["requires_justification"])


def test_the_weights_sum_to_one():
    assert sum(weights().values()) == pytest.approx(1.0)


# --- medicine search ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "generic"), [("glucophag", "metformin"), ("amoxicilin", "amoxicillin"), ("brufen", "ibuprofen")]
)
def test_fuzzy_search_finds_misspelled_medicines(query, generic):
    assert search(query)[0]["generic"] == generic


def test_search_finds_nothing_for_nonsense():
    assert search("xyzq") == []
