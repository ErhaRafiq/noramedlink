"""Who may change a weight or height reading, how a change is merged and checked, and the pregnancy marker.
No database: the audit call is replaced and the rows are plain objects."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from schemas import BodyMeasurementIn, BodyMeasurementUpdate
from services import body_record


@pytest.fixture(autouse=True)
def audit_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(body_record.audit, "record", lambda *a, **k: calls.append((a[2], k.get("detail"))))
    return calls


def row(by="patient", weight=70.0, height=170.0, on=date(2026, 1, 1), added_by_id=None):
    return SimpleNamespace(
        id=1,
        patient_id=5,
        weight_kg=weight,
        height_cm=height,
        measured_on=on,
        status="active",
        added_by_role=by,
        added_by_id=added_by_id if added_by_id is not None else (5 if by == "patient" else 9),
    )


ME = SimpleNamespace(id=5)


def test_a_patient_changes_their_own_reading_and_it_is_audited_without_values(audit_calls):
    r = row()
    body_record.update(None, r, ME, "patient", BodyMeasurementUpdate(weight=154, weight_unit="lb"))
    assert r.weight_kg == 69.85 and r.height_cm == 170.0
    assert audit_calls == [("body_measurement.update", "weight and height")]
    assert "69" not in audit_calls[0][1]


def test_a_patient_cannot_change_or_remove_a_doctors_reading():
    r = row(by="doctor")
    with pytest.raises(HTTPException) as error:
        body_record.update(None, r, ME, "patient", BodyMeasurementUpdate(weight=60))
    assert error.value.status_code == 403 and r.weight_kg == 70.0
    with pytest.raises(HTTPException) as error:
        body_record.remove(None, r, ME, "patient")
    assert error.value.status_code == 403 and r.status == "active"


def test_a_doctor_cannot_change_or_remove_a_patients_reading():
    r = row(by="patient")
    doctor = SimpleNamespace(id=9)
    with pytest.raises(HTTPException) as error:
        body_record.update(None, r, doctor, "doctor", BodyMeasurementUpdate(weight=60))
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        body_record.remove(None, r, doctor, "doctor")
    assert error.value.status_code == 403 and r.status == "active"


def test_a_second_doctor_cannot_change_or_remove_another_doctors_reading(audit_calls):
    r = row(by="doctor", added_by_id=9)
    other = SimpleNamespace(id=10)
    with pytest.raises(HTTPException) as error:
        body_record.update(None, r, other, "doctor", BodyMeasurementUpdate(weight=60))
    assert error.value.status_code == 403 and "Add a new reading" in error.value.detail and r.weight_kg == 70.0
    with pytest.raises(HTTPException) as error:
        body_record.remove(None, r, other, "doctor")
    assert error.value.status_code == 403 and r.status == "active" and audit_calls == []


def test_a_doctor_changes_and_removes_a_doctors_reading(audit_calls):
    r = row(by="doctor")
    doctor = SimpleNamespace(id=9)
    body_record.update(None, r, doctor, "doctor", BodyMeasurementUpdate(height_cm=171))
    assert r.height_cm == 171.0
    body_record.remove(None, r, doctor, "doctor")
    assert r.status == "removed"
    assert [c[0] for c in audit_calls] == ["body_measurement.update", "body_measurement.remove"]


def test_a_change_is_validated_like_a_new_reading():
    r = row()
    for bad in (
        BodyMeasurementUpdate(weight=900),
        BodyMeasurementUpdate(height_cm=20),
        BodyMeasurementUpdate(weight=None, height_cm=None),  # nothing left
    ):
        with pytest.raises(HTTPException) as error:
            body_record.update(None, r, ME, "patient", bad)
        assert error.value.status_code == 422
    assert (r.weight_kg, r.height_cm) == (70.0, 170.0)


def test_null_clears_one_value_and_unsent_fields_stay():
    r = row()
    body_record.update(None, r, ME, "patient", BodyMeasurementUpdate(weight=None))
    assert r.weight_kg is None and r.height_cm == 170.0
    r2 = row()
    body_record.update(None, r2, ME, "patient", BodyMeasurementUpdate(measured_on=date(2026, 2, 2)))
    assert r2.weight_kg == 70.0 and r2.measured_on == date(2026, 2, 2)


def test_a_future_date_on_a_change_is_refused_by_the_model():
    with pytest.raises(ValueError):
        BodyMeasurementUpdate(measured_on=date.today() + timedelta(days=1))


def test_the_payload_models_agree_on_defaults():
    assert BodyMeasurementIn(weight=70).weight_unit == "kg" and BodyMeasurementIn(weight=70).measured_on is None
