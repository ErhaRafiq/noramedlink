"""Demo doctors for the home-visit service, on a LOCAL development database only.

    backend\\venv\\Scripts\\python.exe scripts\\home_visit_demo.py seed      create the demo doctors (safe to repeat)
    backend\\venv\\Scripts\\python.exe scripts\\home_visit_demo.py status    list them
    backend\\venv\\Scripts\\python.exe scripts\\home_visit_demo.py remove    delete them and everything tied to them

The four doctors are labelled "[DEMO]" test accounts at approximate places in Islamabad (F-10, G-11, Blue Area,
Bahria Town), approved, with home visits on and open all day, so a request can be matched at any hour. They
cannot sign in unless you set DEMO_DOCTOR_PASSWORD in your environment before `seed` (it is never printed or
stored anywhere else). `remove` deletes only accounts whose email is demo-homevisit-*@example.test AND whose
name starts with "[DEMO] ". Refuses to run unless every database URL points to localhost.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))
os.chdir(ROOT / "backend")
os.environ.setdefault("DISABLE_PAID_SERVICES", "1")

import acceptance_test as base  # noqa: E402  (loads the .env files and the localhost-only guard)
from sqlalchemy import text  # noqa: E402

from auth import hash_password  # noqa: E402
from services.home_visits.demo_data import DOCTORS, EMAIL_PREFIX, EMAIL_SUFFIX, HOSPITAL, NAME_PREFIX, is_demo_account  # noqa: E402


def demo_ids(conn) -> dict[str, int]:
    rows = conn.execute(
        text("select id, email, full_name from users where email like :e and full_name like :n"),
        {"e": f"{EMAIL_PREFIX}%{EMAIL_SUFFIX}", "n": f"{NAME_PREFIX}%"},
    ).all()
    return {email: user_id for user_id, email, name in rows if is_demo_account(email, name)}


def seed() -> None:
    password = os.environ.get("DEMO_DOCTOR_PASSWORD", "")
    hashed = hash_password(password) if password else f"unusable-{secrets.token_hex(16)}"
    created = 0
    with base.engine.begin() as conn:
        existing = demo_ids(conn)
        for doctor in DOCTORS:
            if doctor.email in existing:
                continue
            user_id = conn.execute(
                text(
                    "insert into users (full_name, email, hashed_password, role, phone, is_active, is_email_verified, is_identity_verified) "
                    "values (:name, :email, :pw, 'DOCTOR', '', true, true, true) returning id"
                ),
                {"name": doctor.full_name, "email": doctor.email, "pw": hashed},
            ).scalar_one()
            conn.execute(
                text(
                    "insert into doctor_profiles (user_id, pmdc_number, specialization, hospital_name, verification_status, "
                    "consultation_modes, city, home_visits_enabled, service_radius_km, base_latitude, base_longitude) "
                    "values (:u, :pmdc, :spec, :hosp, 'approved', 'in_clinic,home', 'Islamabad', true, :r, :la, :lo)"
                ),
                {"u": user_id, "pmdc": doctor.pmdc, "spec": doctor.specialty, "hosp": HOSPITAL, "r": doctor.radius_km,
                 "la": doctor.latitude, "lo": doctor.longitude},
            )
            for weekday in range(7):
                conn.execute(
                    text("insert into doctor_availability (doctor_id, weekday, start_time, end_time, slot_minutes) values (:u, :d, '00:00', '23:59', 30)"),
                    {"u": user_id, "d": weekday},
                )
            created += 1
    signin = "they can sign in with DEMO_DOCTOR_PASSWORD" if password else "they cannot sign in (set DEMO_DOCTOR_PASSWORD before seeding to log in as one)"
    print(f"Created {created} demo doctor(s); {len(DOCTORS) - created} already existed. {signin}.")
    status()


def status() -> None:
    with base.engine.connect() as conn:
        found = demo_ids(conn)
    for doctor in DOCTORS:
        state = "present" if doctor.email in found else "absent"
        print(f"  {doctor.full_name:50} {doctor.specialty:18} radius {doctor.radius_km:g} km  {state}  {doctor.email}")


# Only the demo doctors' own rows. Patients' rows that mention a demo doctor (a visit, an appointment) are kept:
# their doctor reference is cleared by the foreign keys, so a real patient's history is never deleted here.
OWN_ROWS = [
    ("email_outbox", "user_id"),
    ("auth_tokens", "user_id"),
    ("notifications", "user_id"),
    ("notification_tokens", "user_id"),
    ("doctor_availability", "doctor_id"),
    ("home_visit_offers", "doctor_id"),
    ("doctor_profiles", "user_id"),
]


def remove() -> None:
    with base.engine.begin() as conn:
        ids = list(demo_ids(conn).values())
        if not ids:
            print("No demo doctors to remove.")
            return
        existing = set(conn.execute(text("select table_name from information_schema.tables where table_schema = 'public'")).scalars())
        deleted = 0
        for table, column in OWN_ROWS:
            if table in existing:
                deleted += conn.execute(text(f"delete from {table} where {column} = any(:ids)"), {"ids": ids}).rowcount
        users = conn.execute(text("delete from users where id = any(:ids)"), {"ids": ids}).rowcount
    print(f"Removed {users} demo doctor(s) and {deleted} related row(s).")


def main() -> int:
    base.assert_local_databases()
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"seed": seed, "status": status, "remove": remove}.get(command, lambda: sys.exit(__doc__))()
    return 0


if __name__ == "__main__":
    sys.exit(main())
