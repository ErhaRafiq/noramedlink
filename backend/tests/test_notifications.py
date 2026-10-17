"""In-app notifications: which category a kind belongs to, where an older one leads, and the rules that stop an
event being told twice. No database."""

import contextlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from services import notifications


@pytest.mark.parametrize(
    ("kind", "category"),
    [
        ("appointment_confirmed", "appointments"),
        ("appointment_reminder", "appointments"),
        ("review_received", "appointments"),
        ("payment_received", "payments"),
        ("payment_refund", "payments"),
        ("prescription_added", "records"),
        ("access_opened", "records"),
        ("record_changed", "records"),
        ("account_password", "account"),
        ("doctor_approved", "account"),
        ("doctor_pmdc", "account"),
        ("admin_doctor_review", "admin"),
        ("admin_refund_attention", "admin"),
        ("something_new", "account"),  # an unknown kind is never lost: it lands in Account
    ],
)
def test_every_kind_has_a_category(kind, category):
    assert notifications.category_of(kind) == category


def test_every_category_the_filter_offers_matches_some_kind():
    for category in notifications.CATEGORIES:
        assert any(name == category for _, name in notifications._PREFIXES)


@pytest.mark.parametrize(
    ("kind", "role", "link"),
    [
        ("appointment_confirmed", "patient", "/doctors"),
        ("appointment_confirmed", "doctor", "/dashboard/doctor#appointments"),
        ("review_received", "doctor", "/dashboard/doctor#appointments"),
        ("payment_received", "patient", "/payments"),
        ("access_opened", "patient", None),
    ],
)
def test_an_older_notification_without_a_link_still_leads_somewhere(kind, role, link):
    assert notifications.fallback_link(kind, role) == link


def test_a_link_is_always_inside_the_app():
    """Links are written by the server from fixed paths; none points to another site."""
    for path in (notifications.PATIENT_APPOINTMENTS, notifications.DOCTOR_APPOINTMENTS):
        assert path.startswith("/") and "//" not in path and "http" not in path


@pytest.mark.parametrize(
    ("name", "shown"), [("Erha Rafiq", "Dr. Erha Rafiq"), ("Dr. Erha Rafiq", "Dr. Erha Rafiq"), ("dr sana", "dr sana")]
)
def test_a_doctors_name_gets_one_title(name, shown):
    assert notifications._dr(name) == shown


class TellDb:
    """Just enough of a session to see what add() writes, including the unique-key refusal."""

    def __init__(self):
        self.rows, self._pending = [], None

    def add(self, row):
        self._pending = row

    def begin_nested(self):
        return contextlib.nullcontext()

    def flush(self):
        if self._pending.dedupe_key and any(r.dedupe_key == self._pending.dedupe_key for r in self.rows):
            raise IntegrityError("duplicate", None, Exception("unique"))
        self.rows.append(self._pending)


def test_a_notification_without_a_key_is_always_added():
    db = TellDb()
    notifications.add(db, 1, "access_opened", "t", "b")
    notifications.add(db, 1, "access_opened", "t", "b")
    assert db._pending is not None  # added both times (no key: not deduplicated)


def test_an_event_with_the_same_key_is_told_once():
    db = TellDb()
    assert notifications.add(db, 1, "payment_received", "t", "b", dedupe_key="payment-paid:5") is not None
    assert notifications.add(db, 1, "payment_received", "t", "b", dedupe_key="payment-paid:5") is None
    assert notifications.add(db, 1, "payment_received", "t", "b", dedupe_key="payment-paid:6") is not None
    assert len(db.rows) == 2


def test_a_long_title_is_cut_to_fit_the_column():
    assert len(notifications.add(TellDb(), 1, "x", "t" * 500, "b").title) == 180


def test_the_reminders_are_a_day_an_hour_and_five_minutes_before():
    assert (timedelta(hours=24), timedelta(hours=1), timedelta(minutes=5)) == notifications.REMINDER_LEADS
    assert set(notifications.REMINDER_WORDS) == set(notifications.REMINDER_LEADS)


def test_times_are_written_in_clinic_time():
    assert notifications.when_text(datetime(2030, 1, 7, 4, 30, tzinfo=UTC)) == "Mon 7 Jan, 9:30 AM"


def test_a_payment_notice_names_the_amount_and_never_a_card_or_a_reason():
    told = []
    db = SimpleNamespace(
        add=told.append,
        begin_nested=contextlib.nullcontext,
        flush=lambda: None,
        get=lambda *a: SimpleNamespace(full_name="Sana Khan"),
    )
    payment = SimpleNamespace(id=9, user_id=1, currency="pkr", amount=1500, appointment_id=4, reference="NML-X")
    appointment = SimpleNamespace(
        date=datetime(2030, 1, 7, 4, 30, tzinfo=UTC), doctor_name="Erha Rafiq", doctor_id=2, user_id=1
    )
    notifications.payment_received(db, payment, appointment)
    assert [n.user_id for n in told] == [1, 2]
    assert "PKR 1,500" in told[0].body and "Dr. Erha Rafiq" in told[0].body and "Mon 7 Jan" in told[0].body
    assert "Sana Khan paid" in told[1].body
    for note in told:
        assert note.link and not any(word in note.body.lower() for word in ("card number", "reason", "diagnos"))
