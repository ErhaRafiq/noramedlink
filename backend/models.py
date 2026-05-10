from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="PATIENT", nullable=False)
    phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_identity_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dashboard_access_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient_profile: Mapped["PatientProfile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    doctor_profile: Mapped["DoctorProfile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    medical_documents: Mapped[list["MedicalDocument"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    patient_reports: Mapped[list["PatientReport"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    medicine_history: Mapped[list["MedicineHistory"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    health_risk_predictions: Mapped[list["HealthRiskPrediction"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    health_tips: Mapped[list["HealthTip"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    doctor_summaries: Mapped[list["DoctorSummary"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    cnic: Mapped[str] = mapped_column(String(20), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(30), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="patient_profile")


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    pmdc_number: Mapped[str] = mapped_column(String(80), nullable=False)
    specialization: Mapped[str] = mapped_column(String(120), nullable=False)
    hospital_name: Mapped[str] = mapped_column(String(180), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="doctor_profile")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    doctor_name: Mapped[str] = mapped_column(String(180), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    status: Mapped[str] = mapped_column(String(40), default="BOOKED", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class EmergencyBooking(Base):
    __tablename__ = "emergency_bookings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    patient_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    symptoms: Mapped[str] = mapped_column(Text, nullable=False)
    doctor_name: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="SEARCHING", index=True, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(default=18, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[int] = mapped_column(nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Vitals(Base):
    __tablename__ = "vitals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    blood_pressure: Mapped[str] = mapped_column(String(80), nullable=False)
    sugar_level: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    dosage: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="UPCOMING", index=True, nullable=False)
    fcm_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class MedicalDocument(Base):
    __tablename__ = "medical_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="general-medicine", index=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    file_type: Mapped[str] = mapped_column(String(30), default="unknown", nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    possible_report_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detected_keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    structured_sections: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    scan_status: Mapped[str] = mapped_column(String(30), default="UPLOADED", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="medical_documents")
    ai_analyses: Mapped[list["MedicalAiAnalysis"]] = relationship(
        back_populates="medical_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def patient_id(self) -> int:
        return self.user_id

    @patient_id.setter
    def patient_id(self, value: int) -> None:
        self.user_id = value

    @property
    def original_filename(self) -> str:
        return self.file_name

    @original_filename.setter
    def original_filename(self, value: str) -> None:
        self.file_name = value

    @property
    def stored_file_path(self) -> str:
        return self.file_url

    @stored_file_path.setter
    def stored_file_path(self, value: str) -> None:
        self.file_url = value

    @property
    def upload_date(self) -> datetime:
        return self.created_at

    @upload_date.setter
    def upload_date(self, value: datetime) -> None:
        self.created_at = value

    @property
    def ocr_status(self) -> str:
        return self.scan_status

    @ocr_status.setter
    def ocr_status(self, value: str) -> None:
        self.scan_status = value

    @property
    def ocr_cleaned_text(self) -> str | None:
        return self.edited_ocr_text or self.extracted_text

    @ocr_cleaned_text.setter
    def ocr_cleaned_text(self, value: str | None) -> None:
        self.extracted_text = value
        self.edited_ocr_text = value

    @property
    def file_url_alias(self) -> str:
        return self.file_url

    @property
    def report_title(self) -> str:
        return self.title

    @property
    def report_category(self) -> str:
        return self.category


class MedicalDepartment(Base):
    __tablename__ = "medical_departments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reports: Mapped[list["PatientReport"]] = relationship(back_populates="department")


class PatientReport(Base):
    __tablename__ = "patient_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("medical_departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(30), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    formatted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rule_warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), default="SAFE", index=True, nullable=False)
    validation_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    clinical_summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    llm_self_check: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary_source: Mapped[str] = mapped_column(String(80), default="rule_based", nullable=False)
    ocr_status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True, nullable=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    upload_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient: Mapped[User] = relationship(back_populates="patient_reports")
    department: Mapped[MedicalDepartment | None] = relationship(back_populates="reports")
    ai_analyses: Mapped[list["MedicalAiAnalysis"]] = relationship(
        back_populates="patient_report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MedicalAiAnalysis(Base):
    __tablename__ = "medical_ai_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    medical_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("medical_documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    patient_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("patient_reports.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(80), default="rule_based", nullable=False)
    extracted_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rule_warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    validation_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    doctor_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    medical_document: Mapped[MedicalDocument | None] = relationship(back_populates="ai_analyses")
    patient_report: Mapped[PatientReport | None] = relationship(back_populates="ai_analyses")


class MedicineHistory(Base):
    __tablename__ = "medicine_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    medicine_name: Mapped[str] = mapped_column(String(160), nullable=False)
    dosage: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    prescribed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    side_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient: Mapped[User] = relationship(back_populates="medicine_history")


class HealthRiskPrediction(Base):
    __tablename__ = "health_risk_predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_title: Mapped[str] = mapped_column(String(180), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[User] = relationship(back_populates="health_risk_predictions")


class HealthTip(Base):
    __tablename__ = "health_tips"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    tip_text: Mapped[str] = mapped_column(Text, nullable=False)
    based_on_data: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[User] = relationship(back_populates="health_tips")


class DoctorSummary(Base):
    __tablename__ = "doctor_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[User] = relationship(back_populates="doctor_summaries")


class PatientDashboardAccess(Base):
    __tablename__ = "patient_dashboard_access"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PatientDashboardOtp(Base):
    __tablename__ = "patient_dashboard_otps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SignupOtp(Base):
    __tablename__ = "signup_otps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class NotificationToken(Base):
    __tablename__ = "notification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="web", nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_id: Mapped[int | None] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="UNREAD", nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
