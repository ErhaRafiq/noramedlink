"""baseline: schema of the SQLAlchemy models at the start of Phase 1

Revision ID: 0001
Revises: 
Create Date: 2026-10-04 01:21:22.124907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Each table is created only if it is missing, so this baseline can run on a fresh
    # database and on databases created earlier by FastAPI's create_all or by Prisma.
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if 'medical_departments' not in existing:
        op.create_table('medical_departments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('icon', sa.String(length=80), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_medical_departments_id'), 'medical_departments', ['id'], unique=False)
        op.create_index(op.f('ix_medical_departments_name'), 'medical_departments', ['name'], unique=True)

    if 'signup_otps' not in existing:
        op.create_table('signup_otps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('otp_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('verified', sa.Boolean(), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_signup_otps_created_at'), 'signup_otps', ['created_at'], unique=False)
        op.create_index(op.f('ix_signup_otps_email'), 'signup_otps', ['email'], unique=False)
        op.create_index(op.f('ix_signup_otps_expires_at'), 'signup_otps', ['expires_at'], unique=False)
        op.create_index(op.f('ix_signup_otps_id'), 'signup_otps', ['id'], unique=False)
        op.create_index(op.f('ix_signup_otps_phone'), 'signup_otps', ['phone'], unique=False)
        op.create_index(op.f('ix_signup_otps_role'), 'signup_otps', ['role'], unique=False)
        op.create_index(op.f('ix_signup_otps_verified'), 'signup_otps', ['verified'], unique=False)

    if 'users' not in existing:
        op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=160), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_email_verified', sa.Boolean(), nullable=False),
        sa.Column('is_identity_verified', sa.Boolean(), nullable=False),
        sa.Column('dashboard_access_key', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dashboard_access_key')
        )
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    if 'appointments' not in existing:
        op.create_table('appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doctor_name', sa.String(length=180), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('payment_status', sa.String(length=40), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_appointments_date'), 'appointments', ['date'], unique=False)
        op.create_index(op.f('ix_appointments_doctor_id'), 'appointments', ['doctor_id'], unique=False)
        op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)
        op.create_index(op.f('ix_appointments_user_id'), 'appointments', ['user_id'], unique=False)

    if 'doctor_profiles' not in existing:
        op.create_table('doctor_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('pmdc_number', sa.String(length=80), nullable=False),
        sa.Column('specialization', sa.String(length=120), nullable=False),
        sa.Column('hospital_name', sa.String(length=180), nullable=False),
        sa.Column('verification_status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
        )
        op.create_index(op.f('ix_doctor_profiles_id'), 'doctor_profiles', ['id'], unique=False)

    if 'doctor_summaries' not in existing:
        op.create_table('doctor_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_doctor_summaries_id'), 'doctor_summaries', ['id'], unique=False)
        op.create_index(op.f('ix_doctor_summaries_patient_id'), 'doctor_summaries', ['patient_id'], unique=False)

    if 'emergency_bookings' not in existing:
        op.create_table('emergency_bookings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=True),
        sa.Column('patient_name', sa.String(length=160), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('symptoms', sa.Text(), nullable=False),
        sa.Column('doctor_name', sa.String(length=180), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('estimated_minutes', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_emergency_bookings_doctor_id'), 'emergency_bookings', ['doctor_id'], unique=False)
        op.create_index(op.f('ix_emergency_bookings_id'), 'emergency_bookings', ['id'], unique=False)
        op.create_index(op.f('ix_emergency_bookings_status'), 'emergency_bookings', ['status'], unique=False)
        op.create_index(op.f('ix_emergency_bookings_user_id'), 'emergency_bookings', ['user_id'], unique=False)

    if 'health_risk_predictions' not in existing:
        op.create_table('health_risk_predictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('risk_title', sa.String(length=180), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('recommendation', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_health_risk_predictions_id'), 'health_risk_predictions', ['id'], unique=False)
        op.create_index(op.f('ix_health_risk_predictions_patient_id'), 'health_risk_predictions', ['patient_id'], unique=False)

    if 'health_tips' not in existing:
        op.create_table('health_tips',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=80), nullable=False),
        sa.Column('tip_text', sa.Text(), nullable=False),
        sa.Column('based_on_data', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_health_tips_id'), 'health_tips', ['id'], unique=False)
        op.create_index(op.f('ix_health_tips_patient_id'), 'health_tips', ['patient_id'], unique=False)

    if 'medical_documents' not in existing:
        op.create_table('medical_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('category', sa.String(length=80), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_url', sa.String(length=500), nullable=False),
        sa.Column('file_type', sa.String(length=30), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('ocr_raw_text', sa.Text(), nullable=True),
        sa.Column('edited_ocr_text', sa.Text(), nullable=True),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('extracted_entities', sa.JSON(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('possible_report_type', sa.String(length=120), nullable=True),
        sa.Column('detected_keywords', sa.JSON(), nullable=False),
        sa.Column('structured_sections', sa.JSON(), nullable=False),
        sa.Column('scan_status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_medical_documents_category'), 'medical_documents', ['category'], unique=False)
        op.create_index(op.f('ix_medical_documents_id'), 'medical_documents', ['id'], unique=False)
        op.create_index(op.f('ix_medical_documents_scan_status'), 'medical_documents', ['scan_status'], unique=False)
        op.create_index(op.f('ix_medical_documents_user_id'), 'medical_documents', ['user_id'], unique=False)

    if 'medications' not in existing:
        op.create_table('medications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('dosage', sa.String(length=120), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_medications_id'), 'medications', ['id'], unique=False)
        op.create_index(op.f('ix_medications_user_id'), 'medications', ['user_id'], unique=False)

    if 'medicine_history' not in existing:
        op.create_table('medicine_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('medicine_name', sa.String(length=160), nullable=False),
        sa.Column('dosage', sa.String(length=120), nullable=False),
        sa.Column('frequency', sa.String(length=120), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('prescribed_by', sa.String(length=160), nullable=True),
        sa.Column('side_effects', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_medicine_history_id'), 'medicine_history', ['id'], unique=False)
        op.create_index(op.f('ix_medicine_history_patient_id'), 'medicine_history', ['patient_id'], unique=False)

    if 'notification_tokens' not in existing:
        op.create_table('notification_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('platform', sa.String(length=40), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
        )
        op.create_index(op.f('ix_notification_tokens_id'), 'notification_tokens', ['id'], unique=False)
        op.create_index(op.f('ix_notification_tokens_user_id'), 'notification_tokens', ['user_id'], unique=False)

    if 'patient_dashboard_access' not in existing:
        op.create_table('patient_dashboard_access',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doctor_id', 'patient_id', name='patient_dashboard_access_doctor_id_patient_id_key')
        )
        op.create_index(op.f('ix_patient_dashboard_access_doctor_id'), 'patient_dashboard_access', ['doctor_id'], unique=False)
        op.create_index(op.f('ix_patient_dashboard_access_id'), 'patient_dashboard_access', ['id'], unique=False)
        op.create_index(op.f('ix_patient_dashboard_access_patient_id'), 'patient_dashboard_access', ['patient_id'], unique=False)

    if 'patient_dashboard_otps' not in existing:
        op.create_table('patient_dashboard_otps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=12), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
        )
        op.create_index(op.f('ix_patient_dashboard_otps_id'), 'patient_dashboard_otps', ['id'], unique=False)
        op.create_index(op.f('ix_patient_dashboard_otps_patient_id'), 'patient_dashboard_otps', ['patient_id'], unique=False)

    if 'patient_profiles' not in existing:
        op.create_table('patient_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cnic', sa.String(length=20), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('gender', sa.String(length=30), nullable=False),
        sa.Column('verification_status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
        )
        op.create_index(op.f('ix_patient_profiles_id'), 'patient_profiles', ['id'], unique=False)

    if 'patient_reports' not in existing:
        op.create_table('patient_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('original_file_name', sa.String(length=255), nullable=False),
        sa.Column('file_url', sa.String(length=500), nullable=False),
        sa.Column('file_type', sa.String(length=30), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('formatted_text', sa.Text(), nullable=True),
        sa.Column('structured_data_json', sa.JSON(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('extracted_entities', sa.JSON(), nullable=False),
        sa.Column('rule_warnings', sa.JSON(), nullable=False),
        sa.Column('validation_status', sa.String(length=30), nullable=False),
        sa.Column('validation_results', sa.JSON(), nullable=False),
        sa.Column('clinical_summary_json', sa.JSON(), nullable=False),
        sa.Column('llm_self_check', sa.JSON(), nullable=False),
        sa.Column('summary_source', sa.String(length=80), nullable=False),
        sa.Column('ocr_status', sa.String(length=30), nullable=False),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('upload_date', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['medical_departments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_patient_reports_department_id'), 'patient_reports', ['department_id'], unique=False)
        op.create_index(op.f('ix_patient_reports_id'), 'patient_reports', ['id'], unique=False)
        op.create_index(op.f('ix_patient_reports_ocr_status'), 'patient_reports', ['ocr_status'], unique=False)
        op.create_index(op.f('ix_patient_reports_patient_id'), 'patient_reports', ['patient_id'], unique=False)
        op.create_index(op.f('ix_patient_reports_upload_date'), 'patient_reports', ['upload_date'], unique=False)
        op.create_index(op.f('ix_patient_reports_validation_status'), 'patient_reports', ['validation_status'], unique=False)

    if 'reminders' not in existing:
        op.create_table('reminders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('fcm_token', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_reminders_due_at'), 'reminders', ['due_at'], unique=False)
        op.create_index(op.f('ix_reminders_id'), 'reminders', ['id'], unique=False)
        op.create_index(op.f('ix_reminders_status'), 'reminders', ['status'], unique=False)
        op.create_index(op.f('ix_reminders_user_id'), 'reminders', ['user_id'], unique=False)

    if 'vitals' not in existing:
        op.create_table('vitals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('blood_pressure', sa.String(length=80), nullable=False),
        sa.Column('sugar_level', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_vitals_id'), 'vitals', ['id'], unique=False)
        op.create_index(op.f('ix_vitals_user_id'), 'vitals', ['user_id'], unique=False)

    if 'medical_ai_analyses' not in existing:
        op.create_table('medical_ai_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('medical_record_id', sa.Integer(), nullable=True),
        sa.Column('patient_report_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=80), nullable=False),
        sa.Column('extracted_entities', sa.JSON(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('rule_warnings', sa.JSON(), nullable=False),
        sa.Column('validation_results', sa.JSON(), nullable=False),
        sa.Column('doctor_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['medical_record_id'], ['medical_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_report_id'], ['patient_reports.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_medical_ai_analyses_id'), 'medical_ai_analyses', ['id'], unique=False)
        op.create_index(op.f('ix_medical_ai_analyses_medical_record_id'), 'medical_ai_analyses', ['medical_record_id'], unique=False)
        op.create_index(op.f('ix_medical_ai_analyses_patient_report_id'), 'medical_ai_analyses', ['patient_report_id'], unique=False)
        op.create_index(op.f('ix_medical_ai_analyses_user_id'), 'medical_ai_analyses', ['user_id'], unique=False)

    if 'notifications' not in existing:
        op.create_table('notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reminder_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['reminder_id'], ['reminders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
        op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    if 'payments' not in existing:
        op.create_table('payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('method', sa.String(length=40), nullable=False),
        sa.Column('purpose', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('reference', sa.String(length=120), nullable=False),
        sa.Column('transaction_id', sa.String(length=160), nullable=True),
        sa.Column('invoice_number', sa.String(length=120), nullable=True),
        sa.Column('invoice_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_number'),
        sa.UniqueConstraint('reference')
        )
        op.create_index(op.f('ix_payments_appointment_id'), 'payments', ['appointment_id'], unique=False)
        op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
        op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
        op.create_index(op.f('ix_payments_user_id'), 'payments', ['user_id'], unique=False)


def downgrade() -> None:
    # Downgrading the baseline would drop every table and all data; refuse instead.
    raise NotImplementedError("The baseline migration cannot be downgraded.")
