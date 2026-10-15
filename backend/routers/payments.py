"""Consultation payments: the patient's list, Stripe Checkout, and Stripe's webhook.

The rules live in services/payments.py. The webhook is called by Stripe, not by a signed-in user;
it is trusted only when Stripe's signature checks out.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database import get_db
from dependencies import get_current_user, require_patient
from models import Payment, User
from pagination import Page, PageParams, page_params, paginate
from rate_limit import PAYMENT_LIMIT, limiter
from schemas import CheckoutOut, CheckoutRequest, PaymentOut, WebhookAck
from services import payments
from services.payments import PaymentError

router = APIRouter(prefix="/payments", tags=["payments"])


def _http(error: PaymentError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


@router.get("", response_model=Page[PaymentOut])
def list_payments(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
    )
    return paginate(query, params, payments.to_out)


@router.post("/checkout", response_model=CheckoutOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(PAYMENT_LIMIT)
def start_checkout(
    request: Request,
    payload: CheckoutRequest,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Open Stripe's hosted payment page for one of the patient's own appointments, at the doctor's fee."""
    try:
        payment, url = payments.start_checkout(db, current_user, payload.appointment_id)
    except PaymentError as error:
        raise _http(error) from error
    return CheckoutOut(payment=payments.to_out(payment), checkout_url=url)


@router.get("/session/{session_id}", response_model=PaymentOut)
def payment_for_session(session_id: str, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """The payment behind a Checkout session, for the page Stripe sends the patient back to."""
    try:
        return payments.to_out(payments.payment_for_session(db, current_user, session_id))
    except PaymentError as error:
        raise _http(error) from error


@router.post("/stripe/webhook", response_model=WebhookAck)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    payload = await request.body()
    try:
        event = payments.verified_event(payload, stripe_signature)
    except PaymentError as error:
        raise _http(error) from error
    # The database work is synchronous: keep it off the event loop.
    return WebhookAck(received=True, outcome=await run_in_threadpool(payments.apply_event, db, event))
