"""Signup checks (services/signup_service.py and the signup schemas)."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from schemas import PatientSignupRequest, SignupOtpRequest, VerifySignupOtpRequest
from services import signup_service
from services.signup_service import as_utc, normalize_email, normalize_phone, validate_role_specific_fields

BASE = {
    "full_name": "Test Patient",
    "email": "patient1@test.com",
    "password": "a-strong-pass",
    "confirm_password": "a-strong-pass",
    "phone": "0300 1234567",
}


def payload(**fields) -> SignupOtpRequest:
    return SignupOtpRequest(**{**BASE, **fields})


def rejected(request: SignupOtpRequest) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        validate_role_specific_fields(request)
    return caught.value


def test_normalizers():
    assert normalize_email("  Patient1@Test.COM ") == "patient1@test.com"
    assert normalize_phone("  0300   123  4567 ") == "0300 123 4567"


def test_as_utc_treats_naive_times_as_utc_and_converts_aware_ones():
    naive = datetime(2026, 1, 1, 12, 0)
    assert as_utc(naive) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    karachi = datetime(2026, 1, 1, 17, 0, tzinfo=timezone(timedelta(hours=5)))
    assert as_utc(karachi) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


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
    complete = {"pmdc_number": "PMC-12345", "specialization": "Cardiology", "hospital_name": "City Hospital"}
    validate_role_specific_fields(payload(role="doctor", **complete))
    assert "PMDC/PMC" in rejected(payload(role="doctor", **{**complete, "pmdc_number": " "})).detail
    assert "Specialization" in rejected(payload(role="doctor", **{**complete, "hospital_name": None})).detail


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
        SignupOtpRequest(**{**BASE, "role": "patient", **fields})


@pytest.mark.parametrize("otp", ["12345", "abcdef", "12 345"])
def test_otp_must_be_six_digits(otp):
    with pytest.raises(ValidationError):
        VerifySignupOtpRequest(**BASE, role="patient", otp=otp)


def test_patient_signup_schema_normalises_cnic():
    request = PatientSignupRequest(**BASE, cnic=" 12345-1234567-1 ", date_of_birth=date(1990, 1, 1), gender="female")
    assert request.cnic == "12345-1234567-1"


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
