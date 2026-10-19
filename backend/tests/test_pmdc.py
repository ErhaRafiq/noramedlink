"""PMDC numbers and the register check (services/pmdc.py). No network: the register's answer is faked, and
the conftest switches the real lookup off."""

from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from config import settings
from services import pmdc
from services.pmdc import PmdcDisabled, PmdcRecord, PmdcUnavailable

ON = replace(
    settings, pmdc_lookup_enabled=True, pmdc_lookup_url="https://register.example/api", pmdc_lookup_timeout=3.0
)


@pytest.fixture
def lookup_on(monkeypatch):
    monkeypatch.setattr(pmdc, "settings", ON)


# --- the format ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("12345-P", "12345-P"),
        ("12345p", "12345-P"),
        ("12345 P", "12345-P"),
        ("12345/P", "12345-P"),
        ("  12345 - p  ", "12345-P"),
        ("12345–P", "12345-P"),  # a typographic dash
        ("PMDC 12345-P", "12345-P"),
        ("PMDC-12345-P", "12345-P"),
        ("pmdc no. 12345-n", "12345-N"),
        ("PM&DC No: 12345-S", "12345-S"),
        ("PM & DC Reg. No. 12345-D", "12345-D"),
        ("PMC 12345-P", "12345-P"),
        ("Registration No. 12345-P", "12345-P"),
        ("012345-P", "12345-P"),  # the register has no leading zeros
        ("1234-D", "1234-D"),
        ("123-S", "123-S"),
        ("1234567-P", "1234567-P"),
        ("1815-AJK", "1815-AJK"),  # Azad Jammu and Kashmir: a three-letter ending
        ("1815ajk", "1815-AJK"),
        ("1815 / AJK", "1815-AJK"),
        ("PMDC 1815-AJK", "1815-AJK"),
        ("01815-ajk", "1815-AJK"),
        ("12-P", "12-P"),  # the register has short numbers too
        ("1-S", "1-S"),
        ("00012-P", "12-P"),
        ("100000-P", "100000-P"),
        ("2000-B", "2000-B"),
        ("2000-F", "2000-F"),
    ],
)
def test_the_usual_ways_of_writing_a_number_become_the_form_the_register_searches(raw, canonical):
    assert pmdc.normalize_registration(raw) == canonical


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "PMDC",
        "12345",  # no letter: the register would find nothing
        "P-12345",
        "12345-PP",
        "00000-P",  # all zeros: not a number the register has
        "1815-K",  # an ending the register does not use
        "1815-A",
        "1815-AJ",
        "1815-AJKK",
        "1815-AJK-1",
        "12345-X",
        "12345-1",
        "12345678-P",  # too long
        "abcde-P",
        "12345-P-1",
        "12.345-P",
        "12345 PQ",
        "١٢٣٤٥-P",  # Arabic-Indic digits
        "HACKED",
        "'; drop table users;--",
    ],
)
def test_a_number_that_does_not_fit_is_refused(raw):
    assert pmdc.normalize_registration(raw) is None


@pytest.mark.parametrize(
    "raw", ["12345-P", "012345-p", "pmdc no. 0012345 - n", "PM&DC 1234-D", "123/S", "1815-AJK", "00001-ajk"]
)
def test_the_standard_form_normalises_to_itself(raw):
    once = pmdc.normalize_registration(raw)
    assert once is not None and pmdc.normalize_registration(once) == once


# --- names ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("register", "doctor"),
    [
        ("Erha Rafiq", "Erha Rafiq"),
        ("ERHA RAFIQ", "Dr. Erha Rafiq"),
        ("Muhammad Ali Khan", "Dr Muhammad Ali"),  # a middle or last name left out
        ("Mohammad Ali", "Muhammad Ali"),  # a spelling variant
        ("Sadia Maryam", "Maryam Sadia"),  # the order differs
        ("Ayesha", "Ayesha"),  # a one-word name matches only another one-word name
    ],
)
def test_the_register_name_may_differ_in_spelling_order_or_titles(register, doctor):
    assert pmdc.names_match(register, doctor)


@pytest.mark.parametrize(
    ("register", "doctor"),
    [
        ("Erha Rafiq", "Momna Javed"),
        ("Muhammad Ali Khan", "Muhammad"),  # one shared word is not enough
        ("Muhammad Ali", "Muhammad Hassan"),
        ("", "Erha Rafiq"),
        ("Erha Rafiq", ""),
        ("Dr", "Dr."),  # titles alone are nothing
    ],
)
def test_a_different_name_is_not_a_match(register, doctor):
    assert not pmdc.names_match(register, doctor)


# --- the register's answer -----------------------------------------------------------------------------


def reply(status=200, **body):
    return lambda *args, **kwargs: httpx.Response(status, **body)


ROW = {"RegistrationNo": "12345-P", "Name": "Erha  Rafiq", "FatherName": "X", "Status": "ACTIVE"}


def test_a_listed_number_comes_back_with_its_name_and_status(lookup_on):
    record = pmdc.lookup("12345-P", post=reply(json={"status": True, "data": [ROW], "message": "1 Records Found!"}))
    assert record == PmdcRecord("12345-P", "Erha Rafiq", "ACTIVE")


def test_only_the_registration_number_is_sent(lookup_on):
    seen = {}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(200, json={"status": True, "data": []})

    pmdc.lookup("12345-P", post=post)
    assert seen["url"] == "https://register.example/api"
    assert seen["data"] == {"RegistrationNo": "12345-P", "Name": "", "FatherName": ""}
    assert seen["timeout"] == 3.0 and seen["follow_redirects"] is False


def test_an_empty_answer_means_the_register_does_not_list_the_number(lookup_on):
    assert pmdc.lookup("12345-P", post=reply(json={"status": True, "data": [], "message": "0 Records Found!"})) is None


def test_a_row_for_another_number_is_not_taken_for_ours(lookup_on):
    other = {**ROW, "RegistrationNo": "99999-P"}
    assert pmdc.lookup("12345-P", post=reply(json={"status": True, "data": [other]})) is None


@pytest.mark.parametrize(
    "answer",
    [
        reply(status=500, json={}),
        reply(status=200, content=b"<html>maintenance</html>"),
        reply(json={"status": False, "data": None, "message": "error"}),
        reply(json=["not", "a", "dict"]),
        reply(json={"status": True, "data": "oops"}),
    ],
)
def test_an_answer_we_cannot_use_is_unavailable_not_not_found(lookup_on, answer):
    with pytest.raises(PmdcUnavailable):
        pmdc.lookup("12345-P", post=answer)


def test_a_network_failure_is_unavailable(lookup_on):
    def post(*args, **kwargs):
        raise httpx.ConnectTimeout("slow")

    with pytest.raises(PmdcUnavailable):
        pmdc.lookup("12345-P", post=post)


def test_the_lookup_is_off_in_a_test_run_and_makes_no_request():
    def post(*args, **kwargs):
        raise AssertionError("a request was made")

    with pytest.raises(PmdcDisabled):
        pmdc.lookup("12345-P", post=post)


# --- recording a check ---------------------------------------------------------------------------------


def profile(number="12345-P"):
    return SimpleNamespace(
        pmdc_number=number, pmdc_verified=False, pmdc_outcome=None, pmdc_checked_at=None, pmdc_checked_by_id=None,
        pmdc_register_name=None, pmdc_register_status=None, pmdc_note="old note",
    )  # fmt: skip


def check(record, number="12345-P", name="Dr. Erha Rafiq"):
    p = profile(number)
    outcome = pmdc.check_doctor(p, name, 7, lookup_fn=lambda n: record)
    return outcome, p


def test_active_under_the_doctors_name_is_verified():
    outcome, p = check(PmdcRecord("12345-P", "Erha Rafiq", "ACTIVE"))
    assert outcome == "verified" and p.pmdc_verified is True
    assert (p.pmdc_register_name, p.pmdc_register_status, p.pmdc_checked_by_id, p.pmdc_note) == (
        "Erha Rafiq",
        "ACTIVE",
        7,
        None,
    )
    assert p.pmdc_checked_at is not None


def test_a_listed_but_inactive_number_is_not_verified():
    outcome, p = check(PmdcRecord("12345-P", "Erha Rafiq", "In Active"))
    assert outcome == "inactive" and p.pmdc_verified is False and p.pmdc_register_status == "In Active"


def test_another_persons_name_is_not_verified_and_the_name_is_kept_for_the_admin():
    outcome, p = check(PmdcRecord("12345-P", "Someone Else", "ACTIVE"))
    assert outcome == "name_mismatch" and p.pmdc_verified is False and p.pmdc_register_name == "Someone Else"


def test_an_unlisted_number_is_not_verified():
    outcome, p = check(None)
    assert outcome == "not_found" and p.pmdc_verified is False and p.pmdc_register_name is None


def test_a_stored_number_that_does_not_fit_is_not_sent_to_the_register():
    def lookup_fn(number):
        raise AssertionError("the register was asked about a number that cannot be searched")

    p = profile("HACKED")
    assert pmdc.check_doctor(p, "Erha Rafiq", 7, lookup_fn=lookup_fn) == "format_invalid"
    assert p.pmdc_verified is False


def test_an_older_number_in_another_spelling_is_searched_in_the_standard_form():
    asked = []
    p = profile("pmc 12345 p")
    pmdc.check_doctor(p, "Erha Rafiq", 7, lookup_fn=lambda n: asked.append(n))
    assert asked == ["12345-P"]


def test_an_unreachable_register_changes_nothing():
    p = profile()
    p.pmdc_verified = True  # verified earlier

    def lookup_fn(number):
        raise PmdcUnavailable

    with pytest.raises(PmdcUnavailable):
        pmdc.check_doctor(p, "Erha Rafiq", 7, lookup_fn=lookup_fn)
    assert p.pmdc_verified is True and p.pmdc_outcome is None and p.pmdc_note == "old note"


def test_a_later_check_can_take_the_badge_away():
    p = profile()
    p.pmdc_verified = True
    pmdc.check_doctor(p, "Erha Rafiq", 7, lookup_fn=lambda n: PmdcRecord(n, "Erha Rafiq", "In Active"))
    assert p.pmdc_verified is False


def test_a_decision_by_hand_keeps_the_reason_and_who_made_it():
    p = profile()
    pmdc.set_by_hand(p, True, "  Checked on pmdc.pk: the name is spelled differently.  ", 9)
    assert (p.pmdc_verified, p.pmdc_outcome, p.pmdc_checked_by_id) == (True, "manual", 9)
    assert p.pmdc_note == "Checked on pmdc.pk: the name is spelled differently."
