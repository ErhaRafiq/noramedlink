"""The app's local date (Asia/Karachi by default): timestamps stay UTC, date-only values use the patient's calendar.

Just after midnight in Pakistan (00:30) it is still the previous day in UTC. No database, no network."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from config import settings
from schemas import BodyMeasurementIn, BodyMeasurementUpdate
from services import body_measurements as bm
from services import clock, pregnancy
from services.mscie import context as mscie_context
from services.mscie.engine import PatientContext

# 00:30 on 22 November in Pakistan (UTC+5) is 19:30 on 21 November in UTC
HALF_PAST_MIDNIGHT_PKT = datetime(2026, 11, 21, 19, 30, tzinfo=UTC)


@pytest.fixture
def at_0030_pakistan(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: HALF_PAST_MIDNIGHT_PKT)


def test_the_default_zone_is_pakistan():
    assert settings.app_timezone == "Asia/Karachi"
    assert clock.zone().key == "Asia/Karachi"


def test_today_at_0030_in_pakistan_is_the_next_day_while_utc_is_still_the_previous_day(at_0030_pakistan):
    assert clock.now().date() == date(2026, 11, 21)  # UTC
    assert clock.today() == date(2026, 11, 22)  # the patient's calendar


def test_today_accepts_any_moment_and_reads_a_naive_one_as_utc():
    assert clock.today(datetime(2026, 11, 21, 18, 59, tzinfo=UTC)) == date(2026, 11, 21)  # 23:59 PKT
    assert clock.today(datetime(2026, 11, 21, 19, 0, tzinfo=UTC)) == date(2026, 11, 22)  # 00:00 PKT
    assert clock.today(datetime(2026, 11, 21, 19, 30)) == date(2026, 11, 22)


def test_local_date_of_a_stored_timestamp_and_of_a_plain_date():
    assert clock.local_date(HALF_PAST_MIDNIGHT_PKT) == date(2026, 11, 22)
    assert clock.local_date(date(2026, 1, 1)) == date(2026, 1, 1)
    assert clock.local_date(None) is None


def test_a_date_that_is_today_in_pakistan_is_not_in_the_future(at_0030_pakistan):
    tomorrow_utc = date(2026, 11, 22)  # still "tomorrow" by the UTC clock, but it is today for the patient
    assert BodyMeasurementIn(weight=70, measured_on=tomorrow_utc).measured_on == tomorrow_utc
    assert BodyMeasurementUpdate(measured_on=tomorrow_utc).measured_on == tomorrow_utc
    assert bm.validate_input(70, "kg", None, tomorrow_utc)[2] == tomorrow_utc
    with pytest.raises(ValueError):
        BodyMeasurementIn(weight=70, measured_on=date(2026, 11, 23))
    with pytest.raises(bm.MeasurementError):
        bm.validate_input(70, "kg", None, date(2026, 11, 23))


def test_a_reading_with_no_date_defaults_to_the_patients_today(at_0030_pakistan):
    assert bm.validate_input(70, "kg", None, None)[2] == date(2026, 11, 22)


def test_weight_age_in_days_counts_from_the_local_date(at_0030_pakistan):
    # taken on 21 Aug: 93 days before 22 November, but 92 days before 21 November (the UTC date)
    assert not bm.weight_is_current(date(2026, 8, 21), 40)
    assert bm.weight_is_current(date(2026, 8, 24), 40)  # 90 days by the local calendar


def test_the_pregnancy_date_set_at_0030_is_the_local_date_not_yesterday(at_0030_pakistan, monkeypatch):
    monkeypatch.setattr(pregnancy.audit, "record", lambda *a, **k: None)
    profile = SimpleNamespace(
        id=1, gender="female", pregnancy_status=None, pregnancy_status_set_at=None,
        pregnancy_status_set_by_role=None, pregnancy_status_set_by_id=None,
    )  # fmt: skip
    me = SimpleNamespace(id=5, patient_profile=profile)
    pregnancy.set_status(None, me, me, "pregnant")
    assert profile.pregnancy_status_set_at == HALF_PAST_MIDNIGHT_PKT  # the timestamp itself stays UTC
    state = pregnancy.state_for(profile)
    assert state.set_on == date(2026, 11, 22) and state.status == "pregnant"


def test_the_pregnancy_expiry_uses_the_local_calendar(at_0030_pakistan):
    # set 10 months before 22 Nov (22 Jan): still current today; set on 21 Jan: expired
    keep = pregnancy.effective("pregnant", datetime(2026, 1, 21, 19, 30, tzinfo=UTC), "patient")  # 22 Jan local
    gone = pregnancy.effective("pregnant", datetime(2026, 1, 21, 18, 30, tzinfo=UTC), "patient")  # 21 Jan local
    assert keep.status == "pregnant" and not keep.expired
    assert gone.status == "not_recorded" and gone.expired


def test_age_in_months_and_years_use_the_local_date(at_0030_pakistan, monkeypatch):
    monkeypatch.setattr(mscie_context.body_record, "rows_for", lambda db, patient_id: [])
    # born 22 August: exactly 3 months old on 22 November local; 2 months by the UTC date (21 November)
    baby = SimpleNamespace(id=1, patient_profile=SimpleNamespace(date_of_birth=date(2026, 8, 22), gender="male"))
    context = PatientContext()
    mscie_context._add_body(None, baby, context, clock.today())
    assert context.age_months == 3
    # a birthday on 22 November: 36 years old now, still 35 by the UTC date
    adult = SimpleNamespace(id=2, patient_profile=SimpleNamespace(date_of_birth=date(1990, 11, 22), gender="female"))
    context = PatientContext()
    mscie_context._add_body(None, adult, context, clock.today())
    assert context.age == 36


def test_the_profile_age_uses_the_local_date(at_0030_pakistan):
    from services.profiles import age_on

    assert age_on(date(1990, 11, 22)) == 36
    assert age_on(date(1990, 11, 23)) == 35


def test_a_timestamp_is_still_utc_and_moves_with_the_clock(monkeypatch):
    first = clock.now()
    assert first.tzinfo is not None and first.utcoffset() == timedelta(0)
