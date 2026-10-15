"""Sign-in sessions: a short-lived access token plus a rotating refresh token.

- The access token is a JWT (15 minutes). The refresh token is a random secret; only its SHA-256 is stored.
- Every refresh rotates: the used token is revoked and a new one issued in the same family.
- A token that was already revoked and is presented again was stolen or replayed: the whole family
  is revoked, which signs that session out everywhere.
- Logging out, or an account turned inactive, ends the family. Browsers never see either token:
  the Next.js server keeps them in HttpOnly cookies (app/api/auth, app/api/backend).
"""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from auth import create_access_token
from models import RefreshToken, User

log = logging.getLogger("nora.auth")

REFRESH_DAYS = 7
# A request that raced the rotation (two tabs, parallel calls) may still carry the token just used. Within
# this many seconds that is refused without ending the session; later, it is treated as a replay.
GRACE_SECONDS = 3


class SessionError(Exception):
    """The refresh token is unknown, expired, revoked or its account is inactive."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def access_token_for(user: User) -> str:
    return create_access_token(str(user.id), {"email": user.email, "role": user.role.lower()})


def _issue(db: Session, user: User, family_id: str) -> tuple[str, str]:
    refresh = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=_hash(refresh),
            expires_at=_now() + timedelta(days=REFRESH_DAYS),
        )
    )
    return access_token_for(user), refresh


def start_session(db: Session, user: User) -> tuple[str, str]:
    """A new sign-in: (access token, refresh token). The caller commits."""
    return _issue(db, user, secrets.token_hex(16))


def revoke_family(db: Session, family_id: str) -> None:
    now = _now()
    for row in db.query(RefreshToken).filter(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)):
        row.revoked_at = now


def refresh_session(db: Session, refresh_token: str) -> tuple[User, str, str]:
    """Trade a refresh token for a new pair. Commits (a replay must still revoke the family)."""
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash(refresh_token or "")).first()
    if row is None:
        raise SessionError("Unknown refresh token.")
    if row.revoked_at is not None:
        if (_now() - _aware(row.revoked_at)).total_seconds() <= GRACE_SECONDS:
            raise SessionError("Refresh token was just rotated.")
        revoke_family(db, row.family_id)
        db.commit()
        log.warning("A revoked refresh token was used again; session family revoked (user %s).", row.user_id)
        raise SessionError("Refresh token already used.")
    if _aware(row.expires_at) <= _now():
        raise SessionError("Refresh token expired.")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        revoke_family(db, row.family_id)
        db.commit()
        raise SessionError("Account unavailable.")
    row.revoked_at = _now()
    access, refresh = _issue(db, user, row.family_id)
    db.commit()
    return user, access, refresh


def end_session(db: Session, refresh_token: str) -> None:
    """Log out: revoke the token's whole family. Unknown tokens are ignored."""
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash(refresh_token or "")).first()
    if row is not None:
        revoke_family(db, row.family_id)
        db.commit()
