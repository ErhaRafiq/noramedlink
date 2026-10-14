"""Backend settings, read once from the environment.

Every environment variable the backend uses is read here, so the names, defaults and
types live in one place (see backend/.env.example for what each one means).

.env files: the project-root .env is loaded without overriding the process environment,
then backend/.env is loaded on top and wins. A blank value counts as unset and falls back
to the default.
"""

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def env_str(name: str, default: str = "", *, strip_quotes: bool = False) -> str:
    value = (os.getenv(name) or "").strip()
    if strip_quotes:
        value = value.strip('"').strip("'")
    return value or default


def env_int(name: str, default: int) -> int:
    return int(env_str(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(env_str(name, str(default)))


def env_bool(name: str, default: bool) -> bool:
    value = env_str(name).lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    items = [item.strip() for item in env_str(name).split(",") if item.strip()]
    return items or list(default or [])


@dataclass(frozen=True)
class Settings:
    # Database
    database_url: str = ""  # empty: local SQLite fallback (development only)
    db_pool_recycle_seconds: int = 1800
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_seconds: int = 30

    # Files
    upload_dir: str = "uploads"
    max_upload_mb: int = 10

    # Auth
    jwt_secret: str = ""  # empty: a random per-process secret (tokens die on restart)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    admin_invite_code: str = ""
    frontend_origin: str = "http://localhost:3000"

    # Signup OTP delivery
    otp_expiry_minutes: int = 5
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Nora MedLink"
    smtp_use_tls: bool = True
    sms_provider: str = ""
    sms_api_key: str = ""

    # AI providers. DISABLE_PAID_SERVICES=1 ignores every AI and OCR.space key (test runs: tests never
    # call a paid service, even when backend/.env has keys).
    paid_services_disabled: bool = False
    openai_api_key: str = ""
    openai_scan_model: str = "gpt-4.1-mini"
    openai_fallback_models: list[str] = field(default_factory=list)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_chat_models: list[str] = field(default_factory=lambda: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"])
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_fallback_models: list[str] = field(default_factory=list)
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    biobert_model: str = "d4data/biomedical-ner-all"

    # OCR.space
    ocr_space_api_key: str = ""
    ocr_space_timeout_seconds: float = 60
    ocr_space_language: str = "eng"
    ocr_space_engine: str = "2"
    ocr_model_dir: str = "models"  # local OCR model cache, relative to backend/

    # Rate limits ("<count>/<second|minute|hour|day>"); see rate_limit.py
    rate_limit_enabled: bool = True
    rate_limit_storage_uri: str = "memory://"
    rate_limit_default: str = "200/minute"
    rate_limit_login: str = "20/minute"
    rate_limit_login_account: str = "5/minute"
    rate_limit_signup: str = "5/minute"
    rate_limit_upload: str = "10/minute"
    rate_limit_ai: str = "10/minute"
    rate_limit_access_code: str = "10/minute"
    trusted_proxy_ips: list[str] = field(default_factory=lambda: ["127.0.0.1", "::1"])

    # Logging
    log_level: str = "INFO"


def load_settings() -> Settings:
    d = Settings()
    return Settings(
        database_url=env_str("FASTAPI_DATABASE_URL", strip_quotes=True) or env_str("DATABASE_URL", strip_quotes=True),
        db_pool_recycle_seconds=env_int("DB_POOL_RECYCLE_SECONDS", d.db_pool_recycle_seconds),
        db_pool_size=env_int("DB_POOL_SIZE", d.db_pool_size),
        db_max_overflow=env_int("DB_MAX_OVERFLOW", d.db_max_overflow),
        db_pool_timeout_seconds=env_int("DB_POOL_TIMEOUT_SECONDS", d.db_pool_timeout_seconds),
        upload_dir=env_str("UPLOAD_DIR", d.upload_dir),
        max_upload_mb=env_int("MAX_UPLOAD_MB", d.max_upload_mb),
        jwt_secret=env_str("JWT_SECRET_KEY") or env_str("SECRET_KEY") or env_str("NORA_JWT_SECRET"),
        jwt_algorithm=env_str("JWT_ALGORITHM", d.jwt_algorithm),
        access_token_expire_minutes=env_int("ACCESS_TOKEN_EXPIRE_MINUTES", d.access_token_expire_minutes),
        admin_invite_code=env_str("ADMIN_INVITE_CODE") or env_str("ADMIN_SIGNUP_CODE"),
        frontend_origin=env_str("FRONTEND_ORIGIN", d.frontend_origin),
        otp_expiry_minutes=env_int("OTP_EXPIRY_MINUTES", d.otp_expiry_minutes),
        smtp_host=env_str("SMTP_HOST"),
        smtp_port=env_int("SMTP_PORT", d.smtp_port),
        smtp_username=env_str("SMTP_USERNAME"),
        smtp_password=env_str("SMTP_PASSWORD"),
        smtp_from_email=env_str("SMTP_FROM_EMAIL"),
        smtp_from_name=env_str("SMTP_FROM_NAME", d.smtp_from_name),
        smtp_use_tls=env_bool("SMTP_USE_TLS", d.smtp_use_tls),
        sms_provider=env_str("SMS_PROVIDER"),
        sms_api_key=env_str("SMS_API_KEY"),
        paid_services_disabled=env_bool("DISABLE_PAID_SERVICES", d.paid_services_disabled),
        openai_api_key=env_str("OPENAI_API_KEY"),
        openai_scan_model=env_str("OPENAI_SCAN_MODEL", d.openai_scan_model),
        openai_fallback_models=env_list("OPENAI_FALLBACK_MODELS"),
        groq_api_key=env_str("GROQ_API_KEY"),
        groq_base_url=env_str("GROQ_BASE_URL", d.groq_base_url),
        groq_chat_models=env_list("GROQ_CHAT_MODELS", d.groq_chat_models),
        gemini_api_key=env_str("GEMINI_API_KEY") or env_str("GOOGLE_API_KEY"),
        gemini_model=env_str("GEMINI_MODEL", d.gemini_model),
        gemini_fallback_models=env_list("GEMINI_FALLBACK_MODELS"),
        gemini_base_url=env_str("GEMINI_BASE_URL", d.gemini_base_url),
        biobert_model=env_str("BIOBERT_MODEL", d.biobert_model),
        ocr_space_api_key=env_str("OCR_SPACE_API_KEY", strip_quotes=True),
        ocr_space_timeout_seconds=env_float("OCR_SPACE_TIMEOUT_SECONDS", d.ocr_space_timeout_seconds),
        ocr_space_language=env_str("OCR_SPACE_LANGUAGE", d.ocr_space_language),
        ocr_space_engine=env_str("OCR_SPACE_ENGINE", d.ocr_space_engine),
        ocr_model_dir=env_str("OCR_MODEL_DIR", d.ocr_model_dir),
        rate_limit_enabled=env_bool("RATE_LIMIT_ENABLED", d.rate_limit_enabled),
        rate_limit_storage_uri=env_str("RATE_LIMIT_STORAGE_URI", d.rate_limit_storage_uri),
        rate_limit_default=env_str("RATE_LIMIT_DEFAULT", d.rate_limit_default),
        rate_limit_login=env_str("RATE_LIMIT_LOGIN", d.rate_limit_login),
        rate_limit_login_account=env_str("RATE_LIMIT_LOGIN_ACCOUNT", d.rate_limit_login_account),
        rate_limit_signup=env_str("RATE_LIMIT_SIGNUP", d.rate_limit_signup),
        rate_limit_upload=env_str("RATE_LIMIT_UPLOAD", d.rate_limit_upload),
        rate_limit_ai=env_str("RATE_LIMIT_AI", d.rate_limit_ai),
        rate_limit_access_code=env_str("RATE_LIMIT_ACCESS_CODE", d.rate_limit_access_code),
        trusted_proxy_ips=env_list("TRUSTED_PROXY_IPS", d.trusted_proxy_ips),
        log_level=env_str("LOG_LEVEL", d.log_level).upper(),
    )


def _without_paid_services(loaded: Settings) -> Settings:
    if not loaded.paid_services_disabled:
        return loaded
    return replace(loaded, openai_api_key="", groq_api_key="", gemini_api_key="", ocr_space_api_key="")


settings = _without_paid_services(load_settings())
