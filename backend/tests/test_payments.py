"""Stripe payments (services/payments.py): only a correctly signed webhook for the right amount
marks a payment paid. No network: signatures are made here with a test secret."""

import hashlib
import hmac
import json
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from config import settings
from services import payments
from services.payments import PaymentError

SECRET = "whsec_test_only"


def signed(payload: bytes, secret: str = SECRET, at: int | None = None) -> str:
    timestamp = at if at is not None else int(time.time())
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setattr(payments, "settings", replace(settings, stripe_webhook_secret=SECRET, stripe_secret_key=""))


def event_bytes(**fields) -> bytes:
    return json.dumps({"id": "evt_1", "type": "checkout.session.completed", **fields}).encode()


def test_a_correctly_signed_event_is_accepted(webhook_secret):
    payload = event_bytes()
    assert payments.verified_event(payload, signed(payload))["id"] == "evt_1"


@pytest.mark.parametrize(
    "header",
    [None, "", "t=1,v1=deadbeef", signed(b"{}"), signed(event_bytes(), secret="whsec_other")],
)
def test_a_missing_wrong_or_mismatched_signature_is_refused(webhook_secret, header):
    with pytest.raises(PaymentError) as caught:
        payments.verified_event(event_bytes(), header)
    assert caught.value.status_code == 400


def test_an_old_signature_is_refused(webhook_secret):
    payload = event_bytes()
    with pytest.raises(PaymentError):
        payments.verified_event(payload, signed(payload, at=int(time.time()) - 3600))


def test_webhooks_are_off_without_a_secret():
    payload = event_bytes()
    with pytest.raises(PaymentError) as caught:
        payments.verified_event(payload, signed(payload))
    assert caught.value.status_code == 503


def test_checkout_is_off_without_a_stripe_key():
    assert payments.online_payment_enabled() is False


class FakeDb:
    def __init__(self, appointment=None):
        self.appointment = appointment

    def get(self, _model, _id):
        return self.appointment


def pending(amount=1500):
    return SimpleNamespace(
        id=7, amount=amount, currency="pkr", status="PENDING", appointment_id=3, paid_at=None, transaction_id=None
    )


def session(**fields):
    return {
        "id": "cs_1",
        "payment_status": "paid",
        "amount_total": 150_000,
        "currency": "pkr",
        "payment_intent": "pi_1",
        **fields,
    }


def test_a_paid_session_for_the_right_amount_marks_payment_and_appointment_paid():
    appointment = SimpleNamespace(payment_status="PENDING")
    payment = pending()
    assert payments._apply(FakeDb(appointment), payment, "checkout.session.completed", session()) == "paid"
    assert payment.status == "PAID" and payment.paid_at is not None and payment.transaction_id == "pi_1"
    assert appointment.payment_status == "PAID"


@pytest.mark.parametrize(
    ("fields", "outcome"),
    [
        ({"amount_total": 100}, "amount mismatch"),
        ({"currency": "usd"}, "amount mismatch"),
        ({"payment_status": "unpaid"}, "awaiting payment"),
    ],
)
def test_a_wrong_amount_currency_or_unpaid_session_changes_nothing(fields, outcome):
    appointment = SimpleNamespace(payment_status="PENDING")
    payment = pending()
    assert payments._apply(FakeDb(appointment), payment, "checkout.session.completed", session(**fields)) == outcome
    assert payment.status == "PENDING" and appointment.payment_status == "PENDING"


def test_expired_and_failed_sessions_never_undo_a_paid_payment():
    payment = pending()
    assert payments._apply(FakeDb(), payment, "checkout.session.expired", session()) == "expired"
    assert payment.status == "EXPIRED"
    paid = pending()
    paid.status = "PAID"
    assert payments._apply(FakeDb(), paid, "checkout.session.async_payment_failed", session()) == "already paid"
    assert paid.status == "PAID"


def test_events_we_do_not_handle_are_ignored():
    assert payments.apply_event(FakeDb(), {"id": "evt_2", "type": "charge.refunded"}) == "ignored"


def test_pkr_is_sent_to_stripe_in_paisa():
    assert payments.minor_units(1500) == 150_000
