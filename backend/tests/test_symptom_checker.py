"""The symptom checker (services/symptom_checker.py): red flags come first and stop everything else;
otherwise symptom words map to a fixed list of specialties. No database, no network."""

from datetime import UTC, datetime, timedelta

import pytest

from schemas import AppointmentDoctorOut
from services import symptom_checker as checker
from services.knowledge.tables import records

SPECIALTIES = {row["name"] for row in records("specialties")}


def flag_labels(text: str) -> list[str]:
    return [flag.label for flag in checker.red_flags(text)]


# --- the cases from the project brief ------------------------------------------------------------------


def test_chest_pain_with_breathlessness_is_an_emergency_not_a_cardiologist():
    labels = flag_labels("Chest pain, dizziness, shortness of breath")
    assert "Chest pain or pressure" in labels and "Difficulty breathing" in labels


def test_an_itchy_rash_goes_to_dermatology():
    assert not checker.red_flags("itchy rash on arm for a week")
    assert checker.suggest_specialties("itchy rash on arm for a week")[0].specialty == "Dermatologist"


def test_fever_and_sore_throat_go_to_a_general_physician():
    assert not checker.red_flags("fever and sore throat for 2 days")
    top = checker.suggest_specialties("fever and sore throat for 2 days")
    assert top[0].specialty == "General Physician" and len(top) == 1


# --- red flags -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "my father has face drooping and slurred speech",
        "he has lost consciousness",
        "she passed out in the kitchen",
        "heavy bleeding that won't stop",
        "bleeding will not stop after the cut",
        "he is vomiting blood",
        "my son had a seizure today",
        "she is having a fit",
        "I want to die",
        "I keep thinking about suicide",
        "I can't breathe",
        "my throat is closing after the injection",
        "an allergic reaction and my tongue is swelling",
        "the worst headache of my life",
        "he took too many tablets, an overdose",
        "my 3 month old baby has a fever",
        "newborn with high temperature",
        "CHEST PAIN!!!",
        "Pain in the chest since morning",
    ],
)
def test_every_warning_sign_is_caught(text):
    assert checker.red_flags(text), text


@pytest.mark.parametrize(
    "text",
    [
        "no chest pain, just a sore knee",
        "I do not have shortness of breath but I have a cough",
        "without any chest pain",
        "never had a seizure",
        "denies suicidal thoughts",
        "my 40 year old father has a fever",  # an adult's fever is not the infant red flag
        "itchy rash",
    ],
)
def test_a_sign_the_patient_says_they_do_not_have_is_not_a_warning(text):
    assert not checker.red_flags(text), text


def test_negation_does_not_hide_a_second_warning_in_the_same_text():
    assert flag_labels("no chest pain but I am vomiting blood") == ["Severe bleeding"]


def test_a_negator_further_back_does_not_cancel_a_warning():
    # "no" is three words before "chest pain": a separate statement, so the pain still counts.
    assert checker.red_flags("no I have chest pain")


def test_negation_does_not_cross_a_sentence_end():
    assert checker.red_flags("I have no appetite. Chest pain since morning")


def test_an_allergy_word_alone_is_not_a_warning():
    assert not checker.red_flags("allergic rhinitis, a runny nose")
    assert checker.red_flags("allergic reaction with swelling of the face")


# --- specialties ---------------------------------------------------------------------------------------


def test_the_specialty_list_is_fixed():
    for row in records("symptom_specialties"):
        assert row["specialty"] in SPECIALTIES


def test_no_match_falls_back_to_a_general_physician_and_says_so():
    [only] = checker.suggest_specialties("feeling strange lately")
    assert only.specialty == "General Physician" and only.fallback and only.matched == []


def test_the_longest_phrase_wins_and_is_not_counted_twice():
    [only] = checker.suggest_specialties("high blood pressure")
    assert only.specialty == "Cardiologist" and only.matched == ["high blood pressure"] and only.score == 3


def test_ties_return_every_specialty_that_fits():
    names = [s.specialty for s in checker.suggest_specialties("my child has a rash")]
    assert names[:2] == ["Dermatologist", "Pediatrician"]


def test_a_symptom_the_patient_does_not_have_is_not_used():
    names = [s.specialty for s in checker.suggest_specialties("no rash, knee pain")]
    assert names == ["Orthopedic Specialist"]


def test_at_most_three_suggestions_each_with_its_reason():
    suggestions = checker.suggest_specialties("rash, back pain, headache, acidity, anxiety, toothache")
    assert len(suggestions) <= 3 and all(s.matched for s in suggestions)


# --- doctors -------------------------------------------------------------------------------------------


BASE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)  # fixed, so equal openings really are equal


def doctor(id_, specialty, *, days=None, rating=None, fee=None):
    when = BASE + timedelta(days=days) if days is not None else None
    return AppointmentDoctorOut(
        id=id_, doctor_id=id_, name=f"Dr {id_}", specialty=specialty, location="Clinic",
        next_available=when, rating=rating, consultation_fee=fee,
    )  # fmt: skip


def test_only_doctors_of_the_specialty_are_listed_soonest_opening_first():
    aliases = next(s for s in checker.suggest_specialties("itchy rash")).aliases
    ranked = checker.rank_doctors(
        [
            doctor(1, "Dermatology", days=3, rating=5.0),
            doctor(2, "Cardiology", days=0),
            doctor(3, "Consultant Dermatologist", days=1, rating=3.0),
            doctor(4, "Skin specialist"),
        ],
        aliases,
    )
    assert [d.id for d in ranked] == [3, 1, 4]  # nobody from Cardiology; no opening listed last


def test_rating_then_fee_break_ties_and_a_missing_fee_is_not_cheap():
    ranked = checker.rank_doctors(
        [
            doctor(1, "General Physician", days=1, rating=4.0, fee=500),
            doctor(2, "General Physician", days=1, rating=4.5, fee=3000),
            doctor(3, "General Physician", days=1, rating=4.5, fee=None),
            doctor(4, "General Physician", days=1, rating=4.5, fee=1000),
        ],
        ["general physician"],
    )
    assert [d.id for d in ranked] == [4, 2, 3, 1]


def test_at_most_five_doctors_are_listed():
    many = [doctor(i, "General Physician", days=i) for i in range(1, 9)]
    assert [d.id for d in checker.rank_doctors(many, ["general physician"])] == [1, 2, 3, 4, 5]
