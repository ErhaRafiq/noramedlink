"""Patient vitals: the simple BP/sugar log (vitals) and detailed readings (patient_vitals).

Ported from the Next.js routes vitals/add, patient/vitals, patient/vitals/today and
patient/vitals/trends. Identity always comes from the verified token.
"""

import re

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_patient
from models import PatientVital, User, Vitals
from schemas import BasicVitalsCreate, DailyVitalOut, PatientVitalCreate, VitalsOut, VitalTrendOut

router = APIRouter(prefix="/patient/vitals", tags=["vitals"])

TREND_POINTS = 14


def _parse_blood_pressure(value: str) -> tuple[int, int] | None:
    match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", value)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _vitals_out(vital: Vitals) -> VitalsOut:
    return VitalsOut(
        id=vital.id,
        user_id=vital.user_id,
        blood_pressure=vital.blood_pressure,
        sugar_level=vital.sugar_level,
        created_at=vital.created_at,
    )


def _daily_out(vital: PatientVital) -> DailyVitalOut:
    return DailyVitalOut(
        id=vital.id,
        patient_id=vital.patient_id,
        blood_pressure_systolic=vital.blood_pressure_systolic,
        blood_pressure_diastolic=vital.blood_pressure_diastolic,
        heart_rate=vital.heart_rate,
        spo2=vital.spo2,
        temperature=vital.temperature,
        sugar_level=vital.sugar_level,
        weight=vital.weight,
        recorded_at=vital.recorded_at,
        created_at=vital.created_at,
    )


@router.post("/basic", response_model=VitalsOut, status_code=status.HTTP_201_CREATED)
def add_basic_vitals(
    payload: BasicVitalsCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    vital = Vitals(
        user_id=current_user.id,
        blood_pressure=payload.blood_pressure.strip(),
        sugar_level=payload.sugar_level.strip(),
    )
    db.add(vital)
    db.commit()
    db.refresh(vital)
    return _vitals_out(vital)


@router.post("", response_model=DailyVitalOut, status_code=status.HTTP_201_CREATED)
def add_patient_vital(
    payload: PatientVitalCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    vital = PatientVital(
        patient_id=current_user.id,
        blood_pressure_systolic=payload.blood_pressure_systolic,
        blood_pressure_diastolic=payload.blood_pressure_diastolic,
        heart_rate=payload.heart_rate,
        spo2=payload.spo2,
        temperature=payload.temperature,
        sugar_level=payload.sugar_level,
        weight=payload.weight,
        **({"recorded_at": payload.recorded_at} if payload.recorded_at else {}),
    )
    db.add(vital)
    # Mirror into the simple log so the doctor view and /dashboard see the reading too.
    db.add(
        Vitals(
            user_id=current_user.id,
            blood_pressure=f"{payload.blood_pressure_systolic}/{payload.blood_pressure_diastolic}",
            sugar_level="Not recorded" if payload.sugar_level is None else str(payload.sugar_level),
        )
    )
    db.commit()
    db.refresh(vital)
    return _daily_out(vital)


@router.get("/today", response_model=DailyVitalOut | None)
def today_vitals(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    latest = (
        db.query(PatientVital)
        .filter(PatientVital.patient_id == current_user.id)
        .order_by(PatientVital.recorded_at.desc())
        .first()
    )
    if latest:
        return _daily_out(latest)

    # Fall back to the simple log. Only blood pressure and sugar are known there;
    # the other values stay null rather than being filled with typical numbers.
    legacy = (
        db.query(Vitals)
        .filter(Vitals.user_id == current_user.id)
        .order_by(Vitals.created_at.desc())
        .first()
    )
    if not legacy:
        return None
    pressure = _parse_blood_pressure(legacy.blood_pressure)
    if not pressure:
        return None
    return DailyVitalOut(
        id=legacy.id,
        patient_id=legacy.user_id,
        blood_pressure_systolic=pressure[0],
        blood_pressure_diastolic=pressure[1],
        heart_rate=None,
        spo2=None,
        temperature=None,
        sugar_level=_parse_float(legacy.sugar_level),
        weight=None,
        recorded_at=legacy.created_at,
        created_at=legacy.created_at,
    )


@router.get("/trends", response_model=list[VitalTrendOut])
def vitals_trends(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    records = (
        db.query(PatientVital)
        .filter(PatientVital.patient_id == current_user.id)
        .order_by(PatientVital.recorded_at.desc())
        .limit(TREND_POINTS)
        .all()
    )
    return [
        VitalTrendOut(
            recorded_at=r.recorded_at,
            blood_pressure_systolic=r.blood_pressure_systolic,
            blood_pressure_diastolic=r.blood_pressure_diastolic,
            heart_rate=r.heart_rate,
            spo2=r.spo2,
            temperature=r.temperature,
            sugar_level=r.sugar_level,
            weight=r.weight,
        )
        for r in reversed(records)
    ]
