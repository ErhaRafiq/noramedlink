"""Pregnancy status: what counts as recorded, when "pregnant" goes out of date (an app rule, from config),
who set it, and that nothing is read from free text. No database, no network."""

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from config import settings
from schemas import PregnancyStatusIn
from services import body_measurements as bm
from services import pregnancy
from services.mscie.engine import PatientContext

TODAY = date(2026, 11, 20)


def at(day):
    return datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)


def test_add_months_keeps_the_day_or_the_end_of_a_short_month():
    assert pregnancy.add_months(date(2026, 1, 15), 10) == date(2026, 11, 15)
    assert pregnancy.add_months(date(2026, 3, 31), 1) == date(2026, 4, 30)
    assert pregnancy.add_months(date(2025, 12, 31), 2) == date(2026, 2, 28)
    assert pregnancy.add_months(date(2026, 5, 5), 10) == date(2027, 3, 5)


def test_nothing_stored_is_not_recorded():
    state = pregnancy.effective(None, None, None, TODAY)
    assert (state.status, state.set_on, state.expired, state.pregnant) == ("not_recorded", None, False, False)


def test_a_recent_pregnant_status_counts():
    state = pregnancy.effective("pregnant", at(date(2026, 8, 1)), "patient", TODAY)
    assert state.status == "pregnant" and state.pregnant and not state.expired
    assert state.set_on == date(2026, 8, 1) and state.set_by_role == "patient"


def test_the_setting_is_ten_months_and_is_an_app_rule():
    assert settings.pregnancy_status_max_months == 10
    assert pregnancy.effective("pregnant", at(date(2026, 1, 20)), "patient", TODAY).status == "pregnant"  # exactly 10
    old = pregnancy.effective("pregnant", at(date(2026, 1, 19)), "patient", TODAY)
    assert old.status == "not_recorded" and old.expired and not old.pregnant
    assert old.set_on == date(2026, 1, 19) and old.max_months == 10  # the page can say when it was set


def test_not_pregnant_does_not_expire():
    state = pregnancy.effective("not_pregnant", at(date(2020, 1, 1)), "doctor", TODAY)
    assert state.status == "not_pregnant" and not state.expired and not state.pregnant


def test_a_pregnant_status_with_no_date_cannot_be_trusted():
    state = pregnancy.effective("pregnant", None, None, TODAY)
    assert state.status == "not_recorded" and state.expired


def test_an_unknown_stored_word_is_not_recorded():
    assert pregnancy.effective("maybe", at(TODAY), "patient", TODAY).status == "not_recorded"


def test_the_window_can_be_changed_for_a_test():
    assert pregnancy.effective("pregnant", at(date(2026, 10, 1)), "patient", TODAY, max_months=1).expired


# --- the BMI rule reads the field, never text -------------------------------------------------------------


def test_the_bmi_category_is_withheld_only_for_a_current_pregnant_status():
    pregnant = pregnancy.effective("pregnant", at(date(2026, 10, 1)), "patient", TODAY)
    result = bm.bmi_result(70, 170, 30, pregnant.pregnant)
    assert result.category is None and "pregnant" in result.category_note
    for stored in ("not_pregnant", None):
        state = pregnancy.effective(stored, at(TODAY) if stored else None, "patient", TODAY)
        assert bm.bmi_result(70, 170, 30, state.pregnant).category == "normal range"
    expired = pregnancy.effective("pregnant", at(date(2025, 1, 1)), "patient", TODAY)
    assert bm.bmi_result(70, 170, 30, expired.pregnant).category == "normal range"


def test_the_old_keyword_logic_is_gone():
    from services import body_record

    assert not hasattr(body_record, "is_marked_pregnant")


# --- setting it -------------------------------------------------------------------------------------------


@pytest.fixture
def audits(monkeypatch):
    calls = []
    monkeypatch.setattr(pregnancy.audit, "record", lambda *a, **k: calls.append((a[2], k)))
    return calls


def patient(gender="female"):
    profile = SimpleNamespace(
        id=7,
        gender=gender,
        pregnancy_status=None,
        pregnancy_status_set_at=None,
        pregnancy_status_set_by_role=None,
        pregnancy_status_set_by_id=None,
    )
    return SimpleNamespace(id=5, patient_profile=profile)


def test_a_patient_sets_their_own_status(audits):
    me = patient()
    profile = pregnancy.set_status(None, me, me, "pregnant")
    assert profile.pregnancy_status == "pregnant" and profile.pregnancy_status_set_by_role == "patient"
    assert profile.pregnancy_status_set_by_id == 5 and profile.pregnancy_status_set_at is not None
    action, extra = audits[0]
    assert action == "pregnancy_status.set" and extra["detail"] == "pregnancy status"  # a label, never the value


def test_a_doctor_sets_it_and_the_role_is_kept(audits):
    me = patient()
    pregnancy.set_status(None, me, SimpleNamespace(id=9), "not_pregnant")
    profile = me.patient_profile
    assert profile.pregnancy_status == "not_pregnant"
    assert profile.pregnancy_status_set_by_role == "doctor" and profile.pregnancy_status_set_by_id == 9


def test_not_recorded_clears_everything(audits):
    me = patient()
    pregnancy.set_status(None, me, me, "pregnant")
    pregnancy.set_status(None, me, me, "not_recorded")
    p = me.patient_profile
    assert (p.pregnancy_status, p.pregnancy_status_set_at, p.pregnancy_status_set_by_role) == (None, None, None)
    assert len(audits) == 2  # the change is still logged


def test_pregnant_is_refused_for_a_patient_recorded_as_male(audits):
    me = patient("Male")
    with pytest.raises(HTTPException) as error:
        pregnancy.set_status(None, me, me, "pregnant")
    assert error.value.status_code == 422 and me.patient_profile.pregnancy_status is None and audits == []
    pregnancy.set_status(None, me, me, "not_pregnant")  # allowed: it is a true statement
    assert me.patient_profile.pregnancy_status == "not_pregnant"


def test_an_unknown_status_is_refused(audits):
    me = patient()
    with pytest.raises(HTTPException) as error:
        pregnancy.set_status(None, me, me, "expecting")
    assert error.value.status_code == 422
    with pytest.raises(ValueError):
        PregnancyStatusIn(status="expecting")


# --- available to MSCIE ---------------------------------------------------------------------------------------


def test_the_check_context_carries_the_status_and_defaults_to_not_recorded():
    assert PatientContext().pregnancy == "not_recorded"
