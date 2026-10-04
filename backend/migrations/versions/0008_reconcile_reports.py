"""reconcile medical_documents into patient_reports (approved Batch C mapping)

Additive and safe to re-run:
1. patient_reports gains notes and legacy_medical_document_id (unique, no FK); file_url
   is widened to TEXT so legacy embedded data: images fit.
2. The six standard departments are added if missing.
3. Every medical_documents row is copied once into patient_reports (mapping below).
   Rows that Prisma's earlier copy (migration 20260506234500) already made are matched
   on patient, file URL, file name and upload time and only get their legacy id.
4. medical_ai_analyses rows linked to a medical document also get patient_report_id
   (medical_record_id is kept).

medical_documents is never modified or deleted. Everything runs in one transaction.

Revision ID: 0008
Revises: 0007
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_INDEX = "patient_reports_legacy_medical_document_id_key"
NOT_VALIDATED = "NOT_VALIDATED"
LEGACY_SOURCE = "legacy_medical_document"

# Frozen copies (services may change later; this migration must not).
DEPARTMENTS = [
    ("Heart", "heart-pulse", "Cardiology, ECG, lipids, blood pressure, and heart-related reports."),
    ("Kidney", "activity", "Renal, creatinine, urea, eGFR, and kidney function reports."),
    ("Ortho", "bone", "Orthopedic, x-ray, fracture, spine, knee, and bone-related reports."),
    ("General", "stethoscope", "General medical records and reports that do not match a specialist department."),
    ("Medicine", "pill", "Prescriptions, dosage plans, tablets, capsules, and medicine notes."),
    ("Lab", "test-tube", "CBC, glucose, hemoglobin, platelet, lipid profile, and blood test reports."),
]
CATEGORY_DEPARTMENTS = {
    "cardiology": "Heart", "heart": "Heart",
    "nephrology": "Kidney", "kidney": "Kidney",
    "orthopedics": "Ortho", "ortho": "Ortho",
    "medicine": "Medicine", "prescription": "Medicine",
    "lab": "Lab", "pathology": "Lab",
}
DEPARTMENT_KEYWORDS = {  # same lists and order as services/ocr_space_service.py
    "Heart": ["ecg", "cardiac", "troponin", "cholesterol", "heart", "cardiology", "blood pressure"],
    "Kidney": ["creatinine", "kidney", "renal", "nephro", "urea", "egfr"],
    "Ortho": ["fracture", "bone", "spine", "knee", "orthopedic", "xray", "x-ray"],
    "Lab": ["cbc", "glucose", "hemoglobin", "haemoglobin", "blood test", "platelet", "lipid profile"],
    "Medicine": ["prescription", "tablet", "capsule", "dosage", "medicine"],
}
COMPLETED_SCAN_STATUSES = {"SCANNED_OCR_SPACE", "SCANNED_LOCAL", "PROCESSED", "REVIEWED"}
FAILED_SCAN_STATUSES = {"SCAN_FAILED", "FAILED"}

documents = sa.table(
    "medical_documents",
    sa.column("id", sa.Integer), sa.column("user_id", sa.Integer), sa.column("title", sa.String),
    sa.column("category", sa.String), sa.column("notes", sa.Text), sa.column("file_name", sa.String),
    sa.column("file_url", sa.Text), sa.column("file_type", sa.String), sa.column("extracted_text", sa.Text),
    sa.column("ocr_raw_text", sa.Text), sa.column("edited_ocr_text", sa.Text), sa.column("ai_summary", sa.Text),
    sa.column("extracted_entities", sa.JSON), sa.column("confidence_score", sa.Float),
    sa.column("possible_report_type", sa.String), sa.column("detected_keywords", sa.JSON),
    sa.column("structured_sections", sa.JSON), sa.column("scan_status", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
)
reports = sa.table(
    "patient_reports",
    sa.column("id", sa.Integer), sa.column("patient_id", sa.Integer), sa.column("department_id", sa.Integer),
    sa.column("title", sa.String), sa.column("notes", sa.Text), sa.column("original_file_name", sa.String),
    sa.column("file_url", sa.Text), sa.column("file_type", sa.String), sa.column("extracted_text", sa.Text),
    sa.column("formatted_text", sa.Text), sa.column("structured_data_json", sa.JSON), sa.column("summary", sa.Text),
    sa.column("extracted_entities", sa.JSON), sa.column("rule_warnings", sa.JSON),
    sa.column("validation_status", sa.String), sa.column("validation_results", sa.JSON),
    sa.column("clinical_summary_json", sa.JSON), sa.column("llm_self_check", sa.JSON),
    sa.column("summary_source", sa.String), sa.column("ocr_status", sa.String), sa.column("ocr_confidence", sa.Float),
    sa.column("upload_date", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("legacy_medical_document_id", sa.Integer),
)
departments = sa.table(
    "medical_departments",
    sa.column("id", sa.Integer), sa.column("name", sa.String), sa.column("icon", sa.String),
    sa.column("description", sa.Text),
)


def _department_for(doc) -> str:
    category = (doc.category or "").strip().lower()
    if category in CATEGORY_DEPARTMENTS:
        return CATEGORY_DEPARTMENTS[category]
    haystack = " ".join(
        part for part in (doc.title, doc.file_name, doc.extracted_text, doc.ocr_raw_text, doc.edited_ocr_text) if part
    ).lower()
    for name, keywords in DEPARTMENT_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return name
    return "General"


def _ocr_status(scan_status: str | None) -> str:
    value = (scan_status or "").strip().upper()
    if value in COMPLETED_SCAN_STATUSES:
        return "COMPLETED"
    if value in FAILED_SCAN_STATUSES:
        return "FAILED"
    return "PENDING"


def _file_type(doc) -> str:
    current = (doc.file_type or "").strip().lower()
    if current and current != "unknown":
        return doc.file_type
    match = re.match(r"data:([a-z]+)/([a-z0-9.+-]+)[;,]", doc.file_url or "", re.I)
    if match:
        return match.group(2).lower()
    extension = re.search(r"\.([a-z0-9]{2,5})$", doc.file_name or "", re.I)
    return extension.group(1).lower() if extension else (doc.file_type or "unknown")


def _is_untouched_default(report) -> bool:
    """True if a Prisma-copied report still has the table defaults (never validated)."""
    return (
        (report.validation_status or "").upper() == "SAFE"
        and not report.validation_results
        and not report.clinical_summary_json
        and not report.rule_warnings
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"]: c for c in inspector.get_columns("patient_reports")}

    # 1. Schema (additive).
    if "notes" not in columns:
        op.add_column("patient_reports", sa.Column("notes", sa.Text(), nullable=True))
    if "legacy_medical_document_id" not in columns:
        op.add_column("patient_reports", sa.Column("legacy_medical_document_id", sa.Integer(), nullable=True))
    if not isinstance(columns["file_url"]["type"], sa.Text):
        with op.batch_alter_table("patient_reports") as batch:
            batch.alter_column("file_url", type_=sa.Text(), existing_nullable=False)
    if LEGACY_INDEX not in {ix["name"] for ix in inspector.get_indexes("patient_reports")}:
        op.create_index(LEGACY_INDEX, "patient_reports", ["legacy_medical_document_id"], unique=True)

    # 2. Departments.
    existing = {row.name for row in bind.execute(sa.select(departments.c.name))}
    missing = [{"name": n, "icon": i, "description": d} for n, i, d in DEPARTMENTS if n not in existing]
    if missing:
        bind.execute(departments.insert(), missing)
    department_ids = {row.name: row.id for row in bind.execute(sa.select(departments.c.id, departments.c.name))}

    # 3. Copy documents not yet linked to a report.
    linked = {row[0] for row in bind.execute(
        sa.select(reports.c.legacy_medical_document_id).where(reports.c.legacy_medical_document_id.is_not(None))
    )}
    for doc in bind.execute(sa.select(documents).order_by(documents.c.id)).fetchall():
        if doc.id in linked:
            continue

        earlier_copy = bind.execute(
            sa.select(reports).where(
                reports.c.legacy_medical_document_id.is_(None),
                reports.c.patient_id == doc.user_id,
                reports.c.file_url == doc.file_url,
                reports.c.original_file_name == doc.file_name,
                reports.c.upload_date == doc.created_at,
            ).order_by(reports.c.id).limit(1)
        ).first()
        if earlier_copy is not None:
            values = {"legacy_medical_document_id": doc.id}
            if _is_untouched_default(earlier_copy):
                values.update(validation_status=NOT_VALIDATED, summary_source=LEGACY_SOURCE)
            if doc.notes and not earlier_copy.notes:
                values["notes"] = doc.notes
            bind.execute(reports.update().where(reports.c.id == earlier_copy.id).values(**values))
            continue

        bind.execute(reports.insert().values(
            patient_id=doc.user_id,
            department_id=department_ids.get(_department_for(doc)) or department_ids.get("General"),
            title=doc.title,
            notes=doc.notes,
            original_file_name=doc.file_name,
            file_url=doc.file_url,
            file_type=_file_type(doc),
            extracted_text=doc.ocr_raw_text if doc.ocr_raw_text is not None else doc.extracted_text,
            formatted_text=doc.edited_ocr_text if doc.edited_ocr_text is not None else doc.extracted_text,
            structured_data_json={
                "fields": doc.structured_sections if isinstance(doc.structured_sections, dict) else {},
                "detected_keywords": doc.detected_keywords if isinstance(doc.detected_keywords, list) else [],
                "legacy_possible_report_type": doc.possible_report_type,
            },
            summary=doc.ai_summary,
            extracted_entities=doc.extracted_entities if isinstance(doc.extracted_entities, list) else [],
            rule_warnings=[],
            validation_status=NOT_VALIDATED,
            validation_results={},
            clinical_summary_json={},
            llm_self_check={},
            summary_source=LEGACY_SOURCE,
            ocr_status=_ocr_status(doc.scan_status),
            ocr_confidence=doc.confidence_score,
            upload_date=doc.created_at,
            updated_at=doc.updated_at,
            legacy_medical_document_id=doc.id,
        ))

    # 4. Relink AI analyses of medical documents to the matching report (keep the old link).
    bind.execute(sa.text(
        """
        UPDATE medical_ai_analyses
        SET patient_report_id = (
            SELECT pr.id FROM patient_reports pr
            WHERE pr.legacy_medical_document_id = medical_ai_analyses.medical_record_id
        )
        WHERE patient_report_id IS NULL
          AND medical_record_id IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM patient_reports pr
            WHERE pr.legacy_medical_document_id = medical_ai_analyses.medical_record_id
          )
        """
    ))


def downgrade() -> None:
    # Undoing the copy would delete reports and analysis links; refuse instead.
    raise NotImplementedError("0008 cannot be downgraded without data loss.")
