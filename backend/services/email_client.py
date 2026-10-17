"""Sending one email through Resend (https://resend.com/docs/api-reference/emails/send-email).

- One HTTPS call: `POST https://api.resend.com/emails`, `Authorization: Bearer <key>`. The key comes only from
  `config.settings` (RESEND_API_KEY) and is never logged. The sender's domain must be verified in Resend.
- An `Idempotency-Key` header makes a retry of the same email safe: Resend returns the first answer instead of
  sending twice (valid for 24 hours).
- Each email carries an HTML part and a plain-text part, and a `kind` tag for Resend's own dashboard.
- Errors are sorted into "worth retrying" (a timeout, 429 rate or quota, 5xx) and "will never work" (a bad
  address, an unverified domain, a bad key): the outbox retries only the first kind.
- Nothing is logged but the kind and the outcome: no address, no subject, no body (a body can hold a code).
"""

import logging
from collections.abc import Callable

import httpx

from config import settings

log = logging.getLogger("nora.email")

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10.0


class EmailDisabled(Exception):
    """No Resend key is configured (or this is a test run): nothing is sent."""


class EmailError(Exception):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


def is_configured() -> bool:
    return bool(settings.resend_api_key)


def send(
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    idempotency_key: str,
    kind: str,
    post: Callable[..., httpx.Response] = httpx.post,
) -> str:
    """Send one email and return Resend's id for it. Raises EmailDisabled or EmailError."""
    if not settings.resend_api_key:
        raise EmailDisabled
    payload: dict = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
        "tags": [{"name": "kind", "value": kind}],
    }
    if settings.email_reply_to:
        payload["reply_to"] = settings.email_reply_to
    try:
        response = post(
            RESEND_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Idempotency-Key": idempotency_key[:256],
                "User-Agent": "NoraMedLink academic prototype",
            },
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        log.warning("Email %s: the provider could not be reached (%s)", kind, type(exc).__name__)
        raise EmailError("The email service could not be reached.", retryable=True) from exc

    if response.status_code == 200:
        try:
            provider_id = str(response.json().get("id") or "")
        except ValueError:
            provider_id = ""
        log.info("Email %s sent", kind)
        return provider_id
    retryable = response.status_code == 429 or response.status_code >= 500
    # Resend's error body names the problem ("name", "message"); it never repeats the key. Keep only the name.
    try:
        name = str(response.json().get("name") or "")[:60]
    except ValueError:
        name = ""
    log.warning("Email %s refused: HTTP %s %s", kind, response.status_code, name)
    raise EmailError(f"HTTP {response.status_code} {name}".strip(), retryable=retryable)
