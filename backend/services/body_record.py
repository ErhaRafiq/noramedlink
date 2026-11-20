"""A patient's dated weight and height history (database side of services/body_measurements.py).

The patient enters and corrects their own readings; a doctor with an active access grant can add readings
and can change or remove the ones a doctor entered. Nobody can change a reading entered by the other role.
Nothing is hard-deleted ("removed" hides a reading). Every add, change and removal is written to the audit
log with a label only ("weight", "height"), never the values.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import BodyMeasurement, PatientHealthEntry, User
from schemas import (
    BodyMeasurementIn,
    BodyMeasurementOut,
    BodyMeasurementUpdate,
    BodySummaryOut,
    DoctorBodySummaryOut,
    LatestReadingOut,
    WeightChangeOut,
)
from services import audit
from services import body_measurements as bm

MAX_READINGS = 500
PATIENT_BMI_NOTE = "This number is not a verdict. Your doctor can tell you what it means for you."
DISCLAIMER = (
    "Advisory only, for physician review: not a diagnosis. Weight change flags and the BMI category follow "
    "published criteria; the freshness limits are an app rule (demo)."
)


def _bad_request(error: bm.MeasurementError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))


def history_query(db: Session, patient_id: int):
    """The patient's active readings, newest first (by measured date, then by when they were entered)."""
    return (
        db.query(BodyMeasurement)
        .filter(BodyMeasurement.patient_id == patient_id, BodyMeasurement.status == "active")
        .order_by(BodyMeasurement.measured_on.desc(), BodyMeasurement.id.desc())
    )


def rows_for(db: Session, patient_id: int) -> list[BodyMeasurement]:
    return history_query(db, patient_id).all()


def _doctor_names(db: Session, rows: list[BodyMeasurement]) -> dict[int, str]:
    ids = {r.added_by_id for r in rows if r.added_by_id and r.added_by_role == "doctor"}
    return {u.id: u.full_name for u in db.query(User).filter(User.id.in_(ids))} if ids else {}


def out_for(db: Session, rows: list[BodyMeasurement]) -> list[BodyMeasurementOut]:
    names = _doctor_names(db, rows)
    return [
        BodyMeasurementOut(
            id=r.id,
            weight_kg=float(r.weight_kg) if r.weight_kg is not None else None,
            height_cm=float(r.height_cm) if r.height_cm is not None else None,
            measured_on=r.measured_on,
            added_by_role=r.added_by_role,
            added_by_name=names.get(r.added_by_id) if r.added_by_role == "doctor" else None,
            created_at=r.created_at,
        )
        for r in rows
    ]


# --- changing the history ------------------------------------------------------------------------------


def _label(weight: float | None, height: float | None) -> str:
    return (
        "weight and height"
        if weight is not None and height is not None
        else "weight"
        if weight is not None
        else "height"
    )


def add(db: Session, patient: User, author: User, payload: BodyMeasurementIn) -> BodyMeasurement:
    try:
        weight, height, when = bm.validate_input(
            payload.weight, payload.weight_unit, payload.height_cm, payload.measured_on
        )
    except bm.MeasurementError as error:
        raise _bad_request(error) from error
    if (
        db.query(BodyMeasurement.id)
        .filter(BodyMeasurement.patient_id == patient.id, BodyMeasurement.status == "active")
        .count()
        >= MAX_READINGS
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"The history is full ({MAX_READINGS} readings). Remove one that is wrong."
        )
    row = BodyMeasurement(
        patient_id=patient.id,
        weight_kg=weight,
        height_cm=height,
        measured_on=when,
        added_by_id=author.id,
        added_by_role="doctor" if author.id != patient.id else "patient",
    )
    db.add(row)
    db.flush()
    audit.record(
        db, author, "body_measurement.add", patient_id=patient.id, target_type="body_measurement",
        target_id=row.id, detail=_label(weight, height), commit=False,
    )  # fmt: skip
    return row


def get_row(db: Session, patient_id: int, row_id: int) -> BodyMeasurement:
    row = (
        db.query(BodyMeasurement)
        .filter(
            BodyMeasurement.id == row_id,
            BodyMeasurement.patient_id == patient_id,
            BodyMeasurement.status == "active",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reading not found.")
    return row


def _only_own(row: BodyMeasurement, role: str) -> None:
    """A patient changes only readings a patient entered; a doctor only readings a doctor entered."""
    if row.added_by_role != role:
        who = "a doctor" if row.added_by_role == "doctor" else "the patient"
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"This reading was entered by {who}, so only {who} can change it."
        )


def update(
    db: Session, row: BodyMeasurement, actor: User, role: str, payload: BodyMeasurementUpdate
) -> BodyMeasurement:
    _only_own(row, role)
    sent = payload.model_fields_set
    weight = row.weight_kg
    height = row.height_cm
    when = row.measured_on
    if "weight" in sent:
        weight = None if payload.weight is None else payload.weight
        unit = payload.weight_unit
    else:
        unit = "kg"
    if "height_cm" in sent:
        height = payload.height_cm
    if "measured_on" in sent and payload.measured_on is not None:
        when = payload.measured_on
    try:
        weight_kg, height_cm, when = bm.validate_input(
            float(weight) if weight is not None else None,
            unit if "weight" in sent else "kg",
            float(height) if height is not None else None,
            when,
        )
    except bm.MeasurementError as error:
        raise _bad_request(error) from error
    row.weight_kg, row.height_cm, row.measured_on = weight_kg, height_cm, when
    audit.record(
        db, actor, "body_measurement.update", patient_id=row.patient_id, target_type="body_measurement",
        target_id=row.id, detail=_label(weight_kg, height_cm), commit=False,
    )  # fmt: skip
    return row


def remove(db: Session, row: BodyMeasurement, actor: User, role: str) -> None:
    _only_own(row, role)
    row.status = "removed"
    audit.record(
        db, actor, "body_measurement.remove", patient_id=row.patient_id, target_type="body_measurement",
        target_id=row.id, detail=_label(row.weight_kg, row.height_cm), commit=False,
    )  # fmt: skip


# --- what the record says now --------------------------------------------------------------------------


def latest_for_profile(db: Session, patient_id: int) -> dict[str, Any]:
    rows = rows_for(db, patient_id)
    weight = bm.latest(bm.readings(rows, "weight_kg"))
    height = bm.latest(bm.readings(rows, "height_cm"))
    return {
        "latest_weight_kg": weight.value if weight else None,
        "latest_weight_date": weight.measured_on if weight else None,
        "latest_height_cm": height.value if height else None,
        "latest_height_date": height.measured_on if height else None,
    }


def is_marked_pregnant(db: Session, patient_id: int) -> bool:
    """The app has no pregnancy field: a patient or doctor marks it by adding "pregnancy" to the health
    record (any active entry whose name contains "pregnan"). Without it the BMI category is not withheld."""
    names = db.query(PatientHealthEntry.name).filter(
        PatientHealthEntry.patient_id == patient_id, PatientHealthEntry.status == "active"
    )
    return any("pregnan" in (name or "").lower() for (name,) in names)


def _latest_out(reading: bm.Reading | None) -> LatestReadingOut | None:
    return (
        LatestReadingOut(value=reading.value, measured_on=reading.measured_on, added_by_role=reading.added_by_role)
        if reading
        else None
    )


def _change_out(change: bm.WeightChange | None) -> WeightChangeOut | None:
    if change is None:
        return None
    return WeightChangeOut(
        percent=change.percent, from_kg=change.from_kg, from_date=change.from_date, to_kg=change.to_kg,
        to_date=change.to_date, window_days=change.window_days, threshold_percent=change.threshold_percent,
        wording=change.wording, basis=change.basis,
    )  # fmt: skip


def patient_summary(db: Session, patient_id: int) -> BodySummaryOut:
    rows = rows_for(db, patient_id)
    weight = bm.latest(bm.readings(rows, "weight_kg"))
    height = bm.latest(bm.readings(rows, "height_cm"))
    number = bm.bmi(weight.value if weight else None, height.value if height else None)
    return BodySummaryOut(
        weight=_latest_out(weight), height=_latest_out(height), bmi=number,
        bmi_note=PATIENT_BMI_NOTE if number is not None else None,
    )  # fmt: skip


def doctor_summary(db: Session, patient: User, age: int | None) -> DoctorBodySummaryOut:
    rows = rows_for(db, patient.id)
    weights = bm.readings(rows, "weight_kg")
    weight = bm.latest(weights)
    height = bm.latest(bm.readings(rows, "height_cm"))
    result = bm.bmi_result(
        weight.value if weight else None, height.value if height else None, age, is_marked_pregnant(db, patient.id)
    )
    return DoctorBodySummaryOut(
        weight=_latest_out(weight),
        height=_latest_out(height),
        bmi=result.value if result else None,
        bmi_note=None,
        bmi_category=result.category if result else None,
        bmi_category_note=result.category_note if result else None,
        bmi_asian_note=result.asian_note if result else None,
        weight_current=bm.weight_is_current(weight.measured_on, age) if weight else None,
        weight_max_age_days=bm.weight_max_age_days(age),
        weight_change_flags=[_change_out(c) for c in bm.weight_change_flags(weights)],
        change_since_previous=_change_out(bm.change_since_previous(weights)),
        disclaimer=DISCLAIMER,
    )
