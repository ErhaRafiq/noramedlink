"""Query-count regression test: no list endpoint may run more SQL as its data grows (no N+1).

Counts the SQL statements of each endpoint with 3 rows of data and again with 15, in this process (no servers needed,
only the local database). The count with 15 rows may be at most one more than with 3 (a lookup that is skipped when
there is nothing to look up). Uses phase0-test- users only and removes them. Run from the repo root:

    $env:DISABLE_PAID_SERVICES="1"; backend/venv/Scripts/python.exe tests/query_count_test.py
"""

import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["DISABLE_PAID_SERVICES"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

spec = importlib.util.spec_from_file_location("acc", ROOT / "tests" / "acceptance_test.py")
acc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acc)
acc.assert_local_databases()

from fastapi.testclient import TestClient
from sqlalchemy import event, text

from database import engine
from main import app
from services import notifications

counter = {"n": 0}


@event.listens_for(engine, "before_cursor_execute")
def _count(*args, **kwargs):
    counter["n"] += 1


client = TestClient(app)  # no lifespan: no migrations, no model loading


def seed(patient, doctor, count, tag):
    now = datetime.now(timezone.utc)
    for i in range(count):
        acc.create_record(patient, f"phase0-test-{tag}-{i}")
    with engine.begin() as conn:
        for i in range(count):
            conn.execute(
                text(
                    "insert into appointments (user_id, doctor_id, doctor_name, date, duration_minutes, mode, status, payment_status, created_at, updated_at) "
                    "values (:u, :d, 'Dr Test', :dt, 30, 'in_clinic', 'booked', 'pending', now(), now())"
                ),
                {"u": patient, "d": doctor, "dt": now + timedelta(days=30 + i, minutes=i * 40)},
            )
            conn.execute(
                text("insert into vitals (user_id, blood_pressure, sugar_level, created_at) values (:u, '120/80', '90', now())"),
                {"u": patient},
            )
    from database import SessionLocal

    db = SessionLocal()
    for i in range(count):
        notifications.add(db, patient, "appointment_booked", f"t{tag}{i}", "body")
        notifications.add(db, doctor, "appointment_booked", f"t{tag}{i}", "body")
    db.commit()
    db.close()


def measure(label, method, path, token, **kw):
    counter["n"] = 0
    response = getattr(client, method)(path, headers={"Authorization": f"Bearer {token}"}, **kw)
    return counter["n"], response.status_code


ENDPOINTS = [
    ("patient", "get", "/patient/reports"),
    ("patient", "get", "/appointments"),
    ("patient", "get", "/notifications"),
    ("patient", "get", "/payments"),
    ("patient", "get", "/patient/prescriptions"),
    ("patient", "get", "/patient/health-flags"),
    ("patient", "get", "/patient/vitals/basic"),
    ("patient", "get", "/patient/access-history"),
    ("patient", "get", "/patient/health-record"),
    ("doctor", "get", "/doctor/overview"),
    ("doctor", "get", "/appointments"),
    ("doctor", "get", "/notifications"),
    ("admin", "get", "/api/admin/users"),
    ("admin", "get", "/api/admin/dashboard-stats"),
    ("admin", "get", "/api/admin/audit-log"),
]
DIRECTORY = ("patient", "get", "/appointments/doctors")

try:
    patient = acc.create_user("np1-patient", "PATIENT")
    doctor = acc.create_user("np1-doctor", "DOCTOR")
    admin = acc.create_user("np1-admin", "ADMIN")
    acc.create_grant(doctor, patient, expires_in=timedelta(hours=2))
    tokens = {"patient": acc.token_for(patient), "doctor": acc.token_for(doctor), "admin": acc.token_for(admin)}
    results = {}
    for size, tag in ((3, "a"), (15, "b")):
        seed(patient, doctor, size if tag == "a" else size - 3, tag)
        for role, method, path in [*ENDPOINTS, DIRECTORY]:
            results.setdefault((role, path), []).append(measure(path, method, path, tokens[role]))
    print(f"{'endpoint':42} {'3 rows':>7} {'15 rows':>8}  status")
    failures = []
    for (role, path), ((n1, s1), (n2, s2)) in results.items():
        grows = n2 > n1 + 1
        print(f"{role + ' ' + path:42} {n1:>7} {n2:>8}  {s1}/{s2}{'  <-- GROWS' if grows else ''}")
        if grows or s1 != 200 or s2 != 200:
            failures.append(path)
    print(("FAILED: " + ", ".join(failures)) if failures else "No endpoint runs more queries as its data grows.")
    code = 1 if failures else 0
finally:
    acc.cleanup_test_users()
sys.exit(code)
