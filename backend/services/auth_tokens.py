"""One-time secrets that prove someone controls an email address (Module 1: verification and password reset).

- A reset **code** is 6 digits, works for 10 minutes, allows 5 wrong tries, and is single-use.
- A verification **link token** is 256 random bits, works for 24 hours, and is single-use.
- Only a keyed hash (HMAC-SHA256 with the server secret) is stored, never the code or token, so a copy of the
  database does not hold working secrets and a 6-digit code cannot be guessed offline without the key.
- Asking for a new one is limited: at least 60 seconds apart and at most 3 an hour per account and purpose. The
  limit is checked in the database, so it holds across restarts and several server processes. A new secret
  replaces the old one.
- Secrets are never logged.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from auth import get_jwt_secret
from models import AuthToken, User

VERIFY_EMAIL, RESET_PASSWORD = "verify_email", "reset_password"
RESET_MINUTES = 10
VERIFY_HOURS = 24
MAX_ATTEMPTS = 5
COOLDOWN_SECONDS = 60
MAX_PER_HOUR = 3


class TooSoon(Exception):
    """Another one was sent less than a minute ago."""

    def __init__(self, retry_after: int):
        super().__init__("too soon")
        self.retry_after = retry_after


class TooMany(Exception):
    """The hourly limit for this account and purpose is used up."""

    def __init__(self, retry_after: int):
        super().__init__("too many")
        self.retry_after = retry_after


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def fingerprint(purpose: str, secret: str, user_id: int | None = None) -> str:
    """The stored form of a secret: HMAC-SHA256 under the server key, bound to its purpose (and user, for codes)."""
    message = f"{purpose}:{user_id if user_id is not None else '-'}:{secret}"
    return hmac.new(get_jwt_secret().encode(), message.encode(), hashlib.sha256).hexdigest()


def _check_limits(db: Session, user: User, purpose: str) -> None:
    now = _now()
    recent = (
        db.query(AuthToken.created_at)
        .filter(
            AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.created_at >= now - timedelta(hours=1)
        )
        .order_by(AuthToken.created_at.desc())
        .all()
    )
    if recent:
        wait = COOLDOWN_SECONDS - (now - _aware(recent[0][0])).total_seconds()
        if wait > 0:
            raise TooSoon(int(wait) + 1)
    if len(recent) >= MAX_PER_HOUR:
        oldest = _aware(recent[-1][0])
        raise TooMany(max(1, int((oldest + timedelta(hours=1) - now).total_seconds())))


def issue(db: Session, user: User, purpose: str) -> str:
    """A new secret for the user (a 6-digit code for a reset, a link token for verification). The caller commits.
    Raises TooSoon or TooMany; an older unused secret of the same purpose stops working."""
    _check_limits(db, user, purpose)
    now = _now()
    for old in db.query(AuthToken).filter(
        AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None)
    ):
        old.used_at = now
    if purpose == RESET_PASSWORD:
        secret = f"{secrets.randbelow(1_000_000):06d}"
        row = AuthToken(user_id=user.id, purpose=purpose, token_hash=fingerprint(purpose, secret, user.id),
                        expires_at=now + timedelta(minutes=RESET_MINUTES))  # fmt: skip
    else:
        secret = secrets.token_urlsafe(32)
        row = AuthToken(user_id=user.id, purpose=purpose, token_hash=fingerprint(purpose, secret),
                        expires_at=now + timedelta(hours=VERIFY_HOURS))  # fmt: skip
    db.add(row)
    db.flush()
    return secret


def verify_code(db: Session, user: User, purpose: str, code: str) -> bool:
    """Whether `code` is the user's current, unused, unexpired code. Wrong tries are counted and committed; after
    5 the code is dead even if the right one is typed. A right code is used up."""
    row = (
        db.query(AuthToken)
        .filter(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
        .order_by(AuthToken.created_at.desc(), AuthToken.id.desc())
        .first()
    )
    if row is None or _aware(row.expires_at) <= _now() or row.attempts >= MAX_ATTEMPTS:
        return False
    if hmac.compare_digest(row.token_hash, fingerprint(purpose, (code or "").strip(), user.id)):
        row.used_at = _now()
        db.commit()
        return True
    row.attempts += 1
    db.commit()
    return False


def consume_link(db: Session, purpose: str, token: str) -> User | None:
    """The user a link token belongs to, when it is unused and unexpired; the token is used up. Commits."""
    row = (
        db.query(AuthToken)
        .filter(AuthToken.purpose == purpose, AuthToken.token_hash == fingerprint(purpose, (token or "").strip()),
                AuthToken.used_at.is_(None))
        .first()
    )  # fmt: skip
    if row is None or _aware(row.expires_at) <= _now():
        return None
    row.used_at = _now()
    user = db.get(User, row.user_id)
    db.commit()
    return user
