"""Test users for the Playwright integration tests (tests/e2e).

    backend\\venv\\Scripts\\python.exe tests\\e2e\\fixtures.py setup <out.json>
    backend\\venv\\Scripts\\python.exe tests\\e2e\\fixtures.py cleanup

Reuses tests/acceptance_test.py: the same localhost-only database guard, the same
"phase0-test-" users, and the same cleanup (only those users, their rows and upload
folders). Do not run the two suites at the same time: each cleans up the other's users.

`setup` writes the users (email, password, id, token) to <out.json> under test-results/,
which git ignores. It also records whether OCR or AI keys are set (true/false only), so
tests that would call those paid services can skip themselves.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# acceptance_test puts backend/ on sys.path and loads the .env files, so it comes first.
import acceptance_test as base
from sqlalchemy import text

from auth import hash_password
from config import settings

PASSWORD = f"E2e-{secrets.token_hex(8)}"
RUN = base.run_id


def make_user(key: str, role: str, **options) -> dict:
    """A test user who can sign in through the UI: real password hash and an @example.com email."""
    user_id = base.create_user(f"e2e-{key}", role, **options)
    email = f"{base.TEST_PREFIX}e2e-{key}-{RUN}@example.com"
    full_name = f"{base.TEST_PREFIX}e2e {key} {RUN}"
    with base.engine.begin() as conn:
        conn.execute(
            text(
                "update users set email = :email, full_name = :name, hashed_password = :pw, phone = :phone where id = :id"
            ),
            {
                "email": email,
                "name": full_name,
                "pw": hash_password(PASSWORD),
                "phone": f"0300 {user_id:07d}",
                "id": user_id,
            },
        )
    return {
        "id": user_id,
        "email": email,
        "fullName": full_name,
        "role": role.lower(),
        "token": base.token_for(user_id),
    }


def setup(out_file: Path) -> None:
    base.assert_local_databases()
    base.cleanup_test_users()  # leftovers from an interrupted run
    users = {
        "patient": make_user("patient", "PATIENT"),
        "patientEmpty": make_user("patient-empty", "PATIENT"),
        "doctor": make_user("doctor", "DOCTOR"),
        "doctorPendingA": make_user("doctor-pending-a", "DOCTOR", doctor_status="pending"),
        "doctorPendingB": make_user("doctor-pending-b", "DOCTOR", doctor_status="pending"),
        # Never reviewed by a test, so it stays pending (admin.spec approves A and rejects B).
        "doctorUnreviewed": make_user("doctor-unreviewed", "DOCTOR", doctor_status="pending"),
        "admin": make_user("admin", "ADMIN"),
    }
    report_id = base.create_record(users["patient"]["id"], f"{base.TEST_PREFIX}e2e blood panel {RUN}")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(
            {
                "run": RUN,
                "password": PASSWORD,
                "users": users,
                "reportId": report_id,
                "ocrKeySet": bool(settings.ocr_space_api_key),
                "aiKeySet": bool(settings.openai_api_key or settings.groq_api_key),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"e2e fixtures: {len(users)} phase0-test- users and 1 report created.")


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup" and len(sys.argv) == 3:
        setup(Path(sys.argv[2]))
        return 0
    if command == "cleanup":
        base.assert_local_databases()
        base.cleanup_test_users()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
