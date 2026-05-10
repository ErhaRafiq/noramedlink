from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Appointment, Payment, User
from schemas import PaymentCreate, PaymentOut, PaymentUpdate


router = APIRouter(prefix="/payments", tags=["payments"])

WALLET_METHODS = {"JAZZCASH", "EASYPAISA", "NAYAPAY"}
PAYMENT_METHODS = WALLET_METHODS | {"CARD", "RAAST", "CASH"}
PAYMENT_STATUSES = {"PENDING", "SUCCESS", "FAILED", "REFUNDED", "PAY_ON_VISIT"}


def create_reference() -> str:
    return f"NML-{uuid4().hex[:12].upper()}"


def create_invoice_number() -> str:
    return f"INV-{uuid4().hex[:10].upper()}"


def payment_to_out(payment: Payment) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        user_id=payment.user_id,
        appointment_id=payment.appointment_id,
        amount=payment.amount,
        method=payment.method,
        purpose=payment.purpose,
        status=payment.status,
        phone=payment.phone,
        reference=payment.reference,
        transaction_id=payment.transaction_id,
        invoice_number=payment.invoice_number,
        invoice_url=payment.invoice_url,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


@router.get("", response_model=list[PaymentOut])
def list_payments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payments = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .limit(100)
        .all()
    )
    return [payment_to_out(payment) for payment in payments]


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(payload: PaymentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    method = payload.method.strip().upper()
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported payment method.")

    phone = payload.phone.strip() if payload.phone else None
    if method in WALLET_METHODS and not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number is required for wallet payments.")

    appointment = None
    if payload.appointment_id:
        appointment = (
            db.query(Appointment)
            .filter(Appointment.id == payload.appointment_id, Appointment.user_id == current_user.id)
            .first()
        )
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found for this user.")

    payment_status = "SUCCESS" if method in WALLET_METHODS else "PAY_ON_VISIT" if method == "CASH" else "PENDING"
    payment = Payment(
        user_id=current_user.id,
        appointment_id=appointment.id if appointment else None,
        amount=payload.amount,
        method=method,
        purpose=payload.purpose.strip(),
        phone=phone,
        reference=create_reference(),
        invoice_number=create_invoice_number(),
        status=payment_status,
    )
    if appointment and payment_status == "SUCCESS":
        appointment.payment_status = "SUCCESS"

    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment_to_out(payment)


@router.put("/{payment_id}", response_model=PaymentOut)
def update_payment(
    payment_id: int,
    payload: PaymentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == current_user.id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")

    if payload.status is not None:
        normalized_status = payload.status.strip().upper()
        if normalized_status not in PAYMENT_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment status.")
        payment.status = normalized_status
        if payment.appointment_id:
            appointment = db.get(Appointment, payment.appointment_id)
            if appointment:
                appointment.payment_status = normalized_status
    if payload.transaction_id is not None:
        payment.transaction_id = payload.transaction_id.strip() or None
    if payload.invoice_url is not None:
        payment.invoice_url = payload.invoice_url.strip() or None

    db.commit()
    db.refresh(payment)
    return payment_to_out(payment)
