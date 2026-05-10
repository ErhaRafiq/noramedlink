CREATE TABLE "medical_departments" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "icon" TEXT,
    "description" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "medical_departments_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "patient_reports" (
    "id" SERIAL NOT NULL,
    "patient_id" INTEGER NOT NULL,
    "department_id" INTEGER,
    "title" TEXT NOT NULL,
    "original_file_name" TEXT NOT NULL,
    "file_url" TEXT NOT NULL,
    "file_type" TEXT NOT NULL,
    "extracted_text" TEXT,
    "formatted_text" TEXT,
    "structured_data_json" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "summary" TEXT,
    "ocr_status" TEXT NOT NULL DEFAULT 'PENDING',
    "ocr_confidence" DOUBLE PRECISION,
    "upload_date" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "patient_reports_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "medical_departments_name_key" ON "medical_departments"("name");
CREATE INDEX "patient_reports_patient_id_upload_date_idx" ON "patient_reports"("patient_id", "upload_date");
CREATE INDEX "patient_reports_department_id_idx" ON "patient_reports"("department_id");
CREATE INDEX "patient_reports_ocr_status_idx" ON "patient_reports"("ocr_status");

ALTER TABLE "patient_reports" ADD CONSTRAINT "patient_reports_patient_id_fkey" FOREIGN KEY ("patient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "patient_reports" ADD CONSTRAINT "patient_reports_department_id_fkey" FOREIGN KEY ("department_id") REFERENCES "medical_departments"("id") ON DELETE SET NULL ON UPDATE CASCADE;

INSERT INTO "medical_departments" ("name", "icon", "description")
VALUES
    ('Heart', 'heart-pulse', 'Cardiology, ECG, lipids, blood pressure, and heart-related reports.'),
    ('Kidney', 'activity', 'Renal, creatinine, urea, eGFR, and kidney function reports.'),
    ('Ortho', 'bone', 'Orthopedic, x-ray, fracture, spine, knee, and bone-related reports.'),
    ('General', 'stethoscope', 'General medical records and reports that do not match a specialist department.'),
    ('Medicine', 'pill', 'Prescriptions, dosage plans, tablets, capsules, and medicine notes.'),
    ('Lab', 'test-tube', 'CBC, glucose, hemoglobin, platelet, lipid profile, and blood test reports.')
ON CONFLICT ("name") DO NOTHING;

INSERT INTO "patient_reports" (
    "patient_id",
    "department_id",
    "title",
    "original_file_name",
    "file_url",
    "file_type",
    "extracted_text",
    "formatted_text",
    "structured_data_json",
    "summary",
    "ocr_status",
    "ocr_confidence",
    "upload_date",
    "updated_at"
)
SELECT
    md."user_id",
    dept."id",
    md."title",
    md."file_name",
    md."file_url",
    md."file_type",
    COALESCE(md."ocr_raw_text", md."extracted_text"),
    COALESCE(md."edited_ocr_text", md."extracted_text"),
    CASE
        WHEN jsonb_typeof(md."structured_sections") = 'object' THEN md."structured_sections"
        ELSE '{}'::jsonb
    END,
    md."ai_summary",
    CASE
        WHEN lower(md."scan_status") IN ('processed', 'reviewed', 'scanned_optiic', 'scanned_local') THEN 'COMPLETED'
        WHEN lower(md."scan_status") IN ('scan_failed', 'failed') THEN 'FAILED'
        WHEN lower(md."scan_status") = 'needs_review' THEN 'NEEDS_REVIEW'
        ELSE 'PENDING'
    END,
    md."confidence_score",
    md."created_at",
    md."updated_at"
FROM "medical_documents" md
JOIN "medical_departments" dept ON dept."name" = CASE
    WHEN lower(md."category") IN ('cardiology', 'heart') THEN 'Heart'
    WHEN lower(md."category") IN ('nephrology', 'kidney') THEN 'Kidney'
    WHEN lower(md."category") IN ('orthopedics', 'ortho') THEN 'Ortho'
    WHEN lower(md."category") IN ('medicine', 'prescription') THEN 'Medicine'
    WHEN lower(md."category") IN ('lab', 'pathology') THEN 'Lab'
    WHEN CONCAT_WS(' ', md."title", md."file_name", md."extracted_text", md."ocr_raw_text", md."edited_ocr_text") ~* '(ecg|cardiac|troponin|cholesterol|heart|cardiology|blood pressure)' THEN 'Heart'
    WHEN CONCAT_WS(' ', md."title", md."file_name", md."extracted_text", md."ocr_raw_text", md."edited_ocr_text") ~* '(creatinine|kidney|renal|nephro|urea|egfr)' THEN 'Kidney'
    WHEN CONCAT_WS(' ', md."title", md."file_name", md."extracted_text", md."ocr_raw_text", md."edited_ocr_text") ~* '(fracture|bone|spine|knee|orthopedic|xray)' THEN 'Ortho'
    WHEN CONCAT_WS(' ', md."title", md."file_name", md."extracted_text", md."ocr_raw_text", md."edited_ocr_text") ~* '(prescription|tablet|capsule|dosage|medicine)' THEN 'Medicine'
    WHEN CONCAT_WS(' ', md."title", md."file_name", md."extracted_text", md."ocr_raw_text", md."edited_ocr_text") ~* '(cbc|glucose|hemoglobin|blood test|platelet|lipid profile)' THEN 'Lab'
    ELSE 'General'
END
WHERE NOT EXISTS (
    SELECT 1
    FROM "patient_reports" pr
    WHERE pr."patient_id" = md."user_id"
      AND pr."file_url" = md."file_url"
      AND pr."original_file_name" = md."file_name"
      AND pr."upload_date" = md."created_at"
);
