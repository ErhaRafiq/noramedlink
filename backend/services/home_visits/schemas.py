"""Request and response models of the home-visit API (Module 6)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PHONE_PATTERN = r"^[0-9+()\- ]{7,20}$"


class Location(BaseModel):
    """Where the patient is: from the browser (with its accuracy) or typed. Never geocoded."""

    latitude: float
    longitude: float
    accuracy_m: float | None = None
    source: Literal["device", "manual"]


class RequestCheck(BaseModel):
    """What the emergency gate and the doctor search read: the reason, the checklist and the place."""

    reason: str = Field(max_length=1000)
    checklist: dict[str, bool] = Field(default_factory=dict)
    location: Location

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class HomeVisitCreate(RequestCheck):
    mode: Literal["auto", "choose"] = "auto"
    doctor_id: int | None = Field(default=None, ge=1, description="Only for mode 'choose'.")
    phone: str = Field(pattern=PHONE_PATTERN)
    address_text: str = Field(min_length=5, max_length=300)

    @field_validator("address_text")
    @classmethod
    def _strip_address(cls, value: str) -> str:
        return value.strip()


class CancelIn(BaseModel):
    """Why a doctor cancels: a fixed choice (the audit log keeps no free text)."""

    reason: Literal["unwell", "urgent_elsewhere", "too_far", "patient_unreachable", "other"]


class EnRouteIn(BaseModel):
    eta_minutes: int | None = Field(default=None, ge=1, le=240)


class CloseIn(BaseModel):
    findings: str = Field(min_length=3, max_length=2000)
    advice: str = Field(min_length=3, max_length=2000)
    follow_up: str = Field(min_length=2, max_length=1000)


class SettingsIn(BaseModel):
    enabled: bool
    radius_km: float | None = Field(default=None, ge=1, le=50)
    latitude: float | None = None
    longitude: float | None = None


class SettingsOut(BaseModel):
    enabled: bool
    radius_km: float | None
    latitude: float | None
    longitude: float | None
    note: str


class DoctorChoice(BaseModel):
    doctor_id: int
    name: str
    specialty: str
    hospital: str | None
    distance: str  # "straight-line distance, about 3 km"
    availability: Literal["now", "soon"]


class DoctorPublic(BaseModel):
    id: int
    name: str
    specialty: str
    hospital: str | None


class Eta(BaseModel):
    minutes: int
    label: str = "doctor's estimate"


class Summary(BaseModel):
    findings: str
    advice: str
    follow_up: str


class PatientVisit(BaseModel):
    """What the patient sees of their own request. No coordinates; the doctor appears only once chosen or matched."""

    id: int
    status: str
    status_label: str
    mode: str
    reason: str
    specialty: str
    address_text: str
    location: str  # "accurate to about 120 m" or "Typed by you"
    doctor: DoctorPublic | None
    offered_to_count: int
    offer_expires_at: datetime | None
    eta: Eta | None
    summary: Summary | None
    emergency_notice: str | None
    created_at: datetime
    accepted_at: datetime | None
    en_route_at: datetime | None
    arrived_at: datetime | None
    completed_at: datetime | None
    closed_at: datetime | None
    ended_at: datetime | None


class ChecklistQuestion(BaseModel):
    id: str
    question: str


class Checklist(BaseModel):
    notice: str
    questions: list[ChecklistQuestion]


class VisitRef(BaseModel):
    """The answer to a doctor's decline or emergency referral: it carries no patient details."""

    id: int
    status: str
    message: str = ""


class LegacyRequest(BaseModel):
    """A request recorded before the home-visit service (old emergency_bookings): read-only, shown as it was."""

    id: int
    created_at: datetime
    symptoms: str
    address: str
    note: str = "Recorded before the home-visit service. No doctor was assigned."


class AdminVisit(PatientVisit):
    """An administrator's view (audited): includes the phone and the coordinates."""

    patient_id: int
    doctor_id: int | None
    phone: str
    latitude: float
    longitude: float


class DoctorOffer(BaseModel):
    """A request waiting for this doctor's answer: no name, phone or address until they accept."""

    id: int
    reason: str
    specialty: str
    distance: str
    expires_at: datetime
    created_at: datetime


class PatientContact(BaseModel):
    """The patient as the matched doctor sees them. Phone, address and place are shown only while the visit is
    live; once it has ended (closed, cancelled, referred) only the name is left."""

    name: str
    phone: str | None
    address_text: str | None
    latitude: float | None
    longitude: float | None
    location: str | None


class DoctorVisit(BaseModel):
    """A visit this doctor accepted: the patient's contact details and place are shown now."""

    id: int
    status: str
    status_label: str
    reason: str
    specialty: str
    patient: PatientContact
    distance: str
    eta: Eta | None
    summary: Summary | None
    created_at: datetime
    accepted_at: datetime | None
    en_route_at: datetime | None
    arrived_at: datetime | None
    completed_at: datetime | None
    closed_at: datetime | None
    ended_at: datetime | None


class Outcome(BaseModel):
    """The answer to sending a request or searching: emergency and not_suitable save nothing."""

    outcome: Literal["emergency", "not_suitable", "created", "doctors"]
    message: str = ""
    red_flags: list[str] = Field(default_factory=list)
    visit: PatientVisit | None = None
    doctors: list[DoctorChoice] = Field(default_factory=list)
    specialty: str | None = None
