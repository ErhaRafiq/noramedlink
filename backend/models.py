from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

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
        foreign_keys="DoctorProfile.user_id",
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
    # Contact and emergency details the patient keeps up to date (Module 1, FE-2).
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    address: Mapped[str | None] = mapped_column(String(240), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(3), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
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
    # Set by the doctor; what a patient pays online for one consultation (whole PKR). None: not set,
    # so the appointment cannot be paid online yet.
    consultation_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # What patients see on the doctor's card (Module 1, FE-3).
    qualifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    languages: Mapped[str | None] = mapped_column(String(200), nullable=True)  # comma-separated
    consultation_modes: Mapped[str] = mapped_column(
        String(40), default="in_clinic", server_default="in_clinic", nullable=False
    )  # online, in_clinic, home
    # PMDC register check (services/pmdc.py). A doctor can be approved and active without it; a verified
    # one carries a badge. True only when the register lists the number as ACTIVE under the doctor's name
    # (or an administrator confirmed it by hand, with a note).
    pmdc_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=expression.false(), nullable=False
    )
    pmdc_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)  # verified, inactive, ...
    pmdc_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pmdc_register_name: Mapped[str | None] = mapped_column(String(160), nullable=True)  # as the register spells it
    pmdc_register_status: Mapped[str | None] = mapped_column(String(40), nullable=True)  # ACTIVE or In Active
    pmdc_checked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    pmdc_note: Mapped[str | None] = mapped_column(String(300), nullable=True)  # the reason for a manual decision
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="doctor_profile", foreign_keys=[user_id])


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    doctor_name: Mapped[str] = mapped_column(String(180), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    status: Mapped[str] = mapped_column(String(40), default="BOOKED", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialty: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The length of the booked slot and how the consultation happens (services/scheduling.py).
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30", nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="in_clinic", server_default="in_clinic", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    # One live appointment per doctor and start time: the database refuses a double booking even if two
    # requests race (the cancelled ones do not count).
    __table_args__ = (
        Index(
            "appointments_doctor_slot_uq",
            "doctor_id",
            "date",
            unique=True,
            postgresql_where=text("status <> 'CANCELLED'"),
            sqlite_where=text("status <> 'CANCELLED'"),
        ),
    )


class DoctorAvailability(Base):
    """One weekly window a doctor sees patients, cut into slots of `slot_minutes` (clinic time, UTC+5)."""

    __tablename__ = "doctor_availability"
    __table_args__ = (Index("doctor_availability_doctor_id_idx", "doctor_id", "weekday"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday ... 6 = Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30", nullable=False)


class AppointmentReview(Base):
    """A patient's rating of a completed appointment (one per appointment)."""

    __tablename__ = "appointment_reviews"
    __table_args__ = (Index("appointment_reviews_doctor_id_idx", "doctor_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 to 5
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmergencyBooking(Base):
    __tablename__ = "emergency_bookings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
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
    # Stripe Checkout: the session that collects this payment; the webhook marks it paid.
    currency: Mapped[str] = mapped_column(String(3), default="pkr", server_default="pkr", nullable=False)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Refund of a cancelled appointment: requested by us, confirmed only by Stripe's webhook.
    stripe_refund_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class StripeEvent(Base):
    """Stripe webhook events already applied, so a redelivered event changes nothing twice."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # Stripe's event id (evt_...)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Vitals(Base):
    __tablename__ = "vitals"
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (Index("vitals_user_id_created_at_idx", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    blood_pressure: Mapped[str] = mapped_column(String(80), nullable=False)
    sugar_level: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PatientVital(Base):
    """Detailed daily vitals (Prisma model PatientVital)."""

    __tablename__ = "patient_vitals"
    __table_args__ = (Index("patient_vitals_patient_id_recorded_at_idx", "patient_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    blood_pressure_systolic: Mapped[int] = mapped_column(Integer, nullable=False)
    blood_pressure_diastolic: Mapped[int] = mapped_column(Integer, nullable=False)
    heart_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    spo2: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    sugar_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Medication(Base):
    """A patient's medicine schedule. The API exposes `name` as medicine_name and
    `user_id` as patient_id (the Prisma model's duplicate columns are not added)."""

    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    dosage: Mapped[str] = mapped_column(String(120), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MedicineReminder(Base):
    """A scheduled dose of a medication (Prisma model MedicineReminder)."""

    __tablename__ = "medicine_reminders"
    __table_args__ = (
        Index("medicine_reminders_patient_id_reminder_time_idx", "patient_id", "reminder_time"),
        Index("medicine_reminders_medication_id_idx", "medication_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reminder_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frequency: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="UPCOMING", server_default="UPCOMING", nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    medication: Mapped["Medication"] = relationship()


class ReminderLog(Base):
    """History of what happened to a medicine reminder (Prisma model ReminderLog)."""

    __tablename__ = "reminder_logs"
    __table_args__ = (
        Index("reminder_logs_patient_id_scheduled_for_idx", "patient_id", "scheduled_for"),
        Index("reminder_logs_reminder_id_idx", "reminder_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("medicine_reminders.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Reminder(Base):
    __tablename__ = "reminders"
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (Index("reminders_user_id_due_at_idx", "user_id", "due_at"),)

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
    """Legacy report table, kept read-only. Migration 0008 copied every row into
    patient_reports, which is the only report table the app writes. Never dropped."""

    __tablename__ = "medical_documents"
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (Index("medical_documents_user_id_created_at_idx", "user_id", "created_at"),)

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
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (
        Index("patient_reports_patient_id_upload_date_idx", "patient_id", "upload_date"),
        Index("patient_reports_legacy_medical_document_id_key", "legacy_medical_document_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("medical_departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # TEXT: legacy reports copied from medical_documents may hold an embedded data: image.
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    # The medical_documents row this report was copied from (migration 0008); no FK so the
    # legacy table can be retired independently.
    legacy_medical_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (Index("medical_ai_analyses_user_id_created_at_idx", "user_id", "created_at"),)

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


@event.listens_for(MedicalDocument, "before_insert")
@event.listens_for(MedicalDocument, "before_update")
@event.listens_for(MedicalDocument, "before_delete")
def _reject_medical_document_writes(mapper, connection, target) -> None:
    raise RuntimeError("medical_documents is read-only; write reports to patient_reports.")


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
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (Index("health_risk_predictions_patient_id_created_at_idx", "patient_id", "created_at"),)

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
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (Index("health_tips_patient_id_created_at_idx", "patient_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    tip_text: Mapped[str] = mapped_column(Text, nullable=False)
    based_on_data: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[User] = relationship(back_populates="health_tips")


class DoctorSummary(Base):
    __tablename__ = "doctor_summaries"
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (Index("doctor_summaries_patient_id_generated_at_idx", "patient_id", "generated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[User] = relationship(back_populates="doctor_summaries")


class ClinicalSummary(Base):
    """One version of a patient's clinical summary for doctors (ICSE). Each regeneration adds a row;
    earlier versions are kept. Derived data only: built from reports, vitals and medicines."""

    __tablename__ = "clinical_summaries"
    __table_args__ = (
        Index("clinical_summaries_patient_id_generated_at_idx", "patient_id", "generated_at"),
        UniqueConstraint("patient_id", "version", name="clinical_summaries_patient_id_version_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # The doctor whose request built this version; kept if that account is later removed.
    generated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    trigger: Mapped[str] = mapped_column(String(300), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="rule_based", nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Prescription(Base):
    """A prescription a doctor confirmed after the medication-safety check (MSCIE). The check result
    and the patient context it used are kept as they were at confirmation."""

    __tablename__ = "prescriptions"
    __table_args__ = (Index("prescriptions_patient_id_created_at_idx", "patient_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Kept if the doctor's account is later removed; the name is copied for the record.
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    doctor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", nullable=False)  # confirmed | cancelled
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_result: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", order_by="PrescriptionItem.position"
    )
    overrides: Mapped[list["SafetyOverride"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan"
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    medicine: Mapped[str] = mapped_column(String(160), nullable=False)  # as chosen by the doctor
    generic: Mapped[str | None] = mapped_column(String(160), nullable=True)  # None: not in the knowledge base
    dose: Mapped[str | None] = mapped_column(String(60), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(60), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(60), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaced_medicine: Mapped[str | None] = mapped_column(String(160), nullable=True)  # an alternative chosen instead

    prescription: Mapped[Prescription] = relationship(back_populates="items")


class SafetyOverride(Base):
    """A doctor's written reason for prescribing despite a high-risk alert (AGENTS.md 6.5)."""

    __tablename__ = "safety_overrides"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    alert_id: Mapped[str] = mapped_column(String(300), nullable=False)
    alert_severity: Mapped[str] = mapped_column(String(20), nullable=False)
    alert_title: Mapped[str] = mapped_column(String(300), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    prescription: Mapped[Prescription] = relationship(back_populates="overrides")


class PatientDashboardAccess(Base):
    __tablename__ = "patient_dashboard_access"
    # Same name as the retired Prisma schema's @@unique([doctorId, patientId]), so existing databases match.
    __table_args__ = (
        UniqueConstraint("doctor_id", "patient_id", name="patient_dashboard_access_doctor_id_patient_id_key"),
    )

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


class RefreshToken(Base):
    """A sign-in session's refresh token (services/sessions.py). Only a hash is stored. Each use
    rotates it: the old row is revoked and a new one issued in the same family. A revoked token
    used again means a stolen copy, so the whole family is revoked."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("refresh_tokens_user_id_idx", "user_id"), Index("refresh_tokens_family_idx", "family_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    family_id: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DashboardOtpAttempt(Base):
    """Every attempt to redeem a patient dashboard OTP, for rate limiting and audit.
    The OTP code itself is never stored here."""

    __tablename__ = "dashboard_otp_attempts"
    __table_args__ = (Index("dashboard_otp_attempts_actor_id_created_at_idx", "actor_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    context: Mapped[str] = mapped_column(String(20), nullable=False)  # "unlock" (doctor) or "booking" (patient)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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


class SymptomSession(Base):
    """One run of the symptom checker, kept for the admin counts. The text is what the visitor typed;
    user_id is empty for visitors who were not signed in."""

    __tablename__ = "symptom_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    symptom_text: Mapped[str] = mapped_column(Text, nullable=False)
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    red_flags: Mapped[str] = mapped_column(String(200), default="", server_default="", nullable=False)  # RF ids, ";"
    specialty: Mapped[str | None] = mapped_column(String(80), nullable=True)  # the top suggestion; none on a red flag
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PatientHealthEntry(Base):
    """One structured allergy, diagnosis or long-term condition on a patient's record. The patient and a
    doctor with an active grant can add and edit; nothing is hard-deleted ("removed" hides it from the list)."""

    __tablename__ = "patient_health_entries"
    __table_args__ = (Index("patient_health_entries_patient_kind_idx", "patient_id", "kind", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # allergy, diagnosis or chronic_condition
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # allergies only: mild, moderate, severe
    since: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", nullable=False)
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    added_by_role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    """Who did what to whose record (FR-8.3, FR-14.3). Holds no medical text: `detail` is a short system label."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[int | None] = mapped_column(nullable=True)
    patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    detail: Mapped[str] = mapped_column(String(300), default="", server_default="", nullable=False)
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
    # Index names from the retired Prisma schema, so existing databases match.
    __table_args__ = (
        Index("notifications_user_id_created_at_idx", "user_id", "created_at"),
        Index("notifications_reminder_id_idx", "reminder_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_id: Mapped[int | None] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="UNREAD", nullable=False)
    # Appointment messages (services/notifications.py): the appointment they are about, and what kind. A
    # message with a scheduled_for in the future (a reminder) is not shown until that time.
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="general", server_default="general", nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
