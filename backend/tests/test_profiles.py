"""Profile rules (Module 1): what a patient or doctor may save, and what is shown back."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from schemas import AccountUpdate, DoctorProfileUpdate, PatientProfileUpdate
from services.profiles import age_on, mask_cnic, split_list

DOCTOR = {
    "hospital_name": "City  Hospital",
    "consultation_modes": ["home", "online"],
    "languages": [" Urdu ", "English", "Urdu", ""],
}


def test_age_counts_whole_years_only():
    assert age_on(date(2000, 6, 15), today=date(2026, 6, 14)) == 25
    assert age_on(date(2000, 6, 15), today=date(2026, 6, 15)) == 26


def test_the_cnic_is_never_shown_in_full():
    assert mask_cnic("12345-1234567-1") == "*****-*******-1"
    assert "1234567" not in mask_cnic("1234512345679")
    assert mask_cnic("") == "Not recorded"


def test_patient_details_are_checked_and_tidied():
    saved = PatientProfileUpdate(
        date_of_birth=date(1990, 1, 1), gender=" female ", blood_group="ab+", city="  Lahore ", address=" "
    )
    assert (saved.gender, saved.blood_group, saved.city, saved.address) == ("Female", "AB+", "Lahore", None)


@pytest.mark.parametrize(
    "fields",
    [
        {"date_of_birth": date.today() + timedelta(days=1)},
        {"date_of_birth": date(1850, 1, 1)},
        {"gender": "robot"},
        {"blood_group": "Z+"},
    ],
)
def test_impossible_patient_details_are_refused(fields):
    base = {"date_of_birth": date(1990, 1, 1), "gender": "Male"}
    with pytest.raises(ValidationError):
        PatientProfileUpdate(**{**base, **fields})


def test_doctor_details_are_tidied_and_modes_keep_a_fixed_order():
    saved = DoctorProfileUpdate(**DOCTOR)
    assert saved.hospital_name == "City Hospital"
    assert saved.languages == ["Urdu", "English"]
    assert saved.consultation_modes == ["online", "home"]


@pytest.mark.parametrize(
    "fields",
    [
        {"consultation_modes": []},
        {"consultation_modes": ["telepathy"]},
        {"consultation_fee": 50},
        {"consultation_fee": 1_000_000},
        {"experience_years": -1},
        {"experience_years": 90},
        {"hospital_name": "x"},
        {"languages": ["a" * 31]},
    ],
)
def test_impossible_doctor_details_are_refused(fields):
    with pytest.raises(ValidationError):
        DoctorProfileUpdate(**{**DOCTOR, **fields})


def test_a_doctor_cannot_change_the_verified_fields():
    saved = DoctorProfileUpdate(**DOCTOR, specialization="Cardiology", pmdc_number="1", verification_status="approved")
    assert not {"specialization", "pmdc_number", "verification_status"} & set(saved.model_dump())


def test_account_names_and_phones_are_tidied_and_must_be_long_enough():
    assert AccountUpdate(full_name="  Ayesha   Khan ", phone="0300  1234567").full_name == "Ayesha Khan"
    with pytest.raises(ValidationError):
        AccountUpdate(full_name="A", phone="0300 1234567")
    with pytest.raises(ValidationError):
        AccountUpdate(full_name="Ayesha Khan", phone="123")


def test_stored_lists_are_split_on_commas():
    assert split_list("Urdu, English ,") == ["Urdu", "English"]
    assert split_list(None) == []
