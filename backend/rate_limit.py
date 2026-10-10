"""Request rate limiting (slowapi), shared by every router.

Keys
- Signed-in requests are counted per user. The user id comes from a token whose
  signature has been verified, so nobody can spend another user's allowance.
- Anonymous requests (and invalid tokens) are counted per client IP.
- Login is also counted per account (email), so one client cannot lock out others
  that share its IP, and an attacker cannot guess one password from many IPs fast.

Client IP
The browser reaches FastAPI through the Next.js proxy, so the direct peer is usually
that proxy. X-Forwarded-For is trusted only when the peer is in TRUSTED_PROXY_IPS
(localhost by default); otherwise the peer address is used, so clients cannot spoof it.

Every limit can be overridden with an environment variable (see LIMITS below), and
RATE_LIMIT_ENABLED=false turns limiting off. Counters live in process memory: fine for
one server process, but several workers would each count separately (use a shared
store such as Redis via RATE_LIMIT_STORAGE_URI in that case).
"""

import math
import os

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from auth import decode_access_token


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


# Limit strings use the `limits` notation: "<count>/<second|minute|hour|day>".
DEFAULT_LIMIT = _env("RATE_LIMIT_DEFAULT", "200/minute")
LOGIN_LIMIT = _env("RATE_LIMIT_LOGIN", "20/minute")  # per IP (the per-email limit is the tighter one)
LOGIN_ACCOUNT_LIMIT = _env("RATE_LIMIT_LOGIN_ACCOUNT", "5/minute")  # per email
SIGNUP_LIMIT = _env("RATE_LIMIT_SIGNUP", "5/minute")  # per IP
UPLOAD_LIMIT = _env("RATE_LIMIT_UPLOAD", "10/minute")  # per user
AI_LIMIT = _env("RATE_LIMIT_AI", "10/minute")  # per user: OCR, summaries, generated insights
ACCESS_CODE_LIMIT = _env("RATE_LIMIT_ACCESS_CODE", "10/minute")  # per patient, issuing doctor codes

RATE_LIMIT_ENABLED = _env("RATE_LIMIT_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
STORAGE_URI = _env("RATE_LIMIT_STORAGE_URI", "memory://")
TRUSTED_PROXY_IPS = {
    ip.strip() for ip in _env("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",") if ip.strip()
}


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and peer in TRUSTED_PROXY_IPS:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return peer


def ip_key(request: Request) -> str:
    return f"ip:{client_ip(request)}"


def user_or_ip_key(request: Request) -> str:
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        try:
            subject = decode_access_token(authorization.split(" ", 1)[1].strip()).get("sub")
        except Exception:  # invalid or expired: count it against the IP instead
            subject = None
        if subject:
            return f"user:{subject}"
    return ip_key(request)


limiter = Limiter(
    key_func=user_or_ip_key,
    default_limits=[DEFAULT_LIMIT],
    storage_uri=STORAGE_URI,
    enabled=RATE_LIMIT_ENABLED,
)

# Separate counter for limits whose key comes from the request body (login per email).
_account_storage = storage_from_string(STORAGE_URI)
_account_limiter = MovingWindowRateLimiter(_account_storage)


def _retry_after_seconds(limit_string: str) -> int:
    return max(1, math.ceil(parse(limit_string).get_expiry()))


def _too_many_requests_detail(seconds: int) -> str:
    return f"Too many requests. Please wait {seconds} seconds and try again."


def enforce_account_limit(scope: str, identifier: str, limit_string: str = LOGIN_ACCOUNT_LIMIT) -> None:
    """Counts one attempt for `identifier` (e.g. an email) and raises 429 past the limit."""
    if not RATE_LIMIT_ENABLED:
        return
    if not _account_limiter.hit(parse(limit_string), scope, identifier.strip().lower()):
        seconds = _retry_after_seconds(limit_string)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_too_many_requests_detail(seconds),
            headers={"Retry-After": str(seconds)},
        )


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 in the same {"detail": ...} shape as every other API error."""
    limit = getattr(exc, "limit", None)
    seconds = max(1, math.ceil(limit.limit.get_expiry())) if limit is not None else 60
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": _too_many_requests_detail(seconds)},
        headers={"Retry-After": str(seconds)},
    )
