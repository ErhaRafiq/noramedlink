"""Consultation payments through Stripe Checkout (Stripe's hosted payment page).

- The amount always comes from the doctor's consultation fee on the server, never from the browser.
- A payment becomes PAID only when Stripe's signed webhook says its Checkout session was paid, for
  the amount and currency we asked for. Each Stripe event is applied once (stripe_events).
- Cancelling a paid appointment asks Stripe for a full refund (REFUND_PENDING). The payment becomes
  REFUNDED only when Stripe's signed webhook confirms it (charge.refunded), or REFUND_FAILED on refund.failed.
- Stripe sees only the doctor's name and the amount: no diagnosis, reason or patient details.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from models import Appointment, Payment, StripeEvent, User
from schemas import PaymentOut
from services import notifications

log = logging.getLogger("nora.payments")

MIN_FEE = 200  # PKR; Stripe's smallest charge is about USD 0.50
MAX_FEE = 100_000
CHECKOUT_MINUTES = 30  # how long the hosted page stays open (Stripe allows 30 minutes to 24 hours)
METHOD = "STRIPE_CARD"
PENDING, PAID, FAILED, EXPIRED = "PENDING", "PAID", "FAILED", "EXPIRED"
REFUND_PENDING, REFUNDED, REFUND_FAILED = "REFUND_PENDING", "REFUNDED", "REFUND_FAILED"
PAID_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
REFUND_EVENTS = {"charge.refunded", "refund.failed"}
HANDLED_EVENTS = PAID_EVENTS | REFUND_EVENTS | {"checkout.session.async_payment_failed", "checkout.session.expired"}


class PaymentError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def online_payment_enabled() -> bool:
    return bool(settings.stripe_secret_key)


def minor_units(amount: int) -> int:
    """Stripe counts PKR in paisa (two decimals)."""
    return amount * 100


def to_out(payment: Payment) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        user_id=payment.user_id,
        appointment_id=payment.appointment_id,
        amount=payment.amount,
        currency=payment.currency,
        method=payment.method,
        purpose=payment.purpose,
        status=payment.status,
        reference=payment.reference,
        invoice_number=payment.invoice_number,
        paid_at=payment.paid_at,
        refunded_at=payment.refunded_at,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


def doctor_fee(db: Session, appointment: Appointment) -> tuple[User | None, int | None]:
    doctor = db.get(User, appointment.doctor_id) if appointment.doctor_id else None
    profile = doctor.doctor_profile if doctor else None
    return doctor, profile.consultation_fee if profile else None


def _client() -> stripe.StripeClient:
    return stripe.StripeClient(settings.stripe_secret_key)


def _open_session_url(db: Session, appointment: Appointment, fee: int) -> tuple[Payment, str] | None:
    """A Checkout page already open for this appointment at the current fee, so paying twice is
    not possible by clicking twice."""
    payment = (
        db.query(Payment)
        .filter(
            Payment.appointment_id == appointment.id,
            Payment.status == PENDING,
            Payment.stripe_session_id.is_not(None),
            Payment.amount == fee,
        )
        .order_by(Payment.created_at.desc())
        .first()
    )
    if payment is None:
        return None
    try:
        session = _client().v1.checkout.sessions.retrieve(payment.stripe_session_id)
    except stripe.StripeError:
        return None
    return (payment, session.url) if session.status == "open" and session.url else None


def start_checkout(db: Session, patient: User, appointment_id: int) -> tuple[Payment, str]:
    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.user_id == patient.id).first()
    )
    if appointment is None:
        raise PaymentError(404, "Appointment not found.")
    if appointment.status.upper() == "CANCELLED":
        raise PaymentError(409, "This appointment was cancelled.")
    if appointment.payment_status.upper() == PAID:
        raise PaymentError(409, "This appointment is already paid.")
    doctor, fee = doctor_fee(db, appointment)
    if doctor is None or not fee:
        raise PaymentError(
            409, "The doctor has not set a consultation fee yet, so this appointment cannot be paid online."
        )
    if not online_payment_enabled():
        raise PaymentError(503, "Online payment is not set up on this server.")

    reused = _open_session_url(db, appointment, fee)
    if reused:
        return reused

    payment = Payment(
        user_id=patient.id,
        appointment_id=appointment.id,
        amount=fee,
        currency=settings.payment_currency,
        method=METHOD,
        purpose=f"Consultation with {doctor.full_name}"[:160],
        status=PENDING,
        reference=f"NML-{uuid4().hex[:12].upper()}",
        invoice_number=f"INV-{uuid4().hex[:10].upper()}",
    )
    db.add(payment)
    db.flush()
    origin = settings.frontend_origin.rstrip("/")
    metadata = {"payment_id": str(payment.id), "appointment_id": str(appointment.id)}
    try:
        session = _client().v1.checkout.sessions.create(
            {
                "mode": "payment",
                "line_items": [
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": payment.currency,
                            "unit_amount": minor_units(fee),
                            "product_data": {
                                "name": f"Consultation with {doctor.full_name} (appointment #{appointment.id})"
                            },
                        },
                    }
                ],
                "client_reference_id": payment.reference,
                "metadata": metadata,
                "payment_intent_data": {"metadata": metadata},
                "success_url": f"{origin}/payments/result?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": f"{origin}/payments?appointmentId={appointment.id}&cancelled=1",
                "expires_at": int((datetime.now(UTC) + timedelta(minutes=CHECKOUT_MINUTES)).timestamp()),
            },
            {"idempotency_key": payment.reference},
        )
    except stripe.StripeError as exc:
        db.rollback()
        log.warning("Stripe Checkout could not be created (%s)", type(exc).__name__)
        raise PaymentError(502, "The payment page could not be opened. Please try again.") from exc
    payment.stripe_session_id = session.id
    db.commit()
    db.refresh(payment)
    return payment, session.url


def payment_for_session(db: Session, patient: User, session_id: str) -> Payment:
    payment = db.query(Payment).filter(Payment.stripe_session_id == session_id, Payment.user_id == patient.id).first()
    if payment is None:
        raise PaymentError(404, "Payment not found.")
    return payment


def verified_event(payload: bytes, signature: str | None) -> dict:
    """The event, only if Stripe signed it with our webhook secret (and recently: 5-minute tolerance)."""
    if not settings.stripe_webhook_secret:
        raise PaymentError(503, "Stripe webhooks are not set up on this server.")
    try:
        stripe.WebhookSignature.verify_header(payload, signature, settings.stripe_webhook_secret, tolerance=300)
        return json.loads(payload)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise PaymentError(400, "Invalid Stripe signature.") from exc


def _apply(db: Session, payment: Payment, kind: str, session: dict) -> str:
    if kind in PAID_EVENTS:
        if session.get("payment_status") != "paid":
            return "awaiting payment"
        if session.get("amount_total") != minor_units(payment.amount) or (
            (session.get("currency") or "").lower() != payment.currency
        ):
            log.warning("Stripe session amount does not match payment %s; not marked paid", payment.id)
            return "amount mismatch"
        payment.status = PAID
        payment.paid_at = datetime.now(UTC)
        payment.transaction_id = session.get("payment_intent")
        appointment = db.get(Appointment, payment.appointment_id) if payment.appointment_id else None
        if appointment is not None:
            appointment.payment_status = PAID
        return "paid"
    if payment.status == PAID:
        return "already paid"
    payment.status = FAILED if kind == "checkout.session.async_payment_failed" else EXPIRED
    return payment.status.lower()


def _apply_refund(db: Session, payment: Payment, kind: str, obj: dict) -> str:
    appointment = db.get(Appointment, payment.appointment_id) if payment.appointment_id else None
    if payment.status == REFUNDED:
        return "already refunded"
    if kind == "charge.refunded":
        if (obj.get("amount_refunded") or 0) < minor_units(payment.amount):
            return "partial refund ignored"
        payment.status = REFUNDED
        payment.refunded_at = datetime.now(UTC)
        outcome = "refunded"
    else:  # refund.failed
        payment.status = REFUND_FAILED
        outcome = "refund failed"
    if appointment is not None:
        appointment.payment_status = payment.status
    return outcome


def refund_for_cancellation(db: Session, appointment: Appointment) -> Payment | None:
    """A cancelled appointment that was paid gets its money back in full (the fee was never earned).

    Stripe is asked for the refund here; the payment only becomes REFUNDED when Stripe's webhook says so.
    If Stripe cannot be reached the cancellation still stands and the payment is marked REFUND_FAILED,
    so it is visible and nobody is told the money is on its way when it is not."""
    payment = db.query(Payment).filter(Payment.appointment_id == appointment.id, Payment.status == PAID).first()
    if payment is None:
        return None
    try:
        if not online_payment_enabled() or not payment.transaction_id:
            raise PaymentError(503, "Online refunds are not set up on this server.")
        refund = _client().v1.refunds.create(
            {
                "payment_intent": payment.transaction_id,
                "metadata": {"payment_id": str(payment.id), "appointment_id": str(appointment.id)},
            },
            {"idempotency_key": f"refund-{payment.reference}"},
        )
        payment.stripe_refund_id = refund.id
        payment.status = REFUND_PENDING
        title, body = (
            "Refund requested",
            (
                f"Your appointment was cancelled, so {payment.amount:,} {payment.currency.upper()} is being refunded to "
                "your card. Your bank may take several days to show it."
            ),
        )
    except (stripe.StripeError, PaymentError) as exc:
        log.warning("Refund for payment %s could not be requested (%s)", payment.id, type(exc).__name__)
        payment.status = REFUND_FAILED
        title, body = (
            "Refund needs attention",
            (
                "Your appointment was cancelled, but the refund could not be requested automatically. "
                "Please contact support with your payment reference " + payment.reference + "."
            ),
        )
    appointment.payment_status = payment.status
    notifications.add(db, payment.user_id, "payment_refund", title, body, appointment.id)
    return payment


def apply_event(db: Session, event: dict) -> str:
    """Apply one verified Stripe event; returns what happened (for the log and the response)."""
    event_id, kind = event.get("id"), event.get("type")
    if kind not in HANDLED_EVENTS or not event_id:
        return "ignored"
    if db.get(StripeEvent, event_id) is not None:
        return "duplicate"
    session = (event.get("data") or {}).get("object") or {}
    if kind in REFUND_EVENTS:
        intent = session.get("payment_intent")
        payment = db.query(Payment).filter(Payment.transaction_id == intent).first() if intent else None
        outcome = _apply_refund(db, payment, kind, session) if payment is not None else "unknown payment"
    else:
        payment = db.query(Payment).filter(Payment.stripe_session_id == session.get("id")).first()
        outcome = _apply(db, payment, kind, session) if payment is not None else "unknown session"
    db.add(StripeEvent(id=event_id, type=kind))
    try:
        db.commit()
    except IntegrityError:  # the same event delivered twice at once
        db.rollback()
        return "duplicate"
    log.info("Stripe %s: %s", kind, outcome)
    return outcome
