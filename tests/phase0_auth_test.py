"""Acceptance tests: route authentication and ownership (Phase 0, extended in Phase 1).

Phase 1 moves routes from Next.js to FastAPI; their checks move with them and call
FastAPI through the same-origin /api/backend proxy, exactly as the frontend does.

Runs against a local Next.js dev server (default http://localhost:3000) and the
local development database. It creates temporary users whose email starts with
"phase0-test-" and deletes them, and only them, together with their related rows,
in a finally block.

Safety:
- Refuses to run unless every database URL in use points to localhost.
  Only the hostname is checked; no URL or secret is printed.
- Never calls external or paid services: no OCR images, no AI requests. Routes
  that would reach OCR.space / OpenAI / Groq are only exercised on paths that
  return before that work (401/403).

Usage (from the repo root, with `npm run dev` running):
    backend\\venv\\Scripts\\python.exe tests\\phase0_auth_test.py
Optional: PHASE0_BASE_URL=http://localhost:3001
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from database import DATABASE_URL  # noqa: E402  (backend/database.py; loads .env files first)
from auth import create_access_token  # noqa: E402  (backend/auth.py; reads JWT secret from env)

BASE_URL = os.environ.get("PHASE0_BASE_URL", "http://localhost:3000").rstrip("/")
TEST_PREFIX = "phase0-test-"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Every route patched in Phase 0, with its HTTP method.
# Next.js admin routes were all removed in Phase 1; admin endpoints are in FASTAPI_ADMIN_ROUTES.
ADMIN_ROUTES: list[tuple[str, str]] = []
DOCTOR_ROUTES = [
    ("GET", "/api/backend/doctor/overview"),
    ("POST", "/api/backend/doctor/access/unlock"),
    ("POST", "/api/backend/doctor/access/end"),
]
PATIENT_ROUTES = [
    ("POST", "/api/medical-records/upload"),
    ("POST", "/api/medical-records/scan"),
    ("POST", "/api/medical-records/delete"),
]
ANY_USER_ROUTES = [
    ("POST", "/api/summarize"),
    ("POST", "/api/ocr/extract"),
    ("POST", "/api/ai/analyze-report"),
]
# FastAPI endpoints (through the proxy) that replaced Next routes in Phase 1.
FASTAPI_PATIENT_ROUTES = [
    ("POST", "/api/backend/patient/vitals/basic"),
    ("POST", "/api/backend/patient/vitals"),
    ("GET", "/api/backend/patient/vitals/today"),
    ("GET", "/api/backend/patient/vitals/trends"),
    ("GET", "/api/backend/patient/vitals/latest"),
    ("GET", "/api/backend/patient/medications"),
    ("POST", "/api/backend/patient/medications"),
    ("POST", "/api/backend/patient/medicine-reminders"),
    ("GET", "/api/backend/patient/medicine-reminders/today"),
    ("PATCH", "/api/backend/patient/medicine-reminders/1/mark-taken"),
    ("PATCH", "/api/backend/patient/medicine-reminders/1/skip"),
    ("POST", "/api/backend/appointments"),
    ("POST", "/api/backend/payments"),
    ("GET", "/api/backend/patient/overview"),
    ("POST", "/api/backend/patient/dashboard-otp"),
    ("POST", "/api/backend/emergency/requests"),
]
# FastAPI endpoints restricted to admins.
FASTAPI_ADMIN_ROUTES = [
    ("PUT", "/api/backend/payments/1"),
    ("GET", "/api/backend/api/admin/dashboard-stats"),
    ("GET", "/api/backend/api/admin/users"),
    ("GET", "/api/backend/api/admin/doctors/pending"),
    ("PATCH", "/api/backend/api/admin/doctors/1/approve"),
    ("PATCH", "/api/backend/api/admin/doctors/1/reject"),
    ("GET", "/api/backend/api/admin/recent-activity"),
]
# FastAPI endpoints open to any signed-in role.
FASTAPI_ANY_USER_ROUTES = [
    ("GET", "/api/backend/reminders"),
    ("POST", "/api/backend/reminders"),
    ("GET", "/api/backend/appointments"),
    ("PUT", "/api/backend/appointments/1"),
    ("GET", "/api/backend/payments"),
]
ALL_ROUTES = (ADMIN_ROUTES + DOCTOR_ROUTES + PATIENT_ROUTES + ANY_USER_ROUTES
              + FASTAPI_PATIENT_ROUTES + FASTAPI_ANY_USER_ROUTES + FASTAPI_ADMIN_ROUTES)

# Tables holding rows that belong to a user, children before parents.
# (table, column) pairs; only rows whose column is a phase0-test- user id are deleted.
USER_OWNED_ROWS = [
    ("medical_ai_analyses", "user_id"),
    ("notifications", "user_id"),
    ("notification_tokens", "user_id"),
    ("payments", "user_id"),
    ("appointments", "user_id"),
    ("appointments", "doctor_id"),
    ("emergency_bookings", "user_id"),
    ("emergency_bookings", "doctor_id"),
    ("patient_dashboard_access", "patient_id"),
    ("patient_dashboard_access", "doctor_id"),
    ("patient_dashboard_otps", "patient_id"),
    ("dashboard_otp_attempts", "actor_id"),
    ("reminder_logs", "patient_id"),
    ("medicine_reminders", "patient_id"),
    ("reminders", "user_id"),
    ("vitals", "user_id"),
    ("patient_vitals", "patient_id"),
    ("medications", "user_id"),
    ("medical_documents", "user_id"),
    ("patient_reports", "patient_id"),
    ("medicine_history", "patient_id"),
    ("health_tips", "patient_id"),
    ("health_risk_predictions", "patient_id"),
    ("doctor_summaries", "patient_id"),
    ("patient_profiles", "user_id"),
    ("doctor_profiles", "user_id"),
]


# --------------------------------------------------------------------------- safety

def assert_local_databases() -> None:
    """Abort unless every database URL the app uses points to localhost."""
    candidates = {"backend DATABASE_URL in use": DATABASE_URL}
    for env_file in (ROOT / ".env.local", ROOT / ".env", ROOT / "backend" / ".env"):
        if not env_file.exists():
            continue
        values = dotenv_values(env_file)
        for key in ("DATABASE_URL", "FASTAPI_DATABASE_URL"):
            if values.get(key):
                candidates[f"{env_file.relative_to(ROOT)} {key}"] = values[key]

    for label, url in candidates.items():
        host = make_url(url.strip().strip('"').strip("'")).host
        if host not in LOCAL_HOSTS:
            sys.exit(f"ABORT: {label} does not point to localhost. Refusing to create test users.")
    print(f"Database guard: {len(candidates)} URL(s) checked, all point to localhost.")


# --------------------------------------------------------------------------- results

results: list[tuple[bool, str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    results.append((condition, name, detail))
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not condition else ""))
    return condition


# --------------------------------------------------------------------------- db helpers

engine = create_engine(DATABASE_URL)
run_id = secrets.token_hex(4)


def create_user(label: str, role: str, *, active: bool = True, doctor_status: str = "approved") -> int:
    """Create a test user plus the profile row signup would create for that role."""
    with engine.begin() as conn:
        user_id = conn.execute(
            text(
                """
                insert into users (full_name, email, hashed_password, role, phone,
                                   is_active, is_email_verified, is_identity_verified)
                values (:name, :email, :pw, :role, '', :active, true, true)
                returning id
                """
            ),
            {
                "name": f"{TEST_PREFIX}{label}",
                "email": f"{TEST_PREFIX}{label}-{run_id}@example.test",
                # Not a usable bcrypt hash: these accounts cannot log in with a password.
                "pw": f"{TEST_PREFIX}no-login-{secrets.token_hex(8)}",
                "role": role,
                "active": active,
            },
        ).scalar_one()
        if role == "PATIENT":
            conn.execute(
                text(
                    """
                    insert into patient_profiles (user_id, cnic, date_of_birth, gender, verification_status)
                    values (:uid, '00000-0000000-0', '1990-01-01', 'unspecified', 'verified')
                    """
                ),
                {"uid": user_id},
            )
        elif role == "DOCTOR":
            conn.execute(
                text(
                    """
                    insert into doctor_profiles (user_id, pmdc_number, specialization, hospital_name, verification_status)
                    values (:uid, :pmdc, 'General Physician', 'phase0-test hospital', :status)
                    """
                ),
                {"uid": user_id, "pmdc": f"{TEST_PREFIX}{label}-{run_id}", "status": doctor_status},
            )
        return user_id


def create_record(user_id: int, title: str) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                insert into medical_documents (user_id, title, category, file_name, file_url, file_type,
                                               extracted_entities, detected_keywords, structured_sections,
                                               scan_status)
                values (:uid, :title, 'general-medicine', 'phase0-test.txt', '', 'unknown',
                        '[]', '[]', '{}', 'UPLOADED')
                returning id
                """
            ),
            {"uid": user_id, "title": title},
        ).scalar_one()


def create_grant(doctor_id: int, patient_id: int, *, expires_in: timedelta) -> None:
    # Update-then-insert: the live table may lack the (doctor_id, patient_id) unique
    # constraint that the Prisma schema declares, so ON CONFLICT is not usable.
    params = {"d": doctor_id, "p": patient_id, "exp": datetime.now(timezone.utc) + expires_in}
    with engine.begin() as conn:
        updated = conn.execute(
            text(
                """
                update patient_dashboard_access
                set status = 'ACTIVE', expires_at = :exp, ended_at = null, updated_at = now()
                where doctor_id = :d and patient_id = :p
                """
            ),
            params,
        ).rowcount
        if not updated:
            conn.execute(
                text(
                    """
                    insert into patient_dashboard_access (doctor_id, patient_id, status, expires_at)
                    values (:d, :p, 'ACTIVE', :exp)
                    """
                ),
                params,
            )


def scalar(sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def cleanup_test_users() -> None:
    """Delete phase0-test- users and rows tied to them. Nothing else is touched."""
    with engine.begin() as conn:
        ids = list(
            conn.execute(
                text("select id from users where email like :p and full_name like :p"),
                {"p": f"{TEST_PREFIX}%"},
            ).scalars()
        )
        if not ids:
            return
        existing = set(
            conn.execute(text("select table_name from information_schema.tables where table_schema = 'public'")).scalars()
        )
        deleted = 0
        for table, column in USER_OWNED_ROWS:
            if table in existing:
                deleted += conn.execute(text(f"delete from {table} where {column} = any(:ids)"), {"ids": ids}).rowcount
        users = conn.execute(text("delete from users where id = any(:ids)"), {"ids": ids}).rowcount
    print(f"Cleanup: removed {users} phase0-test- user(s) and {deleted} related row(s).")


# --------------------------------------------------------------------------- tokens / http

def token_for(user_id: int, **extra) -> str:
    return create_access_token(str(user_id), extra or None)


def tampered_token(valid_token: str, new_sub: int) -> str:
    """Swap the payload's subject but keep the original signature."""
    header, payload, signature = valid_token.split(".")
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    data["sub"] = str(new_sub)
    forged = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    return f"{header}.{forged}.{signature}"


client = httpx.Client(base_url=BASE_URL, timeout=180)


def call(method: str, path: str, token: str | None = None, body: dict | None = None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if method == "GET":
        return client.get(path, headers=headers)
    return client.request(method, path, headers=headers, json=body if body is not None else {})


def overview_patient_ids(doctor_token: str) -> list[int]:
    response = call("GET", "/api/backend/doctor/overview", doctor_token)
    if response.status_code != 200:
        raise AssertionError(f"doctor/overview returned {response.status_code}")
    return [patient["id"] for patient in response.json().get("patients", [])]


# --------------------------------------------------------------------------- tests

def run_tests() -> None:
    patient_a = create_user("patient-a", "PATIENT")
    patient_b = create_user("patient-b", "PATIENT")
    inactive = create_user("patient-inactive", "PATIENT", active=False)
    doctor = create_user("doctor", "DOCTOR")
    doctor_2 = create_user("doctor-2", "DOCTOR")
    admin = create_user("admin", "ADMIN")
    doctor_pending = create_user("doctor-pending", "DOCTOR", doctor_status="pending")
    doctor_inactive = create_user("doctor-inactive", "DOCTOR", active=False)
    doctor_bf = create_user("doctor-bruteforce", "DOCTOR")

    tok_a, tok_b = token_for(patient_a), token_for(patient_b)
    tok_doctor, tok_doctor_2, tok_admin = token_for(doctor), token_for(doctor_2), token_for(admin)

    # Legacy identity fields that must now be ignored.
    spoof_body = {"userId": admin, "adminId": admin, "doctorId": doctor, "patientId": patient_a}

    print("\n[0] /api/backend proxy only reaches the configured FastAPI server")
    check("proxy forwards to FastAPI", call("GET", "/api/backend/health").status_code == 200)
    response = call("GET", "/api/backend/health%00")
    check("control character in path -> 400", response.status_code == 400, f"got {response.status_code}")
    for path in ("/api/backend/http:%2F%2Fexample.com/x", "/api/backend/%2F%2Fexample.com/x", "/api/backend/@example.com/x"):
        response = call("GET", path)
        detail = response.json().get("detail") if "json" in response.headers.get("content-type", "") else None
        check(f"{path} stays on FastAPI (its own 404)", response.status_code == 404 and detail == "Not Found",
              f"got {response.status_code} {detail!r}")

    print("\n[1] No token -> 401 on every patched route (legacy userId params ignored)")
    for method, path in ALL_ROUTES:
        target = f"{path}?userId={admin}" if method == "GET" else path
        response = call(method, target, None, spoof_body)
        check(f"{method} {path} without token -> 401", response.status_code == 401, f"got {response.status_code}")

    print("\n[2] Invalid tokens -> 401")
    response = call("GET", "/api/backend/patient/overview", token_for(patient_a, exp=int(time.time()) - 60))
    check("expired token -> 401", response.status_code == 401, f"got {response.status_code}")
    response = call("GET", "/api/backend/api/admin/dashboard-stats", tampered_token(tok_a, admin))
    check("token with tampered subject -> 401", response.status_code == 401, f"got {response.status_code}")
    response = call("GET", "/api/backend/patient/overview", "not-a-jwt")
    check("malformed token -> 401", response.status_code == 401, f"got {response.status_code}")

    print("\n[3] Wrong role -> 403")
    for method, path in ADMIN_ROUTES + FASTAPI_ADMIN_ROUTES:
        response = call(method, path, tok_a)
        check(f"patient on {path} -> 403", response.status_code == 403, f"got {response.status_code}")
        response = call(method, path, tok_doctor)
        check(f"doctor on {path} -> 403", response.status_code == 403, f"got {response.status_code}")
    for method, path in DOCTOR_ROUTES:
        response = call(method, path, tok_a)
        check(f"patient on {path} -> 403", response.status_code == 403, f"got {response.status_code}")
    for method, path in PATIENT_ROUTES + FASTAPI_PATIENT_ROUTES:
        response = call(method, path, tok_doctor)
        check(f"doctor on {path} -> 403", response.status_code == 403, f"got {response.status_code}")
    response = call("POST", "/api/summarize", tok_doctor, {})
    check("doctor on summarize saved-report mode -> 403", response.status_code == 403, f"got {response.status_code}")
    response = call("GET", "/api/backend/patient/overview", token_for(inactive))
    check("inactive patient account -> 403", response.status_code == 403, f"got {response.status_code}")
    response = call("GET", "/api/backend/patient/vitals/today", token_for(inactive))
    check("inactive patient account on vitals -> 403", response.status_code == 403, f"got {response.status_code}")

    print("\n[4] Correct role -> allowed (positive controls)")
    check("admin on admin dashboard-stats -> 200", call("GET", "/api/backend/api/admin/dashboard-stats", tok_admin).status_code == 200)
    check("doctor on doctor/overview -> 200", call("GET", "/api/backend/doctor/overview", tok_doctor).status_code == 200)
    check("patient on overview -> 200", call("GET", "/api/backend/patient/overview", tok_a).status_code == 200)

    print("\n[5] Ownership: Patient A cannot read or delete Patient B's records")
    record_a = create_record(patient_a, f"{TEST_PREFIX}record A")
    record_b = create_record(patient_b, f"{TEST_PREFIX}record B")

    response = call("GET", f"/api/backend/patient/overview?user_id={patient_b}&userId={patient_b}", tok_a)
    record_ids = [record["id"] for record in response.json().get("medicalRecords", [])]
    check("A's dashboard lists A's record", record_a in record_ids, f"ids={record_ids}")
    check("A's dashboard (with ?userId=B) does not list B's record", record_b not in record_ids, f"ids={record_ids}")

    response = call("POST", "/api/medical-records/delete", tok_a, {"recordId": record_b, "userId": patient_b})
    check("A deleting B's record -> 404", response.status_code == 404, f"got {response.status_code}")
    check(
        "B's record still exists after A's attempt",
        scalar("select count(*) from medical_documents where id = :id", id=record_b) == 1,
    )
    response = call("POST", "/api/medical-records/delete", tok_b, {"recordId": record_b})
    check("B deleting own record -> 200", response.status_code == 200, f"got {response.status_code}")
    check("B's record is gone", scalar("select count(*) from medical_documents where id = :id", id=record_b) == 0)

    response = call("POST", "/api/backend/patient/vitals/basic", tok_a,
                    {"user_id": patient_b, "userId": patient_b, "blood_pressure": "120/80", "sugar_level": "95"})
    check("A adds vitals (body user id=B ignored) -> 201", response.status_code == 201, f"got {response.status_code}")
    check("vitals stored under A", scalar("select count(*) from vitals where user_id = :id", id=patient_a) == 1)
    check("no vitals stored under B", scalar("select count(*) from vitals where user_id = :id", id=patient_b) == 0)
    response = call("GET", f"/api/backend/patient/vitals/latest?user_id={patient_b}&userId={patient_b}", tok_a)
    vitals = response.json() or {}
    check("vitals/latest (with ?user_id=B) returns A's vitals", vitals.get("user_id") == patient_a, f"got {vitals.get('user_id')}")
    response = call("GET", "/api/backend/patient/vitals/today", tok_b)
    check("B's vitals/today is empty", response.status_code == 200 and response.json() is None)

    print("\n[5b] Vitals: nothing is estimated or invented")
    today = call("GET", "/api/backend/patient/vitals/today", tok_a).json() or {}
    check("simple log only -> BP parsed from it", (today.get("blood_pressure_systolic"), today.get("blood_pressure_diastolic")) == (120, 80), f"got {today}")
    check("simple log only -> heart rate, SpO2, temperature are null (not 72/98/98.4)",
          today.get("heart_rate") is None and today.get("spo2") is None and today.get("temperature") is None, f"got {today}")
    reading = {"bloodPressureSystolic": 130, "bloodPressureDiastolic": 85, "heartRate": 77, "spo2": 97, "temperature": 98.9}
    response = call("POST", "/api/backend/patient/vitals", tok_a, reading)
    check("A adds a detailed reading -> 201", response.status_code == 201, f"got {response.status_code}")
    today = call("GET", "/api/backend/patient/vitals/today", tok_a).json() or {}
    check("today returns the detailed reading", (today.get("heart_rate"), today.get("spo2")) == (77, 97), f"got {today}")
    trends = call("GET", "/api/backend/patient/vitals/trends", tok_a).json()
    check("trends has A's reading", len(trends) == 1 and trends[0]["heart_rate"] == 77, f"got {trends}")
    check("B has no trends", call("GET", "/api/backend/patient/vitals/trends", tok_b).json() == [])
    check("detailed reading mirrored into the simple log",
          scalar("select count(*) from vitals where user_id = :id and blood_pressure = '130/85'", id=patient_a) == 1)

    print("\n[5c] Medication schedules are per patient")
    med = {"medicineName": "Phase0 Testamol", "dosage": "1 tablet", "startDate": "2026-01-01", "userId": patient_b}
    response = call("POST", "/api/backend/patient/medications", tok_a, med)
    created = response.json() if response.status_code == 201 else {}
    check("A creates a medication (body userId=B ignored) -> 201", response.status_code == 201, f"got {response.status_code}")
    check("medication stored under A", created.get("patient_id") == patient_a
          and scalar("select user_id from medications where id = :id", id=created.get("id", 0)) == patient_a)
    check("A's list has it", [m["id"] for m in call("GET", "/api/backend/patient/medications", tok_a).json()] == [created.get("id")])
    check("B's list is empty", call("GET", "/api/backend/patient/medications", tok_b).json() == [])
    response = call("POST", "/api/backend/patient/medications", tok_a, {**med, "endDate": "2025-01-01"})
    check("end date before start date -> 400", response.status_code == 400, f"got {response.status_code}")

    print("\n[5d] Reminders are per patient")
    due = datetime.now(timezone.utc).isoformat()
    response = call("POST", "/api/backend/reminders", tok_a, {"title": "Take Phase0 Testamol", "due_at": due, "user_id": patient_b})
    check("A adds a free-text reminder (body user_id=B ignored) -> 201", response.status_code == 201, f"got {response.status_code}")
    check("free-text reminder stored under A", scalar("select count(*) from reminders where user_id = :id", id=patient_a) == 1)
    check("B's reminder list is empty", call("GET", "/api/backend/reminders", tok_b).json() == [])

    med_id = created.get("id")
    schedule = {"medicationId": med_id, "reminderTime": due, "frequency": "Once daily"}
    response = call("POST", "/api/backend/patient/medicine-reminders", tok_b, schedule)
    check("B scheduling a dose of A's medication -> 404", response.status_code == 404, f"got {response.status_code}")
    response = call("POST", "/api/backend/patient/medicine-reminders", tok_a, schedule)
    dose = response.json() if response.status_code == 201 else {}
    check("A schedules a dose -> 201, due now", response.status_code == 201 and dose.get("status") == "DUE_NOW",
          f"got {response.status_code} {dose.get('status')}")
    check("dose includes its medication", (dose.get("medication") or {}).get("medicine_name") == "Phase0 Testamol")
    check("scheduling notification has no reminder_id (it belongs to the other reminders table)",
          scalar("select count(*) from notifications where user_id = :id and title = 'Medicine reminder scheduled' "
                 "and reminder_id is null", id=patient_a) == 1)
    check("A's today list has the dose", [r["id"] for r in call("GET", "/api/backend/patient/medicine-reminders/today", tok_a).json()] == [dose.get("id")])
    check("B's today list is empty", call("GET", "/api/backend/patient/medicine-reminders/today", tok_b).json() == [])
    response = call("PATCH", f"/api/backend/patient/medicine-reminders/{dose.get('id')}/mark-taken", tok_b)
    check("B marking A's dose taken -> 404", response.status_code == 404, f"got {response.status_code}")
    response = call("PATCH", f"/api/backend/patient/medicine-reminders/{dose.get('id')}/mark-taken", tok_a)
    taken = response.json() if response.status_code == 200 else {}
    check("A marks the dose taken -> TAKEN with a time", taken.get("status") == "TAKEN" and bool(taken.get("taken_at")), f"got {taken}")
    check("reminder log has the scheduled and taken entries",
          scalar("select count(*) from reminder_logs where reminder_id = :id", id=dose.get("id", 0)) == 2)
    response = call("PATCH", f"/api/backend/patient/medicine-reminders/{dose.get('id')}/skip", tok_a)
    skipped = response.json() if response.status_code == 200 else {}
    check("A skips it -> SKIPPED with a time", skipped.get("status") == "SKIPPED" and bool(skipped.get("skipped_at")),
          f"got {response.status_code} {skipped.get('status')}")

    print("\n[5e] Doctor search and booking: verified doctors only, nothing invented")
    listed = call("GET", "/api/backend/appointments/doctors").json()
    listed_ids = {d["doctor_id"] for d in listed}
    check("approved doctor is listed", doctor in listed_ids)
    check("pending (unverified) doctor is not listed", doctor_pending not in listed_ids)
    check("inactive doctor is not listed", doctor_inactive not in listed_ids)
    check("no demo doctors (every entry is a registered doctor)", all(d["source"] == "registered" and d["doctor_id"] for d in listed))
    check("no invented ratings or availability", all(d["rating"] is None and d["available_today"] is None for d in listed))

    future = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat()
    booking = {"doctor_id": doctor, "doctor_name": "Someone Else", "specialty": "Cardiology", "date": future,
               "reason": "Follow-up", "user_id": patient_b}
    response = call("POST", "/api/backend/appointments", tok_a, booking)
    booked = (response.json() or {}).get("appointment", {}) if response.status_code == 201 else {}
    check("A books the approved doctor -> 201", response.status_code == 201, f"got {response.status_code}")
    check("booking stored under A with the doctor's real name and specialty (request values ignored)",
          booked.get("user_id") == patient_a and booked.get("doctor_name") == f"{TEST_PREFIX}doctor"
          and booked.get("specialty") == "General Physician" and booked.get("reason") == "Follow-up", f"got {booked}")
    response = call("POST", "/api/backend/appointments", tok_a, {**booking, "doctor_id": doctor_pending})
    check("booking an unverified doctor -> 404", response.status_code == 404, f"got {response.status_code}")
    response = call("POST", "/api/backend/appointments", tok_a, {"doctor_name": f"{TEST_PREFIX}doctor", "date": future})
    check("booking by name only (no doctor_id) -> 400", response.status_code == 400, f"got {response.status_code}")

    check("A sees the appointment", [a["id"] for a in call("GET", "/api/backend/appointments", tok_a).json()] == [booked.get("id")])
    check("B sees no appointments", call("GET", "/api/backend/appointments", tok_b).json() == [])
    check("the booked doctor sees it", booked.get("id") in [a["id"] for a in call("GET", "/api/backend/appointments", tok_doctor).json()])
    check("another doctor does not", call("GET", "/api/backend/appointments", tok_doctor_2).json() == [])

    appt = f"/api/backend/appointments/{booked.get('id')}"
    response = call("PUT", appt, tok_a, {"payment_status": "SUCCESS"})
    check("patient marking own appointment paid -> 403", response.status_code == 403, f"got {response.status_code}")
    response = call("PUT", appt, tok_a, {"status": "COMPLETED"})
    check("patient setting status COMPLETED -> 403", response.status_code == 403, f"got {response.status_code}")
    response = call("PUT", appt, tok_b, {"status": "CANCELLED"})
    check("B changing A's appointment -> 403", response.status_code == 403, f"got {response.status_code}")
    response = call("PUT", appt, tok_admin, {"payment_status": "SUCCESS"})
    check("admin can change payment status -> 200", response.status_code == 200 and response.json().get("payment_status") == "SUCCESS",
          f"got {response.status_code}")
    response = call("PUT", appt, tok_a, {"status": "CANCELLED"})
    check("patient can cancel own appointment -> 200", response.status_code == 200 and response.json().get("status") == "CANCELLED",
          f"got {response.status_code}")

    print("\n[5f] Payments: payers cannot mark payments paid")
    pay = {"amount": 1500, "method": "CASH", "purpose": "Consultation", "appointment_id": booked.get("id"), "user_id": patient_b}
    response = call("POST", "/api/backend/payments", tok_a, pay)
    payment = response.json() if response.status_code == 201 else {}
    check("A records a cash payment for own appointment -> 201 PAY_ON_VISIT",
          response.status_code == 201 and payment.get("status") == "PAY_ON_VISIT" and payment.get("user_id") == patient_a,
          f"got {response.status_code} {payment.get('status')}")
    response = call("POST", "/api/backend/payments", tok_b, pay)
    check("B paying against A's appointment -> 404", response.status_code == 404, f"got {response.status_code}")
    for wallet in ("EASYPAISA", "JAZZCASH", "NAYAPAY"):
        response = call("POST", "/api/backend/payments", tok_a,
                        {"amount": 500, "method": wallet, "purpose": "Consultation", "phone": "03000000000"})
        check(f"{wallet} payment is recorded as PENDING, not SUCCESS (no gateway)",
              response.status_code == 201 and response.json().get("status") == "PENDING",
              f"got {response.status_code} {response.json().get('status') if response.status_code == 201 else ''}")
    response = call("PUT", f"/api/backend/payments/{payment.get('id')}", tok_a, {"status": "SUCCESS"})
    check("A marking own payment SUCCESS -> 403", response.status_code == 403, f"got {response.status_code}")
    response = call("PUT", f"/api/backend/payments/{payment.get('id')}", tok_doctor, {"status": "SUCCESS"})
    check("doctor marking a payment SUCCESS -> 403", response.status_code == 403, f"got {response.status_code}")
    response = call("PUT", f"/api/backend/payments/{payment.get('id')}", tok_admin, {"status": "SUCCESS"})
    check("admin marks it SUCCESS -> 200", response.status_code == 200 and response.json().get("status") == "SUCCESS",
          f"got {response.status_code}")
    check("linked appointment payment status follows",
          scalar("select payment_status from appointments where id = :id", id=booked.get("id", 0)) == "SUCCESS")
    check("B sees no payments", call("GET", "/api/backend/payments", tok_b).json() == [])

    print("\n[5g] Home-visit requests: no invented dispatch")
    request = {"patientName": "Phase0 A", "phone": "03000000000", "address": "Test street", "symptoms": "fever",
               "userId": patient_b, "user_id": patient_b}
    response = call("POST", "/api/backend/emergency/requests", tok_a, request)
    body = response.json() if response.status_code == 201 else {}
    booking_out = body.get("booking") or {}
    check("A sends a request -> 201 REQUESTED", response.status_code == 201 and booking_out.get("status") == "REQUESTED",
          f"got {response.status_code} {booking_out.get('status')}")
    check("no doctor and no ETA are claimed", booking_out.get("doctorName") is None and booking_out.get("estimatedMinutes") is None,
          f"got {booking_out}")
    check("response directs emergencies to 1122", "1122" in body.get("message", "") and "1122" in body.get("emergencyNotice", ""))
    check("request stored under A (body user id ignored), no doctor",
          scalar("select count(*) from emergency_bookings where user_id = :a and doctor_id is null and status = 'REQUESTED'",
                 a=patient_a) == 1
          and scalar("select count(*) from emergency_bookings where user_id = :b", b=patient_b) == 0)

    print("\n[6] Doctor grant lifecycle on doctor/overview")
    check("no grant -> patient A not listed", patient_a not in overview_patient_ids(tok_doctor))

    create_grant(doctor, patient_a, expires_in=timedelta(minutes=-5))
    check("expired grant -> patient A not listed", patient_a not in overview_patient_ids(tok_doctor))

    overview = call("GET", "/api/backend/doctor/overview", tok_doctor).json()
    check("no grant -> none of A's medical records or medications visible",
          all(r["userId"] != patient_a for r in overview["medicalRecords"] + overview["medications"]))
    create_grant(doctor, patient_a, expires_in=timedelta(hours=1))
    check("active grant -> patient A listed", patient_a in overview_patient_ids(tok_doctor))
    overview = call("GET", "/api/backend/doctor/overview", tok_doctor).json()
    check("active grant -> A's record and latest vitals visible",
          record_a in [r["id"] for r in overview["medicalRecords"]]
          and next(p for p in overview["patients"] if p["id"] == patient_a)["latestVitals"] is not None)
    check("grant is per doctor -> doctor 2 does not see A", patient_a not in overview_patient_ids(tok_doctor_2))

    response = call("POST", "/api/backend/doctor/access/end", tok_doctor_2, {"patientId": patient_a, "doctorId": doctor})
    check("doctor 2 calling access/end (doctorId spoofed) -> 200", response.status_code == 200, f"got {response.status_code}")
    check("doctor 2 cannot end doctor 1's grant -> A still listed", patient_a in overview_patient_ids(tok_doctor))

    response = call("POST", "/api/backend/doctor/access/end", tok_doctor, {"patientId": patient_a})
    check("doctor ends access -> 200", response.status_code == 200, f"got {response.status_code}")
    check("after access/end -> patient A not listed", patient_a not in overview_patient_ids(tok_doctor))

    print("\n[7] OTP unlock flow (patient-issued OTP -> doctor unlock -> end)")
    response = call("POST", "/api/backend/patient/dashboard-otp", tok_a, {"userId": patient_b, "user_id": patient_b})
    otp = (response.json().get("otp") or {}).get("code")
    check("A generates dashboard OTP -> 200", response.status_code == 200 and bool(otp), f"got {response.status_code}")
    check(
        "OTP belongs to A (body userId=B ignored)",
        scalar("select patient_id from patient_dashboard_otps where code = :c", c=otp) == patient_a,
    )
    response = call("POST", "/api/backend/doctor/access/unlock", tok_doctor, {"patientAccessOtp": otp, "doctorId": doctor_2})
    check("doctor unlocks with OTP -> 200", response.status_code == 200, f"got {response.status_code}")
    check("after unlock -> A listed for doctor", patient_a in overview_patient_ids(tok_doctor))
    check("after unlock -> A not listed for doctor 2 (doctorId spoof ignored)", patient_a not in overview_patient_ids(tok_doctor_2))
    response = call("POST", "/api/backend/doctor/access/unlock", tok_doctor, {"patientAccessOtp": otp})
    check("OTP is single-use -> second unlock 404", response.status_code == 404, f"got {response.status_code}")
    call("POST", "/api/backend/doctor/access/end", tok_doctor, {"patientId": patient_a})
    check("after end -> A not listed", patient_a not in overview_patient_ids(tok_doctor))

    otp = call("POST", "/api/backend/patient/dashboard-otp", tok_a).json()["otp"]["code"]
    response = call("POST", "/api/backend/appointments", tok_a,
                    {"doctor_id": doctor_2, "date": future, "reason": "Second opinion", "patient_access_otp": otp})
    check("booking with an OTP -> access granted", response.status_code == 201 and response.json().get("dashboard_access_granted") is True,
          f"got {response.status_code}")
    check("booked doctor (2) now sees A", patient_a in overview_patient_ids(tok_doctor_2))
    check("other doctor still does not", patient_a not in overview_patient_ids(tok_doctor))
    call("POST", "/api/backend/doctor/access/end", tok_doctor_2, {"patientId": patient_a})

    print("\n[8] OTP brute-force limit: 5 failures per 15 minutes")
    tok_bf = token_for(doctor_bf)
    for attempt in range(1, 6):
        response = call("POST", "/api/backend/doctor/access/unlock", tok_bf, {"patientAccessOtp": f"wrong-{attempt}"})
        check(f"wrong unlock attempt {attempt} -> 404", response.status_code == 404, f"got {response.status_code}")
    response = call("POST", "/api/backend/doctor/access/unlock", tok_bf, {"patientAccessOtp": "wrong-6"})
    check("6th attempt -> 429 with Retry-After and a clear message",
          response.status_code == 429 and int(response.headers.get("retry-after", "0")) > 0
          and "Too many incorrect OTP attempts" in response.json().get("detail", ""),
          f"got {response.status_code} {response.headers.get('retry-after')}")
    good_otp = call("POST", "/api/backend/patient/dashboard-otp", tok_a).json()["otp"]["code"]
    response = call("POST", "/api/backend/doctor/access/unlock", tok_bf, {"patientAccessOtp": good_otp})
    check("while blocked, even a correct OTP -> 429 (and the OTP stays unused)", response.status_code == 429,
          f"got {response.status_code}")
    check("blocked doctor does not see A", patient_a not in overview_patient_ids(tok_bf))
    check("5 failed unlock attempts logged for that doctor (code not stored)",
          scalar("select count(*) from dashboard_otp_attempts where actor_id = :id and context = 'unlock' "
                 "and succeeded = false", id=doctor_bf) == 5)
    response = call("POST", "/api/backend/doctor/access/unlock", tok_doctor_2, {"patientAccessOtp": good_otp})
    check("another doctor is not affected -> unlock 200", response.status_code == 200, f"got {response.status_code}")
    call("POST", "/api/backend/doctor/access/end", tok_doctor_2, {"patientId": patient_a})

    appointments_before = scalar("select count(*) from appointments where user_id = :id", id=patient_b)
    for attempt in range(1, 6):
        response = call("POST", "/api/backend/appointments", tok_b,
                        {"doctor_id": doctor, "date": future, "patient_access_otp": f"wrong-{attempt}"})
        check(f"booking with wrong OTP {attempt} -> 201, no access shared",
              response.status_code == 201 and response.json().get("dashboard_access_granted") is False,
              f"got {response.status_code}")
    response = call("POST", "/api/backend/appointments", tok_b, {"doctor_id": doctor, "date": future, "patient_access_otp": "wrong-6"})
    check("6th booking with an OTP -> 429", response.status_code == 429, f"got {response.status_code}")
    check("the blocked booking created no appointment",
          scalar("select count(*) from appointments where user_id = :id", id=patient_b) == appointments_before + 5)
    response = call("POST", "/api/backend/appointments", tok_b, {"doctor_id": doctor, "date": future})
    check("booking without an OTP still works while blocked -> 201", response.status_code == 201, f"got {response.status_code}")


def main() -> int:
    assert_local_databases()
    try:
        client.get("/", timeout=180)
    except httpx.HTTPError as error:
        sys.exit(f"ABORT: Next.js server not reachable at {BASE_URL} ({type(error).__name__}). Start it with `npm run dev`.")

    cleanup_test_users()  # leftovers from an interrupted earlier run
    try:
        run_tests()
    except Exception as error:  # report, then still clean up
        check("test run completed without errors", False, f"{type(error).__name__}: {error}")
    finally:
        cleanup_test_users()
        client.close()

    failed = [name for ok, name, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
