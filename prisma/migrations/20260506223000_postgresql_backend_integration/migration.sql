CREATE TABLE "users" (
    "id" SERIAL NOT NULL,
    "full_name" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "hashed_password" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'PATIENT',
    "phone" TEXT NOT NULL DEFAULT '',
    "is_email_verified" BOOLEAN NOT NULL DEFAULT false,
    "is_identity_verified" BOOLEAN NOT NULL DEFAULT false,
    "dashboard_access_key" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "patient_profiles" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "cnic" TEXT NOT NULL,
    "date_of_birth" DATE NOT NULL,
    "gender" TEXT NOT NULL,
    "verification_status" TEXT NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "patient_profiles_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "doctor_profiles" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "pmdc_number" TEXT NOT NULL,
    "specialization" TEXT NOT NULL,
    "hospital_name" TEXT NOT NULL,
    "verification_status" TEXT NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "doctor_profiles_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "appointments" (
    "id" SERIAL NOT NULL,
    "doctor_name" TEXT NOT NULL,
    "user_id" INTEGER NOT NULL,
    "doctor_id" INTEGER,
    "date" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "status" TEXT NOT NULL DEFAULT 'BOOKED',
    "payment_status" TEXT NOT NULL DEFAULT 'PENDING',
    "notes" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "appointments_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "emergency_bookings" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "doctor_id" INTEGER,
    "patient_name" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "address" TEXT NOT NULL,
    "symptoms" TEXT NOT NULL,
    "doctor_name" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'SEARCHING',
    "estimated_minutes" INTEGER NOT NULL DEFAULT 18,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "emergency_bookings_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "payments" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "appointment_id" INTEGER,
    "amount" INTEGER NOT NULL,
    "method" TEXT NOT NULL,
    "purpose" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "phone" TEXT,
    "reference" TEXT NOT NULL,
    "transaction_id" TEXT,
    "invoice_number" TEXT,
    "invoice_url" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "payments_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "vitals" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "blood_pressure" TEXT NOT NULL,
    "sugar_level" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "vitals_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "medications" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "dosage" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "medications_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "reminders" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "title" TEXT NOT NULL,
    "due_at" TIMESTAMPTZ NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'UPCOMING',
    "fcm_token" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "reminders_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "medical_documents" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "title" TEXT NOT NULL,
    "category" TEXT NOT NULL DEFAULT 'general-medicine',
    "notes" TEXT,
    "file_name" TEXT NOT NULL,
    "file_url" TEXT NOT NULL DEFAULT '',
    "file_type" TEXT NOT NULL DEFAULT 'unknown',
    "extracted_text" TEXT,
    "ocr_raw_text" TEXT,
    "edited_ocr_text" TEXT,
    "ai_summary" TEXT,
    "extracted_entities" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "confidence_score" DOUBLE PRECISION,
    "possible_report_type" TEXT,
    "detected_keywords" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "structured_sections" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "scan_status" TEXT NOT NULL DEFAULT 'UPLOADED',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "medical_documents_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "medical_ai_analyses" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "medical_record_id" INTEGER,
    "source" TEXT NOT NULL DEFAULT 'rule_based',
    "extracted_entities" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "confidence_score" DOUBLE PRECISION,
    "rule_warnings" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "validation_results" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "doctor_summary" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "medical_ai_analyses_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "medicine_history" (
    "id" SERIAL NOT NULL,
    "patient_id" INTEGER NOT NULL,
    "medicine_name" TEXT NOT NULL,
    "dosage" TEXT NOT NULL,
    "frequency" TEXT NOT NULL,
    "start_date" DATE NOT NULL,
    "end_date" DATE,
    "reason" TEXT NOT NULL,
    "prescribed_by" TEXT,
    "side_effects" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "medicine_history_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "health_risk_predictions" (
    "id" SERIAL NOT NULL,
    "patient_id" INTEGER NOT NULL,
    "risk_title" TEXT NOT NULL,
    "risk_level" TEXT NOT NULL,
    "reason" TEXT NOT NULL,
    "recommendation" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "health_risk_predictions_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "health_tips" (
    "id" SERIAL NOT NULL,
    "patient_id" INTEGER NOT NULL,
    "category" TEXT NOT NULL,
    "tip_text" TEXT NOT NULL,
    "based_on_data" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "health_tips_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "doctor_summaries" (
    "id" SERIAL NOT NULL,
    "patient_id" INTEGER NOT NULL,
    "summary_text" TEXT NOT NULL,
    "generated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "doctor_summaries_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "patient_dashboard_access" (
    "id" SERIAL NOT NULL,
    "doctor_id" INTEGER NOT NULL,
    "patient_id" INTEGER NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'ACTIVE',
    "expires_at" TIMESTAMPTZ,
    "ended_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "patient_dashboard_access_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "patient_dashboard_otps" (
    "id" SERIAL NOT NULL,
    "patient_id" INTEGER NOT NULL,
    "code" TEXT NOT NULL,
    "expires_at" TIMESTAMPTZ NOT NULL,
    "used_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "patient_dashboard_otps_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "notification_tokens" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "token" TEXT NOT NULL,
    "platform" TEXT NOT NULL DEFAULT 'web',
    "last_seen_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "notification_tokens_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "notifications" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "reminder_id" INTEGER,
    "title" TEXT NOT NULL,
    "body" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'UNREAD',
    "scheduled_for" TIMESTAMPTZ,
    "sent_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "notifications_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "users_email_key" ON "users"("email");
CREATE UNIQUE INDEX "users_dashboard_access_key_key" ON "users"("dashboard_access_key");
CREATE UNIQUE INDEX "patient_profiles_user_id_key" ON "patient_profiles"("user_id");
CREATE UNIQUE INDEX "doctor_profiles_user_id_key" ON "doctor_profiles"("user_id");
CREATE UNIQUE INDEX "payments_reference_key" ON "payments"("reference");
CREATE UNIQUE INDEX "payments_invoice_number_key" ON "payments"("invoice_number");
CREATE UNIQUE INDEX "patient_dashboard_access_doctor_id_patient_id_key" ON "patient_dashboard_access"("doctor_id", "patient_id");
CREATE UNIQUE INDEX "patient_dashboard_otps_code_key" ON "patient_dashboard_otps"("code");
CREATE UNIQUE INDEX "notification_tokens_token_key" ON "notification_tokens"("token");

CREATE INDEX "appointments_user_id_idx" ON "appointments"("user_id");
CREATE INDEX "appointments_doctor_id_idx" ON "appointments"("doctor_id");
CREATE INDEX "appointments_date_idx" ON "appointments"("date");
CREATE INDEX "emergency_bookings_user_id_idx" ON "emergency_bookings"("user_id");
CREATE INDEX "emergency_bookings_doctor_id_idx" ON "emergency_bookings"("doctor_id");
CREATE INDEX "emergency_bookings_status_idx" ON "emergency_bookings"("status");
CREATE INDEX "payments_user_id_idx" ON "payments"("user_id");
CREATE INDEX "payments_appointment_id_idx" ON "payments"("appointment_id");
CREATE INDEX "payments_status_idx" ON "payments"("status");
CREATE INDEX "vitals_user_id_created_at_idx" ON "vitals"("user_id", "created_at");
CREATE INDEX "medications_user_id_idx" ON "medications"("user_id");
CREATE INDEX "reminders_user_id_due_at_idx" ON "reminders"("user_id", "due_at");
CREATE INDEX "reminders_status_idx" ON "reminders"("status");
CREATE INDEX "medical_documents_user_id_created_at_idx" ON "medical_documents"("user_id", "created_at");
CREATE INDEX "medical_documents_category_idx" ON "medical_documents"("category");
CREATE INDEX "medical_documents_scan_status_idx" ON "medical_documents"("scan_status");
CREATE INDEX "medical_ai_analyses_user_id_created_at_idx" ON "medical_ai_analyses"("user_id", "created_at");
CREATE INDEX "medical_ai_analyses_medical_record_id_idx" ON "medical_ai_analyses"("medical_record_id");
CREATE INDEX "medicine_history_patient_id_idx" ON "medicine_history"("patient_id");
CREATE INDEX "health_risk_predictions_patient_id_created_at_idx" ON "health_risk_predictions"("patient_id", "created_at");
CREATE INDEX "health_tips_patient_id_created_at_idx" ON "health_tips"("patient_id", "created_at");
CREATE INDEX "doctor_summaries_patient_id_generated_at_idx" ON "doctor_summaries"("patient_id", "generated_at");
CREATE INDEX "patient_dashboard_access_patient_id_idx" ON "patient_dashboard_access"("patient_id");
CREATE INDEX "patient_dashboard_otps_patient_id_idx" ON "patient_dashboard_otps"("patient_id");
CREATE INDEX "notification_tokens_user_id_idx" ON "notification_tokens"("user_id");
CREATE INDEX "notifications_user_id_created_at_idx" ON "notifications"("user_id", "created_at");
CREATE INDEX "notifications_reminder_id_idx" ON "notifications"("reminder_id");

ALTER TABLE "patient_profiles" ADD CONSTRAINT "patient_profiles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "doctor_profiles" ADD CONSTRAINT "doctor_profiles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "appointments" ADD CONSTRAINT "appointments_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "appointments" ADD CONSTRAINT "appointments_doctor_id_fkey" FOREIGN KEY ("doctor_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "emergency_bookings" ADD CONSTRAINT "emergency_bookings_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "emergency_bookings" ADD CONSTRAINT "emergency_bookings_doctor_id_fkey" FOREIGN KEY ("doctor_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "payments" ADD CONSTRAINT "payments_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "payments" ADD CONSTRAINT "payments_appointment_id_fkey" FOREIGN KEY ("appointment_id") REFERENCES "appointments"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "vitals" ADD CONSTRAINT "vitals_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "medications" ADD CONSTRAINT "medications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "reminders" ADD CONSTRAINT "reminders_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "medical_documents" ADD CONSTRAINT "medical_documents_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "medical_ai_analyses" ADD CONSTRAINT "medical_ai_analyses_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "medical_ai_analyses" ADD CONSTRAINT "medical_ai_analyses_medical_record_id_fkey" FOREIGN KEY ("medical_record_id") REFERENCES "medical_documents"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "medicine_history" ADD CONSTRAINT "medicine_history_patient_id_fkey" FOREIGN KEY ("patient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "health_risk_predictions" ADD CONSTRAINT "health_risk_predictions_patient_id_fkey" FOREIGN KEY ("patient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "health_tips" ADD CONSTRAINT "health_tips_patient_id_fkey" FOREIGN KEY ("patient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "doctor_summaries" ADD CONSTRAINT "doctor_summaries_patient_id_fkey" FOREIGN KEY ("patient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "patient_dashboard_access" ADD CONSTRAINT "patient_dashboard_access_doctor_id_fkey" FOREIGN KEY ("doctor_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "patient_dashboard_access" ADD CONSTRAINT "patient_dashboard_access_patient_id_fkey" FOREIGN KEY ("patient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "patient_dashboard_otps" ADD CONSTRAINT "patient_dashboard_otps_patient_id_fkey" FOREIGN KEY ("patient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "notification_tokens" ADD CONSTRAINT "notification_tokens_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_reminder_id_fkey" FOREIGN KEY ("reminder_id") REFERENCES "reminders"("id") ON DELETE CASCADE ON UPDATE CASCADE;
