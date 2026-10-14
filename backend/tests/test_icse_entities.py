"""FE-1: the shared knowledge base and the typed entity extractor (synthetic text only)."""

import pytest

from services import knowledge
from services.icse.entities import MENTIONED, SUGGESTION, extract_entities


def of_type(entities, kind):
    return [e for e in entities if e["type"] == kind]


def by_name(entities, kind):
    return {e["name"]: e for e in of_type(entities, kind)}


# --- knowledge base ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "generics", "brand"),
    [
        ("Panadol", ("paracetamol",), "Panadol"),
        ("glucophage", ("metformin",), "Glucophage"),
        ("Augmentin", ("amoxicillin and clavulanic acid",), "Augmentin"),
        ("Metformin", ("metformin",), None),
    ],
)
def test_brand_and_generic_names_resolve(name, generics, brand):
    info = knowledge.resolve_medication(name)
    assert info.generics == generics
    assert info.brand == brand
    assert info.source


def test_unknown_medicine_is_not_guessed():
    assert knowledge.resolve_medication("Rifaximin") is None


def test_high_alert_medicines_are_marked():
    assert knowledge.resolve_medication("warfarin").high_alert
    assert not knowledge.resolve_medication("Panadol").high_alert


def test_condition_abbreviations_are_case_sensitive():
    assert [m.info.name for m in knowledge.find_conditions("K/C/O DM and HTN")] == ["diabetes mellitus", "hypertension"]
    assert knowledge.find_conditions("he said dm me, then htn") == []


def test_short_lab_abbreviations_only_count_at_the_start_of_a_row():
    assert [m.info.name for m in knowledge.find_lab_tests("K 5.6 mmol/L")] == ["Potassium"]
    assert knowledge.find_lab_tests("Vitamin K was given") == []


# --- test results -----------------------------------------------------------------------------


def test_a_table_row_gives_value_unit_range_and_the_reports_own_flag():
    [hb] = of_type(extract_entities("Hemoglobin | 10.2 | g/dL | 12 - 17.5 | L"), "test_result")
    assert (hb["value"], hb["unit"], hb["reference_range"], hb["report_flag"]) == ("10.2", "g/dL", "12 - 17.5", "L")
    assert hb["certainty"] == MENTIONED


def test_every_reading_of_a_repeated_test_is_kept():
    text = "Creatinine 1.1 mg/dL 0.6 - 1.3\nCreatinine 2.4 mg/dL 0.6 - 1.3 H\nCreatinine 1.1 mg/dL 0.6 - 1.3"
    assert [e["value"] for e in of_type(extract_entities(text), "test_result")] == ["1.1", "2.4", "1.1"]


def test_an_unreadable_value_is_marked_and_never_replaced_by_the_range():
    [result] = of_type(extract_entities("Creatinine [?] mg/dL 0.6 - 1.3"), "test_result")
    assert result["readable"] is False
    assert result["value"] is None


def test_a_test_name_in_a_sentence_without_a_number_is_not_a_result():
    assert of_type(extract_entities("Creatinine should be repeated after hydration."), "test_result") == []


# --- medications ------------------------------------------------------------------------------


def test_brand_dose_and_frequency():
    [med] = of_type(extract_entities("Tab Concor 2.5 mg OD"), "medication")
    assert (med["name"], med["brand"], med["dose"], med["frequency"]) == ("bisoprolol", "Concor", "2.5 mg", "OD")


def test_stopped_medicine():
    meds = by_name(extract_entities("Warfarin stopped two weeks ago. Continue Norvasc 5 mg OD."), "medication")
    assert meds["warfarin"]["status"] == "stopped"
    assert meds["amlodipine"]["status"] == "mentioned"


def test_prescribed_medicine_outside_the_knowledge_base_is_kept_without_safety_information():
    [med] = of_type(extract_entities("Tab Rifaximin 550 mg BD"), "medication")
    assert med["name"] == "rifaximin"
    assert med["known"] is False
    assert med["classes"] == [] and med["high_alert"] is False


def test_a_medicine_named_as_an_allergy_is_not_a_current_medicine():
    entities = extract_entities("Allergic to aspirin.")
    assert of_type(entities, "medication") == []
    assert by_name(entities, "allergy")["aspirin"]["allergen_kind"] == "medication"


# --- conditions -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["No history of asthma.", "Denies asthma.", "Asthma ruled out.", "Negative for asthma."],
)
def test_negated_conditions(text):
    [condition] = of_type(extract_entities(text), "condition")
    assert condition["negated"] is True
    assert condition["context"] is None  # "no history of" is not a history


def test_history_and_positive_conditions():
    conditions = by_name(extract_entities("Known case of DM and HTN. Also anaemia."), "condition")
    assert conditions["diabetes mellitus"]["context"] == "history"
    assert not any(c["negated"] for c in conditions.values())
    assert conditions["anaemia"]["certainty"] == MENTIONED  # never a confirmed diagnosis


def test_negation_does_not_cross_into_the_next_clause():
    conditions = by_name(extract_entities("No fever. Known hypertension."), "condition")
    assert conditions["hypertension"]["negated"] is False


# --- family history ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "name", "relative"),
    [
        ("Family history of diabetes.", "diabetes mellitus", None),
        ("Fam hx of HTN.", "hypertension", None),
        ("FHx: asthma", "asthma", None),
        ("Family history: father DM, mother HTN", "diabetes mellitus", "father"),
        ("Mother has asthma.", "asthma", "mother"),
        ("Father: IHD", "ischaemic heart disease", "father"),
        ("Brother diagnosed with epilepsy.", "epilepsy", "brother"),
        ("Diabetes runs in the family.", "diabetes mellitus", None),
    ],
)
def test_family_history_is_never_the_patients_condition(text, name, relative):
    entities = extract_entities(text)
    assert of_type(entities, "condition") == []
    family = by_name(entities, "family_history")
    assert family[name]["relative"] == relative


def test_negated_family_history_is_not_a_negated_patient_condition():
    entities = extract_entities("No DM in family.")
    assert of_type(entities, "condition") == []
    assert by_name(entities, "family_history")["diabetes mellitus"]["negated"] is True


def test_family_history_ends_with_its_sentence_and_the_patients_own_conditions_stay():
    entities = extract_entities(
        "Family history: mother has DM. Known case of HTN.\nFather has IHD and patient has asthma."
    )
    assert set(by_name(entities, "condition")) == {"hypertension", "asthma"}
    assert set(by_name(entities, "family_history")) == {"diabetes mellitus", "ischaemic heart disease"}


def test_a_relatives_medicine_or_allergy_is_not_the_patients():
    entities = extract_entities("Family history: mother on insulin, allergic to penicillin.\nTab Metformin 500 mg BD")
    assert [m["name"] for m in of_type(entities, "medication")] == ["metformin"]
    assert of_type(entities, "allergy") == []


# --- allergies --------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["Allergies: NKDA", "No known drug allergies.", "Allergy: nil"])
def test_no_known_allergies_is_recorded_once(text):
    entities = extract_entities(text)
    assert [e["type"] for e in entities] == ["allergy_status"]
    assert entities[0]["status"] == "none_recorded"


def test_allergy_list_with_classes_and_reactions():
    allergies = by_name(extract_entities("Allergies: penicillin (rash), sulfa drugs"), "allergy")
    assert set(allergies) == {"penicillin", "sulfa drugs"}
    assert allergies["penicillin"]["allergen_classes"] == ["penicillin"]
    assert allergies["sulfa drugs"]["allergen_classes"] == ["sulfonamide"]


# --- BioBERT is secondary ---------------------------------------------------------------------


def test_biobert_only_adds_low_confidence_suggestions_for_what_the_rules_missed():
    biobert = [
        {"text": "asthma", "label": "Disease", "confidence": 0.99},  # the rules already found it
        {"text": "sarcoidosis", "label": "Disease", "confidence": 0.99},
        {"text": "23 y / f", "label": "Age", "confidence": 0.99},  # not a medical type
    ]
    entities = extract_entities("No history of asthma. Has sarcoidosis.", biobert)
    asthma = by_name(entities, "condition")["asthma"]
    assert asthma["method"] == "knowledge base" and asthma["negated"] is True  # the model changed nothing
    [suggestion] = [e for e in entities if e["method"] == "biobert"]
    assert suggestion["name"] == "sarcoidosis"
    assert suggestion["certainty"] == SUGGESTION
    assert suggestion["confidence"] <= 0.5


def test_empty_text():
    assert extract_entities("") == []
