"""FE-4: versions of the clinical summary, and when a version is out of date.

A version stores a fingerprint of everything it was built from: each report's stored text, fields
and OCR rows, the vitals and medicines entered in the app, and the versions of the extractor, the
lab rules and the summary. When the fingerprint of the patient's data no longer matches the
current version, that version is out of date. Regenerating adds a new version (the trigger says
what changed); earlier versions are kept.

Nothing here writes to a report. A report whose stored entities come from an older extractor is
re-read from its stored text in memory (identifiers removed first); only the summary is stored.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import ClinicalSummary, Medication, MedicineHistory, PatientReport, PatientVital, User, Vitals
from services.icse.entities import ENTITIES_VERSION, extract_entities
from services.icse.flags import printed_date
from services.icse.summary import SUMMARY_VERSION, build_content, render_text
from services.lab_rules import LAB_RULES_VERSION
from services.privacy import patient_identity_patterns, redact_identifiers


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _report_text(report: PatientReport) -> str:
    return (report.formatted_text or report.extracted_text or "").strip()


def _readable(report: PatientReport) -> bool:
    structured = report.structured_data_json or {}
    return bool(_report_text(report)) and report.ocr_status != "FAILED" and not structured.get("error")


def _report_source(report: PatientReport, identity: list) -> tuple[dict[str, Any], bool]:
    """A report as a summary source; True when its entities had to be re-read (older extractor)."""
    structured = report.structured_data_json or {}
    stored = structured.get("clinical_entities")
    if structured.get("clinical_entities_version") == ENTITIES_VERSION and isinstance(stored, list):
        entities, rebuilt = stored, False
    else:
        entities = extract_entities(
            redact_identifiers(_report_text(report), identity),
            structured.get("bio_bert_entities") or [],
            structured.get("fields") or {},
            structured.get("ocr_rows") or [],
        )
        rebuilt = True
    printed = printed_date(entities)
    return {
        "report_id": report.id,
        "title": report.title,
        "kind": "report",
        "date": printed,
        "date_source": "printed in report" if printed else None,
        "upload_date": report.upload_date.date().isoformat() if report.upload_date else None,
        "entities": entities,
    }, rebuilt


def _vitals_source(key: str, recorded: datetime | None, text: str) -> dict[str, Any]:
    entities = [{**e, "method": "entered by patient"} for e in extract_entities(text)]
    day = recorded.date().isoformat() if recorded else None
    return {
        "report_id": key,
        "title": "Vitals entered in the app",
        "kind": "vitals",
        "date": day,
        "date_source": "recorded in the app" if day else None,
        "upload_date": day,
        "entities": [e for e in entities if e["type"] in ("vital", "test_result")],
    }


def gather(db: Session, patient: User) -> dict[str, Any]:
    """Everything the summary is built from, and the manifest its fingerprint is taken over."""
    identity = patient_identity_patterns(patient)
    reports = db.query(PatientReport).filter(PatientReport.patient_id == patient.id).all()
    sources, unreadable, rebuilt, manifest_reports = [], [], 0, {}
    for report in reports:
        structured = report.structured_data_json or {}
        manifest_reports[str(report.id)] = _hash(
            [_report_text(report), report.ocr_status, structured.get("fields"), structured.get("ocr_rows")]
        )
        if not _readable(report):
            unreadable.append({"report_id": report.id, "title": report.title, "kind": "report"})
            continue
        source, was_rebuilt = _report_source(report, identity)
        rebuilt += was_rebuilt
        sources.append(source)

    vitals_rows = db.query(PatientVital).filter(PatientVital.patient_id == patient.id).all()
    basic_rows = db.query(Vitals).filter(Vitals.user_id == patient.id).all()
    for row in vitals_rows:
        text = f"BP {row.blood_pressure_systolic}/{row.blood_pressure_diastolic} mmHg\nSpO2 {row.spo2} %"
        if row.sugar_level is not None:
            text += f"\nBlood Glucose {row.sugar_level:g}"
        sources.append(_vitals_source(f"vitals:{row.id}", row.recorded_at, text))
    for row in basic_rows:
        text = f"BP {row.blood_pressure}\nBlood Glucose {row.sugar_level}"
        sources.append(_vitals_source(f"basic-vitals:{row.id}", row.created_at, text))
    # Oldest first: by printed or recorded date, else upload date (only printed or recorded dates
    # are used for persistent and trend flags).
    sources.sort(key=lambda s: (s.get("date") or s.get("upload_date") or "", str(s["report_id"])))

    medications = [
        {"name": m.name, "dosage": m.dosage, "instructions": m.instructions, "status": m.status,
         "start_date": m.start_date.isoformat() if m.start_date else None,
         "end_date": m.end_date.isoformat() if m.end_date else None, "list": "medication schedule"}
        for m in db.query(Medication).filter(Medication.user_id == patient.id).all()
    ] + [
        {"name": m.medicine_name, "dosage": m.dosage, "frequency": m.frequency, "reason": m.reason,
         "start_date": m.start_date.isoformat() if m.start_date else None,
         "end_date": m.end_date.isoformat() if m.end_date else None, "list": "medicine history"}
        for m in db.query(MedicineHistory).filter(MedicineHistory.patient_id == patient.id).all()
    ]  # fmt: skip

    manifest = {
        "versions": {"summary": SUMMARY_VERSION, "entities": ENTITIES_VERSION, "lab_rules": LAB_RULES_VERSION},
        "reports": manifest_reports,
        "vitals": _hash(sorted((s["report_id"], s["date"], s["entities"]) for s in sources if s["kind"] == "vitals")),
        "medications": _hash(sorted(medications, key=lambda m: json.dumps(m, sort_keys=True))),
    }
    return {
        "sources": sources,
        "unreadable": unreadable,
        "medications": medications,
        "manifest": manifest,
        "fingerprint": _hash(manifest),
        "rebuilt_reports": rebuilt,
    }


def describe_change(previous: dict | None, current: dict) -> str:
    """What changed between two manifests, in words (the version's trigger)."""
    if not previous:
        return "First summary for this patient."
    changes = []
    before, after = previous.get("reports", {}), current["reports"]
    added = [k for k in after if k not in before]
    removed = [k for k in before if k not in after]
    changed = [k for k in after if k in before and before[k] != after[k]]
    if added:
        changes.append(f"{len(added)} report(s) added")
    if changed:
        changes.append(f"{len(changed)} report(s) edited or re-read")
    if removed:
        changes.append(f"{len(removed)} report(s) deleted")
    if previous.get("vitals") != current["vitals"]:
        changes.append("vitals changed")
    if previous.get("medications") != current["medications"]:
        changes.append("medicines changed")
    if previous.get("versions") != current["versions"]:
        changes.append("summary rules updated")
    return ("; ".join(changes) or "No change in the patient's data") + "."


def current_version(db: Session, patient_id: int) -> ClinicalSummary | None:
    return (
        db.query(ClinicalSummary)
        .filter(ClinicalSummary.patient_id == patient_id, ClinicalSummary.is_current.is_(True))
        .order_by(ClinicalSummary.version.desc())
        .first()
    )


def status(db: Session, patient: User) -> dict[str, Any]:
    """The current version (or None) and whether it is out of date. Never writes."""
    summary = current_version(db, patient.id)
    inputs = gather(db, patient)
    stale = summary is None or summary.input_fingerprint != inputs["fingerprint"]
    previous = (summary.content_json or {}).get("inputs", {}).get("manifest") if summary else None
    return {
        "summary": summary,
        "out_of_date": stale,
        "pending_change": describe_change(previous, inputs["manifest"]) if stale else None,
    }


def regenerate(db: Session, patient: User, doctor: User, today: date | None = None) -> tuple[ClinicalSummary, bool]:
    """Build the summary now. A new version is added only when the inputs changed; returns
    (the current version, whether it is new)."""
    inputs = gather(db, patient)
    existing = current_version(db, patient.id)
    if existing and existing.input_fingerprint == inputs["fingerprint"]:
        return existing, False
    content = build_content(inputs["sources"], inputs["medications"], inputs["unreadable"], today or date.today())
    previous = (existing.content_json or {}).get("inputs", {}).get("manifest") if existing else None
    content["inputs"] = {
        "manifest": inputs["manifest"],
        "reports_used": sum(1 for s in inputs["sources"] if s["kind"] == "report"),
        "reports_reread": inputs["rebuilt_reports"],
    }
    number = (
        db.query(func.max(ClinicalSummary.version)).filter(ClinicalSummary.patient_id == patient.id).scalar() or 0
    ) + 1
    if existing:
        existing.is_current = False
    summary = ClinicalSummary(
        patient_id=patient.id,
        version=number,
        generated_at=datetime.now(UTC),
        generated_by_id=doctor.id,
        trigger=describe_change(previous, inputs["manifest"])[:300],
        input_fingerprint=inputs["fingerprint"],
        content_json=content,
        summary_text=render_text(content),
        source="rule_based",
        is_current=True,
    )
    db.add(summary)
    try:
        db.commit()
    except IntegrityError:  # another request added this version number first: use that one
        db.rollback()
        return current_version(db, patient.id), False
    db.refresh(summary)
    return summary, True
