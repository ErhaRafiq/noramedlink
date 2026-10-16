from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Role = Literal["patient", "doctor", "admin"]


class UserOut(BaseModel):
    id: int
    full_name: str
    # Plain str: emails are validated on the way in. Re-validating stored values on
    # the way out turned an address the validator now rejects into a 500 on /auth/me.
    email: str
    role: Role
    phone: str
    is_email_verified: bool
    is_identity_verified: bool
    verification_status: str


class SignupRequest(BaseModel):
    role: Role
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(max_length=128)
    confirm_password: str
    phone: str = Field(min_length=7, max_length=40)
    cnic: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=30)
    pmdc_number: str | None = Field(default=None, max_length=80)
    specialization: str | None = Field(default=None, max_length=120)
    hospital_name: str | None = Field(default=None, max_length=180)
    admin_invite_code: str | None = Field(default=None, max_length=160)

    @field_validator("password")
    @classmethod
    def strong_password(cls, password: str) -> str:
        if len(password) < 8:
            raise ValueError("Weak password. Password must be at least 8 characters.")
        return password

    @field_validator("confirm_password")
    @classmethod
    def signup_passwords_match(cls, confirm_password: str, info):
        if info.data.get("password") != confirm_password:
            raise ValueError("Password and confirm password must match.")
        return confirm_password


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str  # the Next.js server keeps both in HttpOnly cookies; browsers never see them
    token_type: str = "bearer"
    user: UserOut


class MessageOut(BaseModel):
    message: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class VitalsOut(BaseModel):
    id: int
    user_id: int
    blood_pressure: str
    sugar_level: str
    created_at: datetime


class BasicVitalsCreate(BaseModel):
    """Blood pressure and sugar as free text (the /dashboard vitals form)."""

    blood_pressure: str = Field(min_length=1, max_length=80)
    sugar_level: str = Field(min_length=1, max_length=80)


class MedicationScheduleCreate(BaseModel):
    """Accepts the camelCase names the workspace sends."""

    model_config = {"populate_by_name": True}

    medicine_name: str = Field(min_length=1, max_length=160, alias="medicineName")
    dosage: str = Field(min_length=1, max_length=120)
    instructions: str | None = None
    start_date: date = Field(alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")


class MedicationScheduleOut(BaseModel):
    id: int
    patient_id: int
    medicine_name: str
    dosage: str
    instructions: str | None
    start_date: date | None
    end_date: date | None
    status: str
    created_at: datetime


class MedicineReminderCreate(BaseModel):
    """Accepts the camelCase names the workspace sends."""

    model_config = {"populate_by_name": True}

    medication_id: int = Field(alias="medicationId", gt=0)
    reminder_time: datetime = Field(alias="reminderTime")
    frequency: str = Field(min_length=1, max_length=120)


class MedicineReminderOut(BaseModel):
    id: int
    medication_id: int
    patient_id: int
    reminder_time: datetime
    frequency: str
    status: str
    taken_at: datetime | None
    skipped_at: datetime | None
    created_at: datetime
    updated_at: datetime
    medication: MedicationScheduleOut | None = None


class DailyVitalOut(BaseModel):
    """Latest vitals. Values that were not recorded are null, never estimated."""

    id: int
    patient_id: int
    blood_pressure_systolic: int
    blood_pressure_diastolic: int
    heart_rate: int | None
    spo2: int | None
    temperature: float | None
    sugar_level: float | None
    weight: float | None
    recorded_at: datetime
    created_at: datetime


class PatientReportOut(BaseModel):
    id: int
    patient_id: int
    department_id: int | None
    department_name: str
    department_slug: str
    category: str
    title: str
    original_file_name: str
    original_filename: str
    file_url: str
    stored_file_path: str
    # Short-lived signed link for the owning patient (or the embedded data: image).
    file_access_url: str | None = None
    file_type: str
    extracted_text: str | None
    formatted_text: str | None
    structured_data_json: dict[str, Any]
    summary: str | None
    extracted_entities: list[dict[str, Any]] = []
    rule_warnings: list[dict[str, Any]] = []
    validation_status: Literal["SAFE", "CAUTION", "HIGH_RISK"] | str = "SAFE"
    validation_results: dict[str, Any] = {}
    clinical_summary_json: dict[str, Any] = {}
    llm_self_check: dict[str, Any] = {}
    summary_source: str = "rule_based"
    upload_date: datetime
    updated_at: datetime
    ocr_status: str
    ocr_confidence: float | None
    ocr_raw_text: str | None
    ocr_cleaned_text: str | None
    possible_report_type: str | None
    detected_keywords: list[str]
    structured_sections: dict[str, str]
    ai_summary: str | None
    patient_summary: str | None = None
    # Who wrote patient_summary: "gemini", "openai", "groq" or "rule_based" (absent on older reports).
    patient_summary_source: str | None = None
    # Conditions the report mentions, with everyday names (mentioned in the report, not a diagnosis).
    conditions_mentioned: list[dict[str, Any]] = []


class DepartmentTileOut(BaseModel):
    id: int
    name: str
    slug: str
    icon: str | None
    description: str | None
    total_reports: int
    latest_upload_date: datetime | None
    preview_text: str | None
    health_status: str = "No reports"
    risk_level: Literal["None flagged", "Medium", "High", "Unknown"] | str = "Unknown"
    validation_status: Literal["SAFE", "CAUTION", "HIGH_RISK", "NOT_VALIDATED"] | str = "NOT_VALIDATED"


class PatientReportUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    department: str | None = Field(default=None, max_length=80)
    extracted_text: str | None = None
    formatted_text: str | None = None
    structured_data_json: dict[str, Any] | None = None


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=1)
    category: str | None = None


class SummaryResponse(BaseModel):
    summary: str
    method: Literal["gemini", "openai", "groq", "rule_based"]
    warning: str | None = None
    # From services/report_breakdown.py: values found, rule alerts (deterministic), next steps.
    key_findings: list[str] = Field(default_factory=list)
    risk_indicators: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class AppointmentCreate(BaseModel):
    # doctor_id must name a verified, active doctor, and `date` the start of one of that doctor's open
    # slots (GET /appointments/doctors/{id}/slots). The stored name and specialty come from the doctor's record.
    doctor_id: int
    date: datetime
    mode: Literal["in_clinic", "online", "home"] = "in_clinic"
    reason: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    patient_access_otp: str | None = Field(default=None, max_length=12)


class AppointmentUpdate(BaseModel):
    date: datetime | None = None
    status: str | None = Field(default=None, max_length=40)
    # Always refused (403): only Stripe's webhook marks an appointment paid (services/payments.py).
    payment_status: str | None = Field(default=None, max_length=40)
    notes: str | None = None


class AppointmentOut(BaseModel):
    id: int
    user_id: int
    doctor_id: int | None
    doctor_name: str
    date: datetime
    duration_minutes: int = 30
    mode: str = "in_clinic"
    status: str
    payment_status: str
    notes: str | None
    specialty: str | None = None
    reason: str | None = None
    # The doctor's current fee (whole PKR), what the patient pays online; None: not set.
    consultation_fee: int | None = None
    # Completed visits can be rated once; this says whether that has happened.
    reviewed: bool = False
    created_at: datetime
    updated_at: datetime


class AppointmentBookingResponse(BaseModel):
    message: str
    appointment: AppointmentOut
    dashboard_access_granted: bool = False


class AppointmentDoctorOut(BaseModel):
    id: int
    doctor_id: int | None
    name: str
    specialty: str
    location: str
    # Real values only: null / 0 / false mean "none yet", never an estimate.
    rating: float | None = None
    rating_count: int = 0
    available_today: bool = False
    next_available: datetime | None = None  # the first open slot in the next two weeks
    has_schedule: bool = False  # the doctor has published weekly availability
    consultation_fee: int | None = None  # whole PKR, set by the doctor; None: not set
    qualifications: str | None = None
    experience_years: int | None = None
    bio: str | None = None
    city: str | None = None
    languages: list[str] = Field(default_factory=list)
    consultation_modes: list[str] = Field(default_factory=list)  # online, in_clinic, home
    source: Literal["registered"] = "registered"


class PaymentOut(BaseModel):
    id: int
    user_id: int
    appointment_id: int | None
    amount: int  # whole units of `currency` (PKR)
    currency: str
    method: str
    purpose: str
    status: str  # PENDING, PAID, FAILED, EXPIRED, REFUND_PENDING, REFUNDED or REFUND_FAILED (older manual records may show other values)
    reference: str
    invoice_number: str | None
    paid_at: datetime | None
    refunded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CheckoutRequest(BaseModel):
    appointment_id: int


class CheckoutOut(BaseModel):
    payment: PaymentOut
    checkout_url: str  # Stripe's hosted payment page


class WebhookAck(BaseModel):
    received: bool
    outcome: str


# --- Clinical summary for doctors (ICSE) -------------------------------------------------------

RULE_BASED_NOTE = (
    "Built by fixed rules from the patient's records. Advisory, for physician review; "
    "conditions and allergies are as mentioned in reports, not confirmed diagnoses."
)


AI_WORDED_NOTE = (
    "Key findings: AI-generated wording of the rule-built findings below; advisory, verify with a clinician. "
    "Every flag and severity is set by fixed rules, not by the AI; conditions and allergies are as "
    "mentioned in reports, not confirmed diagnoses."
)


class ClinicalSummaryVersionMeta(BaseModel):
    version: int
    generated_at: datetime
    trigger: str
    source: str
    is_current: bool


class ClinicalSummaryVersionOut(ClinicalSummaryVersionMeta):
    patient_id: int
    summary_text: str
    content: dict[str, Any]
    note: str


class ClinicalSummaryStatusOut(BaseModel):
    patient_id: int
    summary: ClinicalSummaryVersionOut | None
    out_of_date: bool
    pending_change: str | None  # what changed since the current version, when it is out of date


class ClinicalSummaryRegenerateOut(BaseModel):
    summary: ClinicalSummaryVersionOut
    created: bool  # False: nothing had changed, so the current version stands


# --- Patient health flags (fixed rules, everyday words) ----------------------------------------


class HealthFlagReportOut(BaseModel):
    report_id: int
    report_title: str
    upload_date: datetime
    severity: Literal["HIGH_RISK", "CAUTION"]
    messages: list[str]


class HealthFlagConditionOut(BaseModel):
    name: str
    plain: str
    chronic: bool
    report_ids: list[int]


class HealthFlagsOut(BaseModel):
    reports: list[HealthFlagReportOut]
    high_risk_reports: int
    conditions_mentioned: list[HealthFlagConditionOut]


# --- Medication safety and prescribing (MSCIE, Module 4) ------------------------------------------


class PrescriptionItemIn(BaseModel):
    medicine: str = Field(min_length=2, max_length=160)
    dose: str | None = Field(default=None, max_length=60)
    frequency: str | None = Field(default=None, max_length=60)
    duration: str | None = Field(default=None, max_length=60)
    instructions: str | None = Field(default=None, max_length=500)
    # The medicine this one replaces, when the doctor chose a suggested alternative.
    replaced_medicine: str | None = Field(default=None, max_length=160)


class MedicationCheckRequest(BaseModel):
    items: list[PrescriptionItemIn] = Field(min_length=1, max_length=10)


class OverrideIn(BaseModel):
    alert_id: str = Field(min_length=1, max_length=300)
    justification: str = Field(min_length=20, max_length=1000)


class PrescriptionCreate(BaseModel):
    items: list[PrescriptionItemIn] = Field(min_length=1, max_length=10)
    overrides: list[OverrideIn] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)


class MedicineSearchOut(BaseModel):
    name: str
    generic: str
    brand: str | None
    classes: list[str]
    match: int


class MedicationCheckOut(BaseModel):
    """Alerts per proposed medicine (with rule, source and patient evidence), ranked alternatives,
    and the patient context the check used. Advisory: the physician decides."""

    context: dict[str, Any]
    items: list[dict[str, Any]]
    worst: str | None
    requires_justification: list[dict[str, Any]]
    note: str


class PrescriptionOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int | None
    doctor_name: str
    status: str
    notes: str | None
    created_at: datetime
    cancelled_at: datetime | None
    items: list[dict[str, Any]]
    overrides: list[dict[str, Any]]
    alerts_at_confirmation: list[dict[str, Any]]


class PatientPrescriptionOut(BaseModel):
    id: int
    doctor_name: str
    status: str
    created_at: datetime
    items: list[dict[str, Any]]


class LabelEvidenceOut(BaseModel):
    generic: str
    available: bool
    reason: str | None = None
    sections: dict[str, str | None] | None = None
    set_id: str | None = None
    effective_time: str | None = None
    source: str | None = None


# --- profiles (Module 1) ------------------------------------------------------------------------

GENDERS = ("Male", "Female", "Other")
BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
CONSULTATION_MODES = ("online", "in_clinic", "home")


def _clean(value: str | None) -> str | None:
    value = " ".join((value or "").split())
    return value or None


class AccountOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    role: Role
    created_at: datetime


class PatientProfileOut(BaseModel):
    date_of_birth: date
    age: int
    gender: str
    cnic_masked: str  # the CNIC is collected at signup and never shown in full again
    city: str | None
    address: str | None
    blood_group: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None


class DoctorProfileOut(BaseModel):
    pmdc_number: str
    specialization: str
    verification_status: str
    hospital_name: str
    city: str | None
    qualifications: str | None
    experience_years: int | None
    bio: str | None
    languages: list[str]
    consultation_modes: list[str]
    consultation_fee: int | None


class ActivityOut(BaseModel):
    """What is linked to this profile (Module 1, FE-4): counts only, each opening its own page."""

    reports: int = 0  # patients: uploaded reports
    appointments: int = 0
    prescriptions: int = 0  # patients: confirmed ones received; doctors: confirmed ones written
    payments: int = 0  # patients: payments made; doctors: payments received (paid)


class ProfileOut(BaseModel):
    account: AccountOut
    patient: PatientProfileOut | None = None
    doctor: DoctorProfileOut | None = None
    activity: ActivityOut = Field(default_factory=ActivityOut)


class AccountUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=7, max_length=40)

    @field_validator("full_name", "phone")
    @classmethod
    def tidy(cls, value: str) -> str:
        return " ".join(value.split())


class PatientProfileUpdate(BaseModel):
    date_of_birth: date
    gender: str
    city: str | None = Field(default=None, max_length=80)
    address: str | None = Field(default=None, max_length=240)
    blood_group: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=40)

    @field_validator("date_of_birth")
    @classmethod
    def plausible_birth_date(cls, value: date) -> date:
        today = date.today()
        if value > today or (today.year - value.year) > 120:
            raise ValueError("Enter a real date of birth.")
        return value

    @field_validator("gender")
    @classmethod
    def known_gender(cls, value: str) -> str:
        match = next((g for g in GENDERS if g.lower() == value.strip().lower()), None)
        if match is None:
            raise ValueError("Gender must be Male, Female or Other.")
        return match

    @field_validator("blood_group")
    @classmethod
    def known_blood_group(cls, value: str | None) -> str | None:
        value = _clean(value)
        if value is not None and value.upper() not in BLOOD_GROUPS:
            raise ValueError("Blood group must be A+, A-, B+, B-, AB+, AB-, O+ or O-.")
        return value.upper() if value else None

    @field_validator("city", "address", "emergency_contact_name", "emergency_contact_phone")
    @classmethod
    def tidy_optional(cls, value: str | None) -> str | None:
        return _clean(value)


class DoctorProfileUpdate(BaseModel):
    # Specialization and the PMDC number are verified by an admin, so they are not editable here.
    hospital_name: str = Field(min_length=2, max_length=180)
    city: str | None = Field(default=None, max_length=80)
    qualifications: str | None = Field(default=None, max_length=1000)
    experience_years: int | None = Field(default=None, ge=0, le=70)
    bio: str | None = Field(default=None, max_length=2000)
    languages: list[str] = Field(default_factory=list, max_length=10)
    consultation_modes: list[str] = Field(min_length=1)
    consultation_fee: int | None = Field(default=None, ge=200, le=100_000)  # whole PKR; None: not set

    @field_validator("hospital_name")
    @classmethod
    def tidy_hospital(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("city", "qualifications", "bio")
    @classmethod
    def tidy_optional(cls, value: str | None) -> str | None:
        return _clean(value)

    @field_validator("languages")
    @classmethod
    def tidy_languages(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(v for v in (" ".join(x.split()) for x in values) if v))
        if any(len(v) > 30 for v in cleaned):
            raise ValueError("Each language must be 30 characters or fewer.")
        return cleaned

    @field_validator("consultation_modes")
    @classmethod
    def known_modes(cls, values: list[str]) -> list[str]:
        unknown = [v for v in values if v not in CONSULTATION_MODES]
        if unknown:
            raise ValueError("Consultation modes are online, in_clinic and home.")
        return [m for m in CONSULTATION_MODES if m in values]


# --- availability, slots, reviews, notifications (Module 5) ------------------------------------


class SlotOut(BaseModel):
    start: datetime
    end: datetime
    available: bool


class DaySlotsOut(BaseModel):
    day: date  # a clinic-time calendar day
    slots: list[SlotOut]


class SlotsOut(BaseModel):
    timezone: str  # clinic time zone the days and windows are in
    days: list[DaySlotsOut]


class AvailabilityWindow(BaseModel):
    weekday: int = Field(ge=0, le=6)  # 0 = Monday
    start_time: time
    end_time: time
    slot_minutes: int = 30


class AvailabilityIn(BaseModel):
    windows: list[AvailabilityWindow] = Field(max_length=28)


class AvailabilityOut(BaseModel):
    timezone: str
    slot_choices: list[int]
    windows: list[AvailabilityWindow]


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("comment")
    @classmethod
    def tidy_comment(cls, value: str | None) -> str | None:
        return _clean(value)


class ReviewOut(BaseModel):
    rating: int
    comment: str | None
    created_at: datetime


class NotificationOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str
    appointment_id: int | None
    read: bool
    at: datetime  # when it became visible: the reminder time, or when it was created


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    limit: int
    offset: int
    unread: int


class SymptomCheckIn(BaseModel):
    text: str = Field(min_length=3, max_length=1000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("Please describe your symptoms in a few words.")
        return value


class SpecialtySuggestionOut(BaseModel):
    specialty: str
    plain: str  # what this kind of doctor looks after, in everyday words
    matched: list[str]  # the words that pointed here; empty for the general fallback
    fallback: bool = False
    doctors: list[AppointmentDoctorOut]  # verified doctors only, best first


class SymptomCheckOut(BaseModel):
    emergency: bool
    emergency_notice: str | None = None  # set exactly when `emergency` is true
    warning_signs: list[str] = Field(default_factory=list)
    suggestions: list[SpecialtySuggestionOut] = Field(default_factory=list)  # always empty on an emergency
    advisory: str


class SymptomStatsOut(BaseModel):
    total: int
    emergencies: int
    last_7_days: int
    by_specialty: list[dict[str, int | str]]
