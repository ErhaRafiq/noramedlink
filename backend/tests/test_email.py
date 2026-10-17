"""Email: the Resend client, the templates, which reminders get queued, and the token hashing.
No network and no database: the provider's answer is faked, and the conftest blanks the real key."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from config import settings
from services import auth_tokens, email_client, email_outbox, email_templates
from services.email_client import EmailDisabled, EmailError

ON = replace(
    settings, resend_api_key="re_test_key_not_real", email_from="Nora MedLink <noreply@example.test>", email_reply_to=""
)


@pytest.fixture
def provider_on(monkeypatch):
    monkeypatch.setattr(email_client, "settings", ON)


def answer(status=200, **body):
    return lambda *args, **kwargs: httpx.Response(status, **body)


def send(post, **overrides):
    args = {
        "to": "a@example.test",
        "subject": "S",
        "html": "<p>H</p>",
        "text": "T",
        "idempotency_key": "k-1",
        "kind": "reset_code",
        "post": post,
    }
    return email_client.send(**{**args, **overrides})


# --- the Resend client ---------------------------------------------------------------------------------


def test_nothing_is_sent_without_a_key():
    def post(*args, **kwargs):
        raise AssertionError("a request was made")

    with pytest.raises(EmailDisabled):
        send(post)


def test_the_request_is_what_resend_expects(provider_on):
    seen = {}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(200, json={"id": "em_123"})

    assert send(post, idempotency_key="appointment_booked:5:9") == "em_123"
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"]["Authorization"] == "Bearer re_test_key_not_real"
    assert seen["headers"]["Idempotency-Key"] == "appointment_booked:5:9"
    body = seen["json"]
    assert body["from"] == "Nora MedLink <noreply@example.test>" and body["to"] == ["a@example.test"]
    assert body["html"] == "<p>H</p>" and body["text"] == "T"  # both parts
    assert body["tags"] == [{"name": "kind", "value": "reset_code"}] and "reply_to" not in body
    assert seen["follow_redirects"] is False


def test_a_reply_to_address_is_added_when_configured(provider_on, monkeypatch):
    monkeypatch.setattr(email_client, "settings", replace(ON, email_reply_to="help@example.test"))
    seen = {}

    def post(url, **kwargs):
        seen.update(kwargs)
        return httpx.Response(200, json={"id": "x"})

    send(post)
    assert seen["json"]["reply_to"] == "help@example.test"


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(429, True), (500, True), (503, True), (400, False), (401, False), (403, False), (422, False)],
)
def test_errors_are_sorted_into_worth_retrying_or_not(provider_on, status, retryable):
    with pytest.raises(EmailError) as caught:
        send(answer(status, json={"name": "validation_error", "message": "x", "statusCode": status}))
    assert caught.value.retryable is retryable


def test_a_network_failure_is_retryable(provider_on):
    def post(*args, **kwargs):
        raise httpx.ConnectTimeout("slow")

    with pytest.raises(EmailError) as caught:
        send(post)
    assert caught.value.retryable is True


def test_the_key_never_appears_in_an_error(provider_on):
    with pytest.raises(EmailError) as caught:
        send(answer(401, json={"name": "restricted_api_key", "message": "key re_test_key_not_real is bad"}))
    assert "re_test_key_not_real" not in str(caught.value)


# --- the templates -------------------------------------------------------------------------------------

APPOINTMENT = {
    "audience": "patient", "recipient_name": "Sana Khan", "patient_name": "Sana Khan", "doctor_name": "Erha Rafiq",
    "when_text": "Mon 19 Oct, 4:30 PM", "mode": "online", "appointment_id": 7, "minutes": 5,
}  # fmt: skip
CONTEXTS = {
    "verify_email": {"name": "Sana", "link": "https://app.example/verify-email?token=abc"},
    "reset_code": {"name": "Sana", "code": "482913"},
    "password_changed": {"name": "Sana"},
    "appointment_booked": APPOINTMENT,
    "appointment_moved": {**APPOINTMENT, "old_when_text": "Sun 18 Oct, 9:00 AM"},
    "appointment_cancelled": {**APPOINTMENT, "cancelled_by": "doctor"},
    "appointment_reminder": APPOINTMENT,
}


@pytest.mark.parametrize("kind", sorted(CONTEXTS))
def test_every_email_has_a_subject_html_text_and_the_safety_note(kind):
    mail = email_templates.render(kind, CONTEXTS[kind])
    assert mail.subject and "<html" in mail.html and mail.text.strip()
    assert "1122" in mail.html and "1122" in mail.text
    assert 'lang="en"' in mail.html and "prefers-color-scheme: dark" in mail.html  # dark mode and a language
    assert "<table" in mail.html  # table layout for email clients
    assert "{" not in mail.subject and "None" not in mail.html  # no leftover placeholder


def test_the_code_is_in_the_body_and_not_in_the_subject():
    mail = email_templates.render("reset_code", CONTEXTS["reset_code"])
    assert "482913" in mail.html and "482913" in mail.text and "482913" not in mail.subject
    assert "10 minutes" in mail.text and "ignore this email" in mail.text


def test_the_verification_link_is_in_the_button_and_the_text():
    mail = email_templates.render("verify_email", CONTEXTS["verify_email"])
    assert mail.html.count("https://app.example/verify-email?token=abc") >= 2  # the button and the fallback
    assert "https://app.example/verify-email?token=abc" in mail.text


@pytest.mark.parametrize(
    "kind", ["appointment_booked", "appointment_moved", "appointment_cancelled", "appointment_reminder"]
)
def test_an_appointment_email_says_when_with_whom_and_what_type(kind):
    mail = email_templates.render(kind, CONTEXTS[kind])
    for fragment in ("Mon 19 Oct, 4:30 PM", "Dr. Erha Rafiq", "Online consultation", "Pakistan time"):
        assert fragment in mail.html and fragment in mail.text, (kind, fragment)


def test_a_move_shows_the_old_time_and_a_cancel_says_who_cancelled():
    assert "Sun 18 Oct, 9:00 AM" in email_templates.render("appointment_moved", CONTEXTS["appointment_moved"]).html
    assert (
        "cancelled your appointment"
        in email_templates.render("appointment_cancelled", CONTEXTS["appointment_cancelled"]).html
    )
    mine = {**APPOINTMENT, "cancelled_by": "patient"}
    assert "You cancelled your appointment" in email_templates.render("appointment_cancelled", mine).html


def test_the_doctor_gets_the_patients_name_and_the_patient_gets_the_doctors():
    doctor = {**APPOINTMENT, "audience": "doctor", "recipient_name": "Erha Rafiq"}
    mail = email_templates.render("appointment_booked", doctor)
    assert "Sana Khan" in mail.html and "Patient" in mail.html and "New appointment" in mail.subject
    assert (
        "Dr. Erha Rafiq" not in mail.html.split("Patient")[1][:200]
    )  # the doctor is not told their own name as "Doctor"


def test_the_reminder_subject_names_the_minutes():
    assert "5 minutes" in email_templates.render("appointment_reminder", APPOINTMENT).subject


def test_a_doctor_name_that_already_has_a_title_is_not_doubled():
    mail = email_templates.render("appointment_booked", {**APPOINTMENT, "doctor_name": "Dr. Erha Rafiq"})
    assert "Dr. Dr." not in mail.html


def test_names_from_the_record_cannot_inject_markup():
    hostile = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    mail = email_templates.render(
        "appointment_booked",
        {**APPOINTMENT, "doctor_name": hostile, "recipient_name": hostile, "patient_name": hostile},
    )
    assert "<script>" not in mail.html and "<img src=x" not in mail.html and "&lt;script&gt;" in mail.html
    verify = email_templates.render("verify_email", {"name": hostile, "link": 'https://a.example/"><script>x</script>'})
    assert "<script>" not in verify.html


def test_no_email_carries_the_reason_for_a_visit():
    context = {**APPOINTMENT, "reason": "chest pain and shortness of breath", "notes": "private note"}
    for kind in email_templates.APPOINTMENT_KINDS:
        mail = email_templates.render(kind, context)
        assert "chest pain" not in mail.html + mail.text + mail.subject and "private note" not in mail.html + mail.text


def test_an_unknown_kind_is_refused():
    with pytest.raises(ValueError):
        email_templates.render("newsletter", {})


# --- which reminders are queued ------------------------------------------------------------------------


class QueueDb:
    """Just enough of a session to see what enqueue() would add, including the unique-key refusal."""

    def __init__(self):
        self.rows, self._pending = [], None

    @contextmanager
    def begin_nested(self):
        yield

    def add(self, row):
        self._pending = row

    def flush(self):
        if any(r.dedupe_key == self._pending.dedupe_key for r in self.rows):
            raise IntegrityError("duplicate", None, Exception("unique"))
        self.rows.append(self._pending)


def person(id_, **fields):
    base = {
        "id": id_,
        "full_name": f"Person {id_}",
        "email": f"p{id_}@example.test",
        "is_active": True,
        "is_email_verified": True,
        "email_reminders": True,
    }
    return SimpleNamespace(**{**base, **fields})


def appointment(minutes_ahead):
    return SimpleNamespace(
        id=7, date=datetime.now(UTC) + timedelta(minutes=minutes_ahead), mode="in_clinic", status="BOOKED"
    )


def test_each_person_gets_a_reminder_five_minutes_before_and_it_expires_soon_after():
    db, appt = QueueDb(), appointment(120)
    email_outbox.schedule_reminders(db, appt, person(1), person(2))
    assert sorted(r.user_id for r in db.rows) == [1, 2] and {r.kind for r in db.rows} == {"appointment_reminder"}
    for row in db.rows:
        assert row.send_after == appt.date - timedelta(minutes=5)
        assert row.expires_at == row.send_after + timedelta(minutes=3)
        assert row.context["start_iso"] == appt.date.isoformat() and row.appointment_id == 7


def test_no_reminder_when_the_booking_is_less_than_fifteen_minutes_ahead():
    db = QueueDb()
    email_outbox.schedule_reminders(db, appointment(10), person(1), person(2))
    assert db.rows == []


def test_a_person_who_turned_reminders_off_gets_none_and_the_other_still_does():
    db = QueueDb()
    email_outbox.schedule_reminders(db, appointment(120), person(1, email_reminders=False), person(2))
    assert [r.user_id for r in db.rows] == [2]


@pytest.mark.parametrize("fields", [{"is_email_verified": False}, {"is_active": False}, {"email": ""}])
def test_an_address_that_is_not_verified_and_active_gets_nothing(fields):
    db = QueueDb()
    email_outbox.schedule_reminders(db, appointment(120), person(1, **fields), person(2, **fields))
    assert db.rows == []


def test_the_same_reminder_is_never_queued_twice():
    db, appt = QueueDb(), appointment(120)
    email_outbox.schedule_reminders(db, appt, person(1), person(2))
    email_outbox.schedule_reminders(db, appt, person(1), person(2))
    assert len(db.rows) == 2


def test_a_moved_appointment_gets_a_new_reminder_key():
    db, appt = QueueDb(), appointment(120)
    email_outbox.schedule_reminders(db, appt, person(1), person(2))
    appt.date += timedelta(days=1)
    email_outbox.schedule_reminders(db, appt, person(1), person(2))
    assert len(db.rows) == 4


def test_the_reminder_lead_time_is_a_setting(monkeypatch):
    monkeypatch.setattr(email_outbox, "settings", replace(settings, email_reminder_minutes=30))
    db, appt = QueueDb(), appointment(240)
    email_outbox.schedule_reminders(db, appt, person(1), person(2))
    assert db.rows[0].send_after == appt.date - timedelta(minutes=30) and db.rows[0].context["minutes"] == 30


# --- the tokens ----------------------------------------------------------------------------------------


def test_a_secret_is_stored_as_a_keyed_hash_bound_to_its_purpose_and_user():
    one = auth_tokens.fingerprint("reset_password", "123456", 1)
    assert len(one) == 64 and "123456" not in one
    assert one == auth_tokens.fingerprint("reset_password", "123456", 1)
    assert one != auth_tokens.fingerprint("reset_password", "123456", 2)  # another user's code is not this one
    assert one != auth_tokens.fingerprint("verify_email", "123456", 1)  # another purpose is not this one
    assert one != auth_tokens.fingerprint("reset_password", "123457", 1)


def test_the_limits_are_the_documented_ones():
    assert (
        auth_tokens.RESET_MINUTES,
        auth_tokens.MAX_ATTEMPTS,
        auth_tokens.COOLDOWN_SECONDS,
        auth_tokens.MAX_PER_HOUR,
    ) == (10, 5, 60, 3)
