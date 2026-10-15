"""DDInter pairs behind the curated rules (services/mscie/ddinter.py): gaps filled, the higher
rating never hidden, unknown levels shown as caution, DDInter-only drugs checked for interactions."""

import pandas as pd

from services.knowledge.tables import DATA, table
from services.mscie import ddinter
from services.mscie.engine import PatientContext, Proposed, check, resolve
from services.mscie.names import search


def interactions(current: list[str], proposed: str) -> list[dict]:
    result = check(PatientContext(medicines=[resolve(m, "test") for m in current]), [Proposed(proposed)])[0]
    return [a for a in result["alerts"] if a["kind"] == "interaction"]


def test_the_pair_table_is_clean():
    frame = pd.read_csv(DATA / "ddinter_interactions.csv.gz", dtype=str, keep_default_na=False)
    assert len(frame) > 150_000
    assert set(frame["level"]) == {"major", "moderate", "minor", "unknown"}
    assert (frame["drug_a"] < frame["drug_b"]).all()
    assert not frame.duplicated(["drug_a", "drug_b"]).any()


def test_every_name_mapping_points_at_real_names():
    mapping = table("ddinter_names")
    assert set(mapping["generic"]) <= set(table("medicines")["generic"])
    assert set(mapping["ddinter"]) <= ddinter.drug_names()


def test_international_names_and_combinations_are_mapped():
    assert ddinter.names_for(("aspirin",)) == ["acetylsalicylic acid"]
    assert ddinter.names_for(("paracetamol",)) == ["acetaminophen"]
    assert ddinter.names_for(("amoxicillin and clavulanic acid",)) == ["amoxicillin", "clavulanic acid"]


def test_a_pair_the_curated_rules_lack_is_found_in_ddinter():
    hits = interactions(["Amlodipine"], "Simvastatin")  # no curated rule; DDInter: major
    assert [(a["rule_id"], a["severity"]) for a in hits] == [("DDINTER", "major")]
    assert hits[0]["sources"][0]["label"] == "DDINTER" and "full drug reference" in hits[0]["management"]


def test_a_curated_rule_is_kept_and_a_higher_ddinter_rating_is_added():
    hits = interactions(["Warfarin"], "Ciprofloxacin")  # curated: moderate; DDInter: major
    assert {(a["rule_id"].startswith("DDI-"), a["severity"]) for a in hits} == {(True, "moderate"), (False, "major")}


def test_a_curated_rule_at_least_as_severe_stands_alone():
    hits = interactions(["Warfarin"], "Ibuprofen")  # curated major class rule; DDInter major too
    assert hits and all(a["rule_id"] != "DDINTER" for a in hits)


def test_an_unknown_level_is_shown_as_moderate_never_as_no_interaction():
    unknown = next(key for key, level in ddinter._pairs().items() if level == "unknown")
    a, b = key_names = unknown.split("|")
    assert ddinter.interaction((a,), (b,))[0] == "unknown"
    assert ddinter.SEVERITY["unknown"] == "moderate"
    assert "does not grade" in ddinter.effect("unknown", *key_names)


def test_a_drug_known_only_to_ddinter_is_checked_for_interactions_and_says_what_is_missing():
    med = resolve("Dolutegravir")
    assert med.known and med.interactions_only and med.classes == ()
    alerts = check(PatientContext(medicines=[resolve("Iron", "test")]), [Proposed("Dolutegravir")])[0]["alerts"]
    assert any(a["rule_id"] == "DDINTER" and a["severity"] == "major" for a in alerts)
    assert any(a["rule_id"] == "PARTIAL-DATA" and "No alert does not mean safe" in a["management"] for a in alerts)


def test_an_unknown_name_still_gets_no_data():
    result = check(PatientContext(), [Proposed("Zzqmedicine")])[0]
    assert [a["kind"] for a in result["alerts"]] == ["no_data"]


def test_search_finds_drugs_known_only_to_ddinter():
    assert any(r["generic"] == "dolutegravir" for r in search("dolutegravir"))
    assert search("panadol")[0]["generic"] == "paracetamol"  # curated brands still come first
