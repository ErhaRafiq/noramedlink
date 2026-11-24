"""In-app notifications for a home visit. Told once each (dedupe keys); none holds the reason, the address or any
record content: only who, what happened and what to do next."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models import HomeVisitRequest
from services import notifications
from services.symptom_checker import EMERGENCY_NOTICE

PATIENT_LINK = "/emergency"
DOCTOR_LINK = "/dashboard/doctor#home-visits"


def _dr(name: str) -> str:
    return notifications._dr(name)


def _key(request: HomeVisitRequest, event: str, doctor_id: int | None = None) -> str:
    return f"hv:{request.id}:{event}" + (f":{doctor_id}" if doctor_id else "")


def offered(db: Session, request: HomeVisitRequest, doctor_id: int) -> None:
    notifications.add(
        db, doctor_id, "home_visit_offered", "A home visit request is waiting",
        "A patient near you asked for a home visit. Open it and accept or decline before the time runs out.",
        link=DOCTOR_LINK, dedupe_key=_key(request, "offered", doctor_id),
    )  # fmt: skip


def withdrawn(db: Session, request: HomeVisitRequest, doctor_id: int, why: str) -> None:
    notifications.add(
        db, doctor_id, "home_visit_withdrawn", "A home visit request is no longer waiting",
        why, link=DOCTOR_LINK, dedupe_key=_key(request, "withdrawn", doctor_id),
    )  # fmt: skip


def to_patient(db: Session, request: HomeVisitRequest, event: str, title: str, body: str) -> None:
    notifications.add(
        db, request.patient_id, f"home_visit_{event}", title, body,
        link=PATIENT_LINK, dedupe_key=_key(request, event),
    )  # fmt: skip


def accepted(db: Session, request: HomeVisitRequest, doctor_name: str) -> None:
    to_patient(db, request, "accepted", "A doctor accepted your home visit",
               f"{_dr(doctor_name)} accepted your request. You will be told when they set out.")  # fmt: skip


def en_route(db: Session, request: HomeVisitRequest, doctor_name: str, eta: int | None) -> None:
    estimate = f" Their own estimate is about {eta} minutes; it is not a tracked time." if eta else ""
    to_patient(db, request, "en_route", "Your doctor is on the way", f"{_dr(doctor_name)} has set out.{estimate}")


def arrived(db: Session, request: HomeVisitRequest, doctor_name: str) -> None:
    to_patient(db, request, "arrived", "Your doctor has arrived", f"{_dr(doctor_name)} marked the visit as started.")


def completed(db: Session, request: HomeVisitRequest, doctor_name: str) -> None:
    to_patient(db, request, "completed", "Your home visit is finished",
               f"{_dr(doctor_name)} finished the visit. A summary will be saved to your record.")  # fmt: skip


def closed(db: Session, request: HomeVisitRequest, doctor_name: str) -> None:
    to_patient(db, request, "closed", "Your visit summary is saved",
               f"The summary from {_dr(doctor_name)} is saved in your home visits.")  # fmt: skip


def declined(db: Session, request: HomeVisitRequest) -> None:
    to_patient(db, request, "declined", "The doctor could not take your request",
               "The doctor you chose declined. You can send a new request.")  # fmt: skip


def expired(db: Session, request: HomeVisitRequest) -> None:
    to_patient(db, request, "expired", "Your home visit request was not answered",
               "The doctor you chose did not answer in time. You can send a new request.")  # fmt: skip


def no_doctor_found(db: Session, request: HomeVisitRequest) -> None:
    to_patient(db, request, "no_doctor", "No doctor was found for a home visit",
               "No doctor near you could take this request. You can try again later or book a clinic appointment.")  # fmt: skip


def cancelled_by_doctor(db: Session, request: HomeVisitRequest, doctor_name: str) -> None:
    to_patient(db, request, "cancelled", "Your home visit was cancelled",
               f"{_dr(doctor_name)} cancelled the visit. You can send a new request.")  # fmt: skip


def cancelled_by_patient(db: Session, request: HomeVisitRequest) -> None:
    if request.doctor_id:
        notifications.add(
            db, request.doctor_id, "home_visit_cancelled", "A home visit was cancelled",
            "The patient cancelled the home visit.", link=DOCTOR_LINK, dedupe_key=_key(request, "cancelled"),
        )  # fmt: skip


def referred_emergency(db: Session, request: HomeVisitRequest) -> None:
    to_patient(db, request, "emergency", "Please get emergency care now", EMERGENCY_NOTICE)
