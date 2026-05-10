import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_jwt_secret() -> str:
    configured_secret = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or os.getenv("NORA_JWT_SECRET")
    if configured_secret:
        return configured_secret

    if not hasattr(get_jwt_secret, "_runtime_secret"):
        setattr(get_jwt_secret, "_runtime_secret", secrets.token_urlsafe(48))
    return getattr(get_jwt_secret, "_runtime_secret")


def get_jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, get_jwt_secret(), algorithm=get_jwt_algorithm())


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[get_jwt_algorithm()])
    except JWTError as exc:
        raise ValueError("Invalid or expired token.") from exc
