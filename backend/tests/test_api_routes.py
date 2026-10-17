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
    "/appointments/doctors/{doctor_id}/slots": "open times of a verified doctor; no patient data",
    "/appointments/doctors/{doctor_id}/reviews": "ratings of a verified doctor, without patient names",
    "/symptoms/check": "emergency advice must not wait behind a login; rate limited per IP, identity optional",
    "/files/{file_path:path}": "signed, short-lived links; the signature is checked in the handler",
    "/auth/forgot-password": "no account yet to sign in with; same answer for every address, rate limited, emails the account only",
    "/auth/reset-password": "needs the emailed 6-digit code (5 tries, 10 minutes); rate limited; same error for every failure",
    "/auth/verify-email": "the single-use link from the email is the proof; rate limited",
    "/payments/stripe/webhook": "called by Stripe; trusted only with a valid Stripe-Signature (services/payments.py)",
    **{f"{prefix}/{path}": "signing in and signing up" for prefix in ("/auth", "/api/auth")
       for path in ("login", "signup", "refresh", "logout")},
}  # fmt: skip

# Older routes that return plain dicts; known, and not to grow. New routes need a response model.
WITHOUT_RESPONSE_MODEL = {
    "/appointments/{appointment_id}", "/patient/medicines/{medicine_id}", "/patient/reports/{report_id}",
    "/reminders/{reminder_id}", "/api/admin/dashboard-stats", "/api/admin/doctors/pending",
    "/api/admin/recent-activity", "/doctor/dashboard", "/doctor/overview", "/files/{file_path:path}", "/health",
    "/health/database", "/patient/overview", "/api/admin/doctors/{doctor_id}/approve",
    "/api/admin/doctors/{doctor_id}/reject", "/doctor/access/end",
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


# Signed-in routes open to every role, each reviewed: they answer only about the caller's own data,
# or check the object (owner, treating doctor) inside the handler. Anything else needs a role.
ANY_SIGNED_IN_ROLE = {
    "/auth/me": "the caller's own account",
    "/api/auth/me": "the caller's own account",
    "/nlp/summarize": "summarises text the caller pastes; stores nothing",
    "/appointments": "lists the caller's own appointments (patients: booked by them; doctors: booked with them)",
    "/appointments/{appointment_id}": "owner, treating doctor or admin only (can_access_appointment); no payment status changes",
    "/payments": "the caller's own payments",
    "/profile": "the caller's own profile",
    "/notifications": "the caller's own notifications",
    "/notifications/unread-count": "the caller's own unread count",
    "/notifications/{notification_id}": "the caller's own notification (others look like 404): dismiss",
    "/notifications/read-all": "the caller's own notifications",
    "/notifications/{notification_id}/read": "the caller's own notification (others look like 404)",
    "/profile/account": "the caller's own name and phone",
    "/auth/resend-verification": "the caller's own confirmation link; one a minute, 3 an hour",
    "/health-record/options": "suggestion words from the knowledge base (allergy and condition names); no patient data",
}


def test_a_route_without_a_role_is_a_reviewed_exception():
    roles = {require_admin, require_doctor, require_patient}
    no_role = {
        r.path
        for r in ROUTES
        if get_current_user in dependencies(r.dependant) and not roles & set(dependencies(r.dependant))
    }
    assert no_role == set(ANY_SIGNED_IN_ROLE), f"routes open to every role: {sorted(no_role ^ set(ANY_SIGNED_IN_ROLE))}"


def test_each_role_has_only_its_own_routes():
    """A route names at most one role: nothing is shared between patient, doctor and admin by accident."""
    several = {}
    for route in ROUTES:
        required = {
            role.__name__
            for role in (require_admin, require_doctor, require_patient)
            if role in dependencies(route.dependant)
        }
        if len(required) > 1:
            several[route.path] = sorted(required)
    assert several == {}
