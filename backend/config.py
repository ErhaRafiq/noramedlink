"""Backend settings, read once from the environment.

Only what differs between machines comes from the environment (the project-root .env.example
lists it all): the database, secrets and keys, the website's address and two switches. Everything
else is a fixed default below, changed in code, not in .env.

One .env file for the whole project: the project-root .env. Variables already set in the
environment win over it (on Render they come from the dashboard; there is no .env there).
A blank value counts as unset and falls back to the default.
"""

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def env_str(name: str, default: str = "", *, strip_quotes: bool = False) -> str:
    value = (os.getenv(name) or "").strip()
    if strip_quotes:
        value = value.strip('"').strip("'")
    return value or default


def env_bool(name: str, default: bool) -> bool:
    value = env_str(name).lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


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
    access_token_expire_minutes: int = 15  # short; the refresh token (services/sessions.py) renews it
    admin_invite_code: str = ""
    frontend_origin: str = "http://localhost:3000"

    # AI: one key. DISABLE_PAID_SERVICES=1 (test runs) ignores every AI
    # and Stripe key, so tests never call an outside service even when .env has keys.
    paid_services_disabled: bool = False
    ai_api_key: str = ""  # one key: Gemini, OpenAI or Claude (services/ai_client.py picks by prefix)
    biobert_enabled: bool = True  # off on small hosts: BioBERT needs about 1 GB of memory
    biobert_model: str = "d4data/biomedical-ner-all"

    # Local OCR (services/local_ocr.py)
    ocr_model_dir: str = "models"  # model cache, relative to backend/

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
    rate_limit_payment: str = "10/minute"
    rate_limit_symptoms: str = "20/minute"  # per IP: the public symptom checker
    rate_limit_pmdc: str = "20/minute"  # per admin: lookups on the PMDC public register
    trusted_proxy_ips: list[str] = field(default_factory=lambda: ["127.0.0.1", "::1"])

    # Payments (Stripe Checkout, the hosted payment page). Test keys (sk_test_...) take no real money.
    stripe_secret_key: str = ""  # empty: online payment is off (checkout answers 503)
    stripe_webhook_secret: str = ""  # whsec_...: verifies that webhook calls come from Stripe
    payment_currency: str = "pkr"

    # PMDC register lookup (admin doctor verification). The same free public search the PMDC website uses.
    # Only the registration number is sent. Off in test runs (DISABLE_PAID_SERVICES) like every outside call.
    pmdc_lookup_enabled: bool = True
    pmdc_lookup_url: str = "https://hospitals-inspections.pmdc.pk/api/DRC/GetData"
    pmdc_lookup_timeout: float = 10.0  # seconds

    # Logging
    log_level: str = "INFO"


def database_url(url: str) -> str:
    """Hosts such as Render hand out postgres://; SQLAlchemy only accepts postgresql://."""
    return "postgresql://" + url[len("postgres://") :] if url.startswith("postgres://") else url


def load_settings() -> Settings:
    return Settings(
        database_url=database_url(env_str("DATABASE_URL", strip_quotes=True)),
        jwt_secret=env_str("JWT_SECRET_KEY"),
        admin_invite_code=env_str("ADMIN_INVITE_CODE"),
        frontend_origin=env_str("FRONTEND_ORIGIN", Settings.frontend_origin),
        paid_services_disabled=env_bool("DISABLE_PAID_SERVICES", False),
        ai_api_key=env_str("AI_API_KEY"),
        biobert_enabled=env_bool("BIOBERT_ENABLED", True),
        stripe_secret_key=env_str("STRIPE_SECRET_KEY", strip_quotes=True),
        stripe_webhook_secret=env_str("STRIPE_WEBHOOK_SECRET", strip_quotes=True),
        pmdc_lookup_enabled=env_bool("PMDC_LOOKUP_ENABLED", True),
        pmdc_lookup_url=env_str("PMDC_LOOKUP_URL", Settings.pmdc_lookup_url),
    )


def _without_paid_services(loaded: Settings) -> Settings:
    if not loaded.paid_services_disabled:
        return loaded
    return replace(loaded, ai_api_key="", stripe_secret_key="", pmdc_lookup_enabled=False)


settings = _without_paid_services(load_settings())
