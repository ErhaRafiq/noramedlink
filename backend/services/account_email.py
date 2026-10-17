"""Emails that must go at once and hold a secret or a security notice: the verification link, the password
reset code, and "your password was changed". They run as a background task after the request has answered, so
the page never waits on the mail provider.

The secret is passed in memory only. The outbox gets a log row with no content (kind, address, outcome), so a
copy of the database never holds a working code or link. If the send fails nothing is retried: the person asks
again (the limits in auth_tokens.py keep that to a few a hour). Errors are logged by kind only.
"""

import logging
from datetime import UTC, datetime
from uuid import uuid4

from database import SessionLocal
from models import EmailOutbox, User
from services import email_client
from services.email_templates import app_url, render

log = logging.getLogger("nora.email")


def verification_link(token: str) -> str:
    return f"{app_url('/verify-email')}?token={token}"


def send_account_email(user_id: int, kind: str, context: dict) -> None:
    """Render and send one account email now. Never raises."""
    if not email_client.is_configured():
        log.info("Email %s not sent: no email provider is configured", kind)
        return
    try:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user is None or not user.is_active or not user.email:
                return
            rendered = render(kind, {**context, "name": user.full_name})
            row = EmailOutbox(
                user_id=user.id, to_address=user.email, kind=kind, context=None, status="pending",
                dedupe_key=f"{kind}:{user.id}:{uuid4().hex}",
            )  # fmt: skip
            try:
                row.provider_id = email_client.send(
                    to=user.email, subject=rendered.subject, html=rendered.html, text=rendered.text,
                    idempotency_key=row.dedupe_key, kind=kind,
                )  # fmt: skip
                row.status, row.sent_at = "sent", datetime.now(UTC)
            except email_client.EmailError as error:
                row.status, row.last_error = "failed", str(error)[:200]
            db.add(row)
            db.commit()
    except Exception:
        log.exception("Email %s could not be sent", kind)
