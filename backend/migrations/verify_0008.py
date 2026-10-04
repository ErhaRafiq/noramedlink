"""Verify migration 0008 (medical_documents -> patient_reports) on a scratch database.

Usage (from backend/, scratch database already created and empty):
    python migrations/verify_0008.py prisma    # scratch built by `prisma migrate deploy`
    python migrations/verify_0008.py fastapi   # scratch built by Alembic 0001-0007

Never touches the main database: it only connects to SCRATCH_DB on a local server.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from database import DATABASE_URL  # noqa: E402

SCRATCH_DB = "noramedlink_alembic_check"
mode = sys.argv[1]
assert mode in {"prisma", "fastapi"}

base = make_url(DATABASE_URL)
assert base.host in {"localhost", "127.0.0.1", "::1"}, "scratch checks run only against a local server"
engine = create_engine(base.set(database=SCRATCH_DB))
results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))


def alembic(*args: str) -> None:
    run = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"database={SCRATCH_DB}", *args],
        cwd=BACKEND, capture_output=True, text=True, env=dict(os.environ, HF_HUB_OFFLINE="1"),
    )
    if run.returncode != 0:
        sys.exit(f"alembic {' '.join(args)} failed:\n{run.stderr[-2000:]}")


def rows(sql: str, **params):
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def scalar(sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def normalize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


# ---------------------------------------------------------------- 1. migrate to 0007
alembic("upgrade", "0007")
print(f"[{mode}] scratch at 0007; file_url type before:",
      next(c["type"] for c in inspect(engine).get_columns("patient_reports") if c["name"] == "file_url"))

# ---------------------------------------------------------------- 2. seed
SCAN_STATUSES = ["SCANNED_OCR_SPACE", "SCANNED_LOCAL", "PROCESSED", "REVIEWED", "SCAN_FAILED", "FAILED",
                 "UPLOADED", "NEEDS_REVIEW"]
EXPECTED_OCR = {"SCANNED_OCR_SPACE": "COMPLETED", "SCANNED_LOCAL": "COMPLETED", "PROCESSED": "COMPLETED",
                "REVIEWED": "COMPLETED", "SCAN_FAILED": "FAILED", "FAILED": "FAILED", "UPLOADED": "PENDING",
                "NEEDS_REVIEW": "PENDING"}
# A real-length embedded image on Prisma databases (TEXT column); a short one fits FastAPI's VARCHAR(500).
DATA_IMAGE = "data:image/png;base64," + ("iVBORw0KGgo" * (300 if mode == "prisma" else 30))
t0 = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)

with engine.begin() as conn:
    def user(label):
        return conn.execute(text(
            "insert into users (full_name, email, hashed_password, role, phone, is_active, is_email_verified, "
            "is_identity_verified) values (:n, :e, 'x', 'PATIENT', '', true, true, true) returning id"),
            {"n": f"verify-{label}", "e": f"verify-{label}@example.test"}).scalar()

    p1, p2 = user("p1"), user("p2")

    def doc(user_id, title, scan_status, minutes, **extra):
        values = dict(user_id=user_id, title=title, category="general-medicine", notes=None, file_name=f"{title}.jpg",
                      file_url=f"uploads/{user_id}/general/{title}.jpg", file_type="unknown",
                      extracted_text=f"{title} extracted text", ocr_raw_text=None, edited_ocr_text=None,
                      ai_summary=None, extracted_entities="[]", confidence_score=None, possible_report_type=None,
                      detected_keywords="[]", structured_sections="{}", scan_status=scan_status,
                      created_at=t0 + timedelta(minutes=minutes), updated_at=t0 + timedelta(minutes=minutes, seconds=30))
        values.update(extra)
        cols = ", ".join(values)
        params = ", ".join(f":{k}" for k in values)
        return conn.execute(text(f"insert into medical_documents ({cols}) values ({params}) returning id"), values).scalar()

    seeded = {}
    for i, status in enumerate(SCAN_STATUSES):
        seeded[f"status-{status}"] = doc(p1, f"status-{status.lower()}", status, i)
    seeded["image"] = doc(p1, "embedded-image", "SCANNED_LOCAL", 20, file_url=DATA_IMAGE, file_name="photo.png")
    seeded["rich"] = doc(p1, "cardio-report", "SCANNED_OCR_SPACE", 21, category="cardiology", notes="Bring old ECG",
                         ocr_raw_text="RAW text  with  spacing\nline 2", edited_ocr_text="Edited text",
                         ai_summary="Advisory summary", confidence_score=0.83, possible_report_type="ECG",
                         extracted_entities='[{"text": "ECG", "label": "Test"}]', detected_keywords='["ecg", "heart"]',
                         structured_sections='{"heart_rate": "72"}')
    seeded["keyword"] = doc(p2, "renal-panel", "PROCESSED", 22, extracted_text="Serum creatinine 1.9 mg/dL")

    # Rows Prisma's earlier copy (20260506234500) made: one untouched, one later validated.
    def prisma_copy(doc_key, validated):
        d = conn.execute(text("select * from medical_documents where id = :id"), {"id": seeded[doc_key]}).mappings().one()
        dept = conn.execute(text("select id from medical_departments where name = 'General'")).scalar()
        if dept is None:
            dept = conn.execute(text("insert into medical_departments (name, icon, description) "
                                     "values ('General', 'stethoscope', 'x') returning id")).scalar()
        return conn.execute(text(
            "insert into patient_reports (patient_id, department_id, title, original_file_name, file_url, file_type, "
            "extracted_text, formatted_text, structured_data_json, summary, extracted_entities, rule_warnings, "
            "validation_status, validation_results, clinical_summary_json, llm_self_check, summary_source, ocr_status, "
            "upload_date, updated_at) values (:p, :dep, :t, :fn, :fu, :ft, :et, :et, '{}', null, '[]', :rw, :vs, :vr, "
            "'{}', '{}', 'rule_based', 'COMPLETED', :ud, :ud) returning id"),
            {"p": d["user_id"], "dep": dept, "t": d["title"], "fn": d["file_name"], "fu": d["file_url"],
             "ft": d["file_type"], "et": d["extracted_text"], "ud": d["created_at"],
             "rw": '["checked"]' if validated else "[]", "vs": "HIGH_RISK" if validated else "SAFE",
             "vr": '{"glucose": "high"}' if validated else "{}"}).scalar()

    seeded["prior-default"] = doc(p2, "prior-copy-default", "SCANNED_LOCAL", 30)
    seeded["prior-validated"] = doc(p2, "prior-copy-validated", "SCANNED_LOCAL", 31)
    prior_default_report = prisma_copy("prior-default", validated=False)
    prior_validated_report = prisma_copy("prior-validated", validated=True)

    def analysis(user_id, record_id, report_id):
        return conn.execute(text(
            "insert into medical_ai_analyses (user_id, medical_record_id, patient_report_id, source, extracted_entities, "
            "rule_warnings, validation_results) values (:u, :m, :r, 'verify', '[]', '[]', '{}') returning id"),
            {"u": user_id, "m": record_id, "r": report_id}).scalar()

    a_unlinked = analysis(p1, seeded["rich"], None)
    a_prior = analysis(p2, seeded["prior-default"], None)
    other_report = prior_validated_report
    a_already = analysis(p1, seeded["image"], other_report)  # already points at a report: must not change

doc_ids = list(seeded.values())
docs_before = {r["id"]: {k: normalize(v) for k, v in r.items()} for r in rows("select * from medical_documents")}
reports_before = scalar("select count(*) from patient_reports")
expected_new = len(doc_ids) - 2  # two documents were already copied by Prisma
print(f"[{mode}] seeded {len(doc_ids)} documents, {reports_before} existing reports, 3 analyses")

# ---------------------------------------------------------------- 3. migrate to 0008
alembic("upgrade", "0008")
print(f"[{mode}] migrated to 0008")


def report_for(doc_id):
    found = rows("select pr.*, d.name as department from patient_reports pr left join medical_departments d "
                 "on d.id = pr.department_id where pr.legacy_medical_document_id = :id", id=doc_id)
    return found[0] if len(found) == 1 else None


file_url_type = next(c["type"] for c in inspect(engine).get_columns("patient_reports") if c["name"] == "file_url")
check("file_url widened to TEXT", "TEXT" in str(file_url_type).upper(), str(file_url_type))
check("report count = before + new copies", scalar("select count(*) from patient_reports") == reports_before + expected_new,
      f"{scalar('select count(*) from patient_reports')} vs {reports_before + expected_new}")
check("every document has exactly one report", all(report_for(d) for d in doc_ids))
check("six standard departments exist",
      scalar("select count(*) from medical_departments where name in "
             "('Heart','Kidney','Ortho','General','Medicine','Lab')") == 6)

for status in SCAN_STATUSES:
    r = report_for(seeded[f"status-{status}"])
    check(f"scan_status {status} -> ocr_status {EXPECTED_OCR[status]}", r and r["ocr_status"] == EXPECTED_OCR[status],
          str(r and r["ocr_status"]))

image = report_for(seeded["image"])
check("embedded data: image copied exactly", image and image["file_url"] == DATA_IMAGE)
check("data: image file_type from MIME -> png", image and image["file_type"] == "png", str(image and image["file_type"]))

d = docs_before[seeded["rich"]]
r = report_for(seeded["rich"])
structured = r["structured_data_json"] if isinstance(r["structured_data_json"], dict) else json.loads(r["structured_data_json"])
check("title, file name and notes copied exactly",
      (r["title"], r["original_file_name"], r["notes"]) == (d["title"], d["file_name"], d["notes"]))
check("extracted_text = ocr_raw_text (exact, whitespace kept)", r["extracted_text"] == d["ocr_raw_text"])
check("formatted_text = edited_ocr_text (exact)", r["formatted_text"] == d["edited_ocr_text"])
check("summary = ai_summary, ocr_confidence = confidence_score",
      r["summary"] == d["ai_summary"] and r["ocr_confidence"] == d["confidence_score"])
check("entities, keywords, sections and report type preserved",
      normalize(r["extracted_entities"]) == d["extracted_entities"]
      and structured == {"fields": {"heart_rate": "72"}, "detected_keywords": ["ecg", "heart"],
                         "legacy_possible_report_type": "ECG"}, json.dumps(structured))
check("upload_date / updated_at = created_at / updated_at",
      normalize(r["upload_date"]) == d["created_at"] and normalize(r["updated_at"]) == d["updated_at"])
check("category cardiology -> Heart", r["department"] == "Heart", str(r["department"]))
check("new legacy rows are NOT_VALIDATED / legacy_medical_document",
      r["validation_status"] == "NOT_VALIDATED" and r["summary_source"] == "legacy_medical_document")
plain = report_for(seeded["status-UPLOADED"])
check("without ocr_raw/edited text, both fields = extracted_text",
      plain["extracted_text"] == plain["formatted_text"] == docs_before[seeded["status-UPLOADED"]]["extracted_text"])
check("keyword 'creatinine' -> Kidney", report_for(seeded["keyword"])["department"] == "Kidney")
check("no keyword match -> General", plain["department"] == "General")

pd = report_for(seeded["prior-default"])
pv = report_for(seeded["prior-validated"])
check("Prisma's earlier copy reused, not duplicated (untouched one)", pd and pd["id"] == prior_default_report)
check("untouched earlier copy -> NOT_VALIDATED", pd and pd["validation_status"] == "NOT_VALIDATED")
check("validated earlier copy reused and its validation kept",
      pv and pv["id"] == prior_validated_report and pv["validation_status"] == "HIGH_RISK")

links = {r["id"]: r for r in rows("select id, medical_record_id, patient_report_id from medical_ai_analyses")}
check("analysis linked only to a document -> relinked to its report",
      links[a_unlinked]["patient_report_id"] == report_for(seeded["rich"])["id"])
check("analysis of an earlier-copied document -> relinked to that report",
      links[a_prior]["patient_report_id"] == prior_default_report)
check("analysis that already had a report keeps it", links[a_already]["patient_report_id"] == other_report)
check("every analysis keeps its medical_record_id",
      [links[a]["medical_record_id"] for a in (a_unlinked, a_prior, a_already)]
      == [seeded["rich"], seeded["prior-default"], seeded["image"]])
check("every document-linked analysis now has a report",
      scalar("select count(*) from medical_ai_analyses where medical_record_id is not null and patient_report_id is null") == 0)

docs_after = {r["id"]: {k: normalize(v) for k, v in r.items()} for r in rows("select * from medical_documents")}
check("medical_documents unchanged (every row, every column)", docs_after == docs_before)

# ---------------------------------------------------------------- 4. re-run 0008
count_before_rerun = scalar("select count(*) from patient_reports")
snapshot = {r["id"]: {k: normalize(v) for k, v in r.items()} for r in rows("select * from patient_reports")}
alembic("stamp", "0007")
alembic("upgrade", "0008")
check("re-run creates no duplicates", scalar("select count(*) from patient_reports") == count_before_rerun)
check("re-run changes no report", {r["id"]: {k: normalize(v) for k, v in r.items()} for r in rows("select * from patient_reports")} == snapshot)
check("re-run leaves medical_documents unchanged",
      {r["id"]: {k: normalize(v) for k, v in r.items()} for r in rows("select * from medical_documents")} == docs_before)

failed = [name for ok, name in results if not ok]
print(f"[{mode}] {len(results) - len(failed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
