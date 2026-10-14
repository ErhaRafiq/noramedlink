"""Audit of every API route: sign-in, roles, response models and rate limits (AGENTS.md 5 and 16).

A new route fails here until it is signed-in, or added deliberately to a reviewed list below.
"""

import re

from fastapi.routing import APIRoute

import main
from dependencies import get_current_user, require_admin, require_doctor, require_patient
from rate_limit import limiter

ROUTES = [r for r in main.app.routes if isinstance(r, APIRoute)]

# Reviewed: open without signing in, each for a stated reason.
PUBLIC = {
    "/health": "liveness check, no data",
    "/health/database": "up or down only, no address or credentials",
    "/appointments/doctors": "the public list of verified, active doctors",
    "/files/{file_path:path}": "signed, short-lived links; the signature is checked in the handler",
    **{f"{prefix}/{path}": "signing in and signing up" for prefix in ("/auth", "/api/auth")
       for path in ("login", "signup", "signup/doctor", "signup/patient", "request-otp", "verify-otp-signup")},
}  # fmt: skip

# Older routes that return plain dicts; known, and not to grow. New routes need a response model.
WITHOUT_RESPONSE_MODEL = {
    "/appointments/{appointment_id}", "/patient/medicines/{medicine_id}", "/patient/reports/{report_id}",
    "/reminders/{reminder_id}", "/api/admin/dashboard-stats", "/api/admin/doctors/pending",
    "/api/admin/recent-activity", "/doctor/dashboard", "/doctor/overview", "/files/{file_path:path}", "/health",
    "/health/database", "/patient/overview", "/api/admin/doctors/{doctor_id}/approve",
    "/api/admin/doctors/{doctor_id}/reject", "/api/auth/request-otp", "/auth/request-otp", "/doctor/access/end",
    "/doctor/access/unlock", "/emergency/requests", "/patient/dashboard-otp",
}  # fmt: skip

# Reviewed: limited by their own, stricter rule instead of @limiter.limit.
OWN_LIMITS = {
    "/doctor/access/unlock": "5 failed codes per 15 minutes per doctor (services/dashboard_access.py)",
}

# Paths whose role is fixed by their prefix.
ROLE_BY_PREFIX = [
    ("/api/admin/", require_admin),
    ("/doctor/", require_doctor),
    ("/patient/", require_patient),
]
PATIENT_PATHS_OPEN_TO_DOCTORS = set()  # none today


def dependencies(dependant):
    found = []
    for dep in dependant.dependencies:
        found.append(dep.call)
        found += dependencies(dep)
    return found


def test_every_route_needs_sign_in_unless_it_is_on_the_reviewed_public_list():
    open_routes = {r.path for r in ROUTES if get_current_user not in dependencies(r.dependant)}
    assert open_routes == set(PUBLIC), f"unreviewed public routes: {sorted(open_routes - set(PUBLIC))}"


def test_role_routes_check_the_role():
    wrong = []
    for route in ROUTES:
        for prefix, role in ROLE_BY_PREFIX:
            in_scope = route.path.startswith(prefix) and route.path not in PATIENT_PATHS_OPEN_TO_DOCTORS
            if in_scope and role not in dependencies(route.dependant):
                wrong.append(f"{sorted(route.methods)} {route.path} lacks {role.__name__}")
    assert wrong == []


def test_new_routes_have_a_response_model():
    missing = {r.path for r in ROUTES if r.response_model is None}
    assert missing <= WITHOUT_RESPONSE_MODEL, (
        f"routes without a response model: {sorted(missing - WITHOUT_RESPONSE_MODEL)}"
    )


def test_routes_that_cost_money_or_protect_accounts_are_rate_limited():
    costly = re.compile(
        r"(upload|regenerate|generate|summarize|ocr|login|signup|dashboard-otp|unlock|interaction|safety)"
    )
    limited = set(limiter._route_limits)  # "module.function" of every @limiter.limit route
    unlimited = [
        f"{sorted(r.methods)} {r.path}"
        for r in ROUTES
        if costly.search(r.path)
        and "POST" in r.methods
        and f"{r.endpoint.__module__}.{r.endpoint.__name__}" not in limited
        and r.path not in OWN_LIMITS
    ]
    assert unlimited == []


def test_no_route_takes_a_user_id_from_the_query_string():
    # Identity comes only from the verified token (AGENTS.md 5).
    offenders = [
        f"{sorted(r.methods)} {r.path}"
        for r in ROUTES
        for param in r.dependant.query_params
        if param.name.lower() in {"user_id", "userid", "patient_id", "doctor_id", "admin_id"}
    ]
    assert offenders == []
