"""The life of one home-visit request, and the only function that decides which step may follow which.

offered -> accepted -> en_route -> arrived -> completed -> closed, plus the endings cancelled, declined,
no_doctor_found, expired and referred_emergency. Every step has its own timestamp column on the request.
"""

from __future__ import annotations

OFFERED, ACCEPTED, EN_ROUTE, ARRIVED, COMPLETED, CLOSED = (
    "offered", "accepted", "en_route", "arrived", "completed", "closed",
)  # fmt: skip
CANCELLED, DECLINED, NO_DOCTOR_FOUND, EXPIRED, REFERRED_EMERGENCY = (
    "cancelled", "declined", "no_doctor_found", "expired", "referred_emergency",
)  # fmt: skip

STATES = (
    OFFERED, ACCEPTED, EN_ROUTE, ARRIVED, COMPLETED, CLOSED,
    CANCELLED, DECLINED, NO_DOCTOR_FOUND, EXPIRED, REFERRED_EMERGENCY,
)  # fmt: skip
TERMINAL = frozenset({CLOSED, CANCELLED, DECLINED, NO_DOCTOR_FOUND, EXPIRED, REFERRED_EMERGENCY})
ACTIVE = frozenset(STATES) - TERMINAL

PATIENT, DOCTOR, SYSTEM = "patient", "doctor", "system"

# (from, to) -> who may make the step. A doctor can refer to emergency care from any live state.
TRANSITIONS: dict[tuple[str, str], frozenset[str]] = {
    (OFFERED, ACCEPTED): frozenset({DOCTOR}),
    (OFFERED, DECLINED): frozenset({DOCTOR}),
    (OFFERED, EXPIRED): frozenset({SYSTEM}),
    (OFFERED, NO_DOCTOR_FOUND): frozenset({SYSTEM}),
    (OFFERED, CANCELLED): frozenset({PATIENT}),
    (ACCEPTED, EN_ROUTE): frozenset({DOCTOR}),
    (ACCEPTED, CANCELLED): frozenset({PATIENT, DOCTOR}),
    (EN_ROUTE, ARRIVED): frozenset({DOCTOR}),
    (EN_ROUTE, CANCELLED): frozenset({PATIENT, DOCTOR}),
    (ARRIVED, COMPLETED): frozenset({DOCTOR}),
    (ARRIVED, CANCELLED): frozenset({DOCTOR}),
    (COMPLETED, CLOSED): frozenset({DOCTOR}),
    **{(state, REFERRED_EMERGENCY): frozenset({DOCTOR}) for state in (OFFERED, ACCEPTED, EN_ROUTE, ARRIVED, COMPLETED)},
}

# The request column that records when each state was reached.
TIMESTAMP_FIELD = {
    OFFERED: "created_at",
    ACCEPTED: "accepted_at",
    EN_ROUTE: "en_route_at",
    ARRIVED: "arrived_at",
    COMPLETED: "completed_at",
    CLOSED: "closed_at",
    CANCELLED: "ended_at",
    DECLINED: "ended_at",
    NO_DOCTOR_FOUND: "ended_at",
    EXPIRED: "ended_at",
    REFERRED_EMERGENCY: "ended_at",
}

LABELS = {
    OFFERED: "Waiting for a doctor to accept",
    ACCEPTED: "Doctor accepted",
    EN_ROUTE: "Doctor is on the way",
    ARRIVED: "Doctor has arrived",
    COMPLETED: "Visit finished",
    CLOSED: "Visit closed and saved to the record",
    CANCELLED: "Cancelled",
    DECLINED: "Doctor declined",
    NO_DOCTOR_FOUND: "No doctor found",
    EXPIRED: "No answer in time",
    REFERRED_EMERGENCY: "Referred to emergency care",
}


class InvalidTransition(ValueError):
    """The step is not allowed from the current state, or not by this role."""


def can_transition(current: str, target: str, actor: str) -> bool:
    return actor in TRANSITIONS.get((current, target), frozenset())


def transition(current: str, target: str, actor: str) -> str:
    """The new state, or InvalidTransition. The one place the order of a visit is enforced."""
    if current not in STATES or target not in STATES:
        raise InvalidTransition(f"Unknown state: {current!r} -> {target!r}.")
    if current in TERMINAL:
        raise InvalidTransition(f"This visit is already {LABELS[current].lower()}.")
    if (current, target) not in TRANSITIONS:
        raise InvalidTransition(f"A visit cannot go from {current} to {target}.")
    if actor not in TRANSITIONS[(current, target)]:
        raise InvalidTransition(f"A {actor} cannot move a visit from {current} to {target}.")
    return target
