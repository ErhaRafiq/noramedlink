"""Signup checks (services/signup_service.py and the signup schemas)."""

from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from schemas import SignupRequest
from services import signup_service
from services.signup_service import normalize_email, normalize_phone, validate_role_specific_fields

BASE = {
    "full_name": "Test Patient",
    "email": "patient1@test.com",
    "password": "a-strong-pass",
    "confirm_password": "a-strong-pass",
    "phone": "0300 1234567",
}


def payload(**fields) -> SignupRequest:
    return SignupRequest(**{**BASE, **fields})


def rejected(request: SignupRequest) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        validate_role_specific_fields(request)
    return caught.value


def test_normalizers():
    assert normalize_email("  Patient1@Test.COM ") == "patient1@test.com"
    assert normalize_phone("  0300   123  4567 ") == "0300 123 4567"


@pytest.mark.parametrize("cnic", ["12345-1234567-1", "1234512345671"])
def test_valid_patient(cnic):
    validate_role_specific_fields(payload(role="patient", cnic=cnic, date_of_birth=date(1990, 1, 1), gender="female"))


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"cnic": None}, "CNIC number is required"),
        ({"cnic": "12345-123"}, "CNIC must be 13 digits"),
        ({"date_of_birth": None}, "Date of birth and gender"),
        ({"gender": "  "}, "Date of birth and gender"),
    ],
)
def test_incomplete_patient(fields, message):
    request = payload(
        role="patient", **{"cnic": "12345-1234567-1", "date_of_birth": date(1990, 1, 1), "gender": "male", **fields}
    )
    error = rejected(request)
    assert error.status_code == 400 and message in error.detail


def test_doctor_needs_registration_specialty_and_hospital():
    complete = {"pmdc_number": "PMC 12345-P", "specialization": "Cardiology", "hospital_name": "City Hospital"}
    validate_role_specific_fields(payload(role="doctor", **complete))
    assert "PMDC/PMC" in rejected(payload(role="doctor", **{**complete, "pmdc_number": " "})).detail
    assert "Specialization" in rejected(payload(role="doctor", **{**complete, "hospital_name": None})).detail


@pytest.mark.parametrize("number", ["PMC-12345", "12345", "HACKED", "12-X", "12345-PP", "P-12345"])
def test_a_doctor_number_that_is_not_in_a_recognised_form_is_refused_with_an_example(number):
    complete = {"specialization": "Cardiology", "hospital_name": "City Hospital"}
    error = rejected(payload(role="doctor", pmdc_number=number, **complete))
    assert error.status_code == 422 and "12345-P" in error.detail


def test_the_number_is_checked_for_duplicates_in_its_standard_form():
    complete = {"specialization": "Cardiology", "hospital_name": "City Hospital"}
    assert signup_service.doctor_pmdc(payload(role="doctor", pmdc_number="pmdc 12345 p", **complete)) == "12345-P"
    assert signup_service.doctor_pmdc(payload(role="patient")) is None


def test_admin_needs_the_configured_invite_code(monkeypatch):
    monkeypatch.setattr(signup_service, "admin_invite_code", lambda: "invite-123")
    validate_role_specific_fields(payload(role="admin", admin_invite_code="invite-123"))
    assert rejected(payload(role="admin")).status_code == 400
    assert rejected(payload(role="admin", admin_invite_code="wrong")).status_code == 403


def test_admin_signup_is_closed_when_no_code_is_configured(monkeypatch):
    monkeypatch.setattr(signup_service, "admin_invite_code", lambda: "")
    assert rejected(payload(role="admin", admin_invite_code="anything")).status_code == 403


@pytest.mark.parametrize(
    "fields",
    [
        {"password": "short", "confirm_password": "short"},
        {"confirm_password": "something-else"},
        {"email": "not-an-email"},
        {"role": "pharmacist"},
    ],
)
def test_schema_rejects_bad_signups(fields):
    with pytest.raises(ValidationError):
        SignupRequest(**{**BASE, "role": "patient", **fields})


@pytest.mark.parametrize(
    ("first", "second"),
    [("momna-56", "MOMNA-56"), ("PMC 12345", "pmc12345"), ("  12345-P ", "12345-p")],
)
def test_pmdc_numbers_compare_without_case_or_spaces(first, second):
    from services.signup_service import normalize_pmdc

    assert normalize_pmdc(first) == normalize_pmdc(second)


def test_different_pmdc_numbers_stay_different():
    from services.signup_service import normalize_pmdc

    assert normalize_pmdc("12345-P") != normalize_pmdc("12345-PA")
