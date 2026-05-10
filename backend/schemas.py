import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


Role = Literal["patient", "doctor", "admin"]


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: Role
    phone: str
    is_email_verified: bool
    is_identity_verified: bool
    verification_status: str


class PatientSignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str
    cnic: str
    phone: str = Field(min_length=7, max_length=40)
    date_of_birth: date
    gender: str = Field(min_length=1, max_length=30)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, confirm_password: str, info):
        if info.data.get("password") != confirm_password:
            raise ValueError("Password and confirm password must match.")
        return confirm_password

    @field_validator("cnic")
    @classmethod
    def validate_cnic(cls, cnic: str) -> str:
        normalized = cnic.strip()
        if not re.fullmatch(r"(?:\d{5}-\d{7}-\d|\d{13})", normalized):
            raise ValueError("CNIC must be 13 digits or formatted like 12345-1234567-1.")
        return normalized


class DoctorSignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str
    pmdc_number: str = Field(min_length=2, max_length=80)
    specialization: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=40)
    hospital_name: str = Field(min_length=2, max_length=180)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, confirm_password: str, info):
        if info.data.get("password") != confirm_password:
            raise ValueError("Password and confirm password must match.")
        return confirm_password


class SignupOtpRequest(BaseModel):
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


class VerifySignupOtpRequest(SignupOtpRequest):
    otp: str = Field(min_length=6, max_length=6)

    @field_validator("otp")
    @classmethod
    def otp_must_be_six_digits(cls, otp: str) -> str:
        normalized = otp.strip()
        if not re.fullmatch(r"\d{6}", normalized):
            raise ValueError("OTP must be a 6-digit code.")
        return normalized


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class OcrOutput(BaseModel):
    raw_text: str
    cleaned_text: str
    possible_report_type: str
    detected_keywords: list[str]
    structured_sections: dict[str, str]


class MedicalDocumentOut(BaseModel):
    id: int
    patient_id: int
    category: str
    title: str
    notes: str | None
    original_filename: str
    stored_file_path: str
    file_type: str
    upload_date: datetime
    ocr_status: str
    ocr_raw_text: str | None
    ocr_cleaned_text: str | None
    possible_report_type: str | None
    detected_keywords: list[str]
    structured_sections: dict[str, str]
    ai_summary: str | None


class VitalsOut(BaseModel):
    id: int
    user_id: int
    blood_pressure: str
    sugar_level: str
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
    risk_level: Literal["Low", "Medium", "High"] | str = "Low"
    validation_status: Literal["SAFE", "CAUTION", "HIGH_RISK"] | str = "SAFE"


class PatientReportUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    department: str | None = Field(default=None, max_length=80)
    extracted_text: str | None = None
    formatted_text: str | None = None
    structured_data_json: dict[str, Any] | None = None


class MedicineHistoryBase(BaseModel):
    medicine_name: str = Field(min_length=1, max_length=160)
    dosage: str = Field(min_length=1, max_length=120)
    frequency: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date | None = None
    reason: str = Field(min_length=1)
    prescribed_by: str | None = Field(default=None, max_length=160)
    side_effects: str | None = None


class MedicineHistoryCreate(MedicineHistoryBase):
    pass


class MedicineHistoryUpdate(BaseModel):
    medicine_name: str | None = Field(default=None, min_length=1, max_length=160)
    dosage: str | None = Field(default=None, min_length=1, max_length=120)
    frequency: str | None = Field(default=None, min_length=1, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(default=None, min_length=1)
    prescribed_by: str | None = Field(default=None, max_length=160)
    side_effects: str | None = None


class MedicineHistoryOut(MedicineHistoryBase):
    id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime


class HealthRiskPredictionOut(BaseModel):
    id: int
    patient_id: int
    risk_title: str
    risk_level: Literal["Low", "Medium", "High"] | str
    reason: str
    recommendation: str
    created_at: datetime


class HealthTipOut(BaseModel):
    id: int
    patient_id: int
    category: Literal["Food to prefer", "Food to avoid", "Lifestyle advice", "When to consult a doctor"] | str
    tip_text: str
    based_on_data: str
    created_at: datetime


class DoctorSummaryOut(BaseModel):
    id: int
    patient_id: int
    summary_text: str
    generated_at: datetime


class MedicineSafetyCheckRequest(BaseModel):
    medicine_name: str = Field(min_length=1, max_length=160)
    dosage: str | None = Field(default=None, max_length=120)
    known_allergies: str | None = None


class MedicineSafetyCheckResponse(BaseModel):
    status: Literal["Safe", "Caution", "High Risk"]
    reason: str
    warnings: list[str]


class DashboardCategory(BaseModel):
    category: str
    document_count: int
    last_updated: datetime | None


class PatientDashboardOut(BaseModel):
    patient: UserOut
    total_reports: int
    categories_used: int
    latest_upload: PatientReportOut | None
    ocr_processed_reports: int
    ai_summaries_generated: int
    categories: list[DashboardCategory]
    recent_documents: list[PatientReportOut]
    medicine_count: int = 0
    latest_risk_prediction: HealthRiskPredictionOut | None = None
    latest_doctor_summary: DoctorSummaryOut | None = None


class OcrTextUpdateRequest(BaseModel):
    cleaned_text: str = Field(min_length=1)


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=1)
    category: str | None = None


class SummaryResponse(BaseModel):
    summary: str
    method: Literal["openai", "rule_based"]
    warning: str | None = None


class AppointmentCreate(BaseModel):
    doctor_name: str = Field(min_length=1, max_length=180)
    doctor_id: int | None = None
    date: datetime | None = None
    notes: str | None = None
    patient_access_otp: str | None = Field(default=None, max_length=12)


class AppointmentUpdate(BaseModel):
    date: datetime | None = None
    status: str | None = Field(default=None, max_length=40)
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
    rating: float
    available_today: bool
    source: Literal["registered", "demo"]


class PaymentCreate(BaseModel):
    amount: int = Field(gt=0)
    method: str = Field(min_length=1, max_length=40)
    purpose: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    appointment_id: int | None = None


class PaymentUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=40)
    transaction_id: str | None = Field(default=None, max_length=160)
    invoice_url: str | None = Field(default=None, max_length=500)


class PaymentOut(BaseModel):
    id: int
    user_id: int
    appointment_id: int | None
    amount: int
    method: str
    purpose: str
    status: str
    phone: str | None
    reference: str
    transaction_id: str | None
    invoice_number: str | None
    invoice_url: str | None
    created_at: datetime
    updated_at: datetime


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    due_at: datetime
    fcm_token: str | None = Field(default=None, max_length=500)


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    due_at: datetime | None = None
    status: str | None = Field(default=None, max_length=40)
    fcm_token: str | None = Field(default=None, max_length=500)


class ReminderOut(BaseModel):
    id: int
    user_id: int
    title: str
    due_at: datetime
    status: str
    fcm_token: str | None
    created_at: datetime
    updated_at: datetime


class NotificationTokenUpsert(BaseModel):
    token: str = Field(min_length=1, max_length=500)
    platform: str = Field(default="web", max_length=40)


class NotificationTokenOut(BaseModel):
    id: int
    user_id: int
    token: str
    platform: str
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class MedicalAiAnalysisOut(BaseModel):
    id: int
    user_id: int
    medical_record_id: int | None
    patient_report_id: int | None = None
    source: str
    extracted_entities: list
    confidence_score: float | None
    rule_warnings: list
    validation_results: dict
    doctor_summary: str | None
    created_at: datetime
    updated_at: datetime
