from datetime import date, datetime
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
    # doctor_id must name a verified, active doctor; the stored name and specialty
    # come from that doctor's record. doctor_name / specialty are accepted for
    # compatibility but not trusted.
    doctor_id: int | None = None
    doctor_name: str | None = Field(default=None, max_length=180)
    specialty: str | None = Field(default=None, max_length=120)
    date: datetime | None = None
    reason: str | None = None
    notes: str | None = None
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
    status: str
    payment_status: str
    notes: str | None
    specialty: str | None = None
    reason: str | None = None
    # The doctor's current fee (whole PKR), what the patient pays online; None: not set.
    consultation_fee: int | None = None
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
    # No ratings or availability are stored yet (Phase 2c); null means "not available",
    # never an estimate.
    rating: float | None = None
    available_today: bool | None = None
    consultation_fee: int | None = None  # whole PKR, set by the doctor; None: not set
    source: Literal["registered"] = "registered"


class PaymentOut(BaseModel):
    id: int
    user_id: int
    appointment_id: int | None
    amount: int  # whole units of `currency` (PKR)
    currency: str
    method: str
    purpose: str
    status: str  # PENDING, PAID, FAILED or EXPIRED (older manual records may show other values)
    reference: str
    invoice_number: str | None
    paid_at: datetime | None
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


class ConsultationFeeIn(BaseModel):
    consultation_fee: int | None = Field(default=None, ge=200, le=100_000)  # whole PKR; None clears it


class ConsultationFeeOut(BaseModel):
    consultation_fee: int | None


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
