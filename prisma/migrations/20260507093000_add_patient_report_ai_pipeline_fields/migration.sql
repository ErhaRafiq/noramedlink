ALTER TABLE "patient_reports"
ADD COLUMN IF NOT EXISTS "extracted_entities" JSONB NOT NULL DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS "rule_warnings" JSONB NOT NULL DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS "validation_status" TEXT NOT NULL DEFAULT 'SAFE',
ADD COLUMN IF NOT EXISTS "validation_results" JSONB NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS "clinical_summary_json" JSONB NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS "llm_self_check" JSONB NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS "summary_source" TEXT NOT NULL DEFAULT 'rule_based';

ALTER TABLE "medical_ai_analyses"
ADD COLUMN IF NOT EXISTS "patient_report_id" INTEGER;

CREATE INDEX IF NOT EXISTS "patient_reports_validation_status_idx" ON "patient_reports"("validation_status");
CREATE INDEX IF NOT EXISTS "medical_ai_analyses_patient_report_id_idx" ON "medical_ai_analyses"("patient_report_id");

ALTER TABLE "medical_ai_analyses"
DROP CONSTRAINT IF EXISTS "medical_ai_analyses_patient_report_id_fkey";

ALTER TABLE "medical_ai_analyses"
ADD CONSTRAINT "medical_ai_analyses_patient_report_id_fkey"
FOREIGN KEY ("patient_report_id") REFERENCES "patient_reports"("id")
ON DELETE CASCADE ON UPDATE CASCADE;
