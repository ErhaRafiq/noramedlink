"""Settings parsing (config.py)."""

import pytest

from config import Settings, env_bool, env_str, load_settings

NAME = "NORA_UNIT_TEST_VALUE"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(NAME, raising=False)


def test_unset_and_blank_values_use_the_default(monkeypatch):
    assert env_str(NAME, "fallback") == "fallback"
    monkeypatch.setenv(NAME, "   ")
    assert env_str(NAME, "fallback") == "fallback"


def test_values_are_trimmed(monkeypatch):
    monkeypatch.setenv(NAME, "  value  ")
    assert env_str(NAME) == "value"


def test_quotes_are_stripped_only_when_asked(monkeypatch):
    monkeypatch.setenv(NAME, '"quoted"')
    assert env_str(NAME) == '"quoted"'
    assert env_str(NAME, strip_quotes=True) == "quoted"


@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [
        ("true", False, True),
        ("YES", False, True),
        ("1", False, True),
        ("on", False, True),
        ("false", True, False),
        ("Off", True, False),
        ("0", True, False),
        ("maybe", True, True),
        ("maybe", False, False),
    ],
)
def test_booleans(monkeypatch, raw, default, expected):
    monkeypatch.setenv(NAME, raw)
    assert env_bool(NAME, default) is expected


def test_load_settings_reads_only_what_differs_between_machines(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "'sqlite:///x.db'")
    monkeypatch.setenv("BIOBERT_ENABLED", "0")
    monkeypatch.setenv("RATE_LIMIT_AI", "3/minute")  # no longer an environment variable: ignored
    loaded = load_settings()
    assert loaded.database_url == "sqlite:///x.db"
    assert loaded.biobert_enabled is False
    assert loaded.rate_limit_ai == Settings().rate_limit_ai


def test_render_style_postgres_urls_are_accepted(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pw@db.internal:5432/nora")
    assert load_settings().database_url == "postgresql://user:pw@db.internal:5432/nora"


def test_defaults():
    defaults = Settings()
    assert defaults.rate_limit_default == "200/minute"
    assert defaults.rate_limit_login_account == "5/minute"
    assert defaults.max_upload_mb == 10
    assert defaults.access_token_expire_minutes == 1440
    assert defaults.trusted_proxy_ips == ["127.0.0.1", "::1"]


@pytest.mark.parametrize("switch", ["1", "true"])
def test_disable_paid_services_ignores_every_ai_and_stripe_key(monkeypatch, switch):
    from config import _without_paid_services

    for name in ("AI_API_KEY", "STRIPE_SECRET_KEY"):
        monkeypatch.setenv(name, "test-placeholder-key")
    monkeypatch.setenv("DISABLE_PAID_SERVICES", switch)
    loaded = _without_paid_services(load_settings())
    assert loaded.paid_services_disabled
    assert not (loaded.ai_api_key or loaded.stripe_secret_key)


def test_keys_are_kept_without_the_switch(monkeypatch):
    from config import _without_paid_services

    monkeypatch.setenv("AI_API_KEY", "test-placeholder-key")
    monkeypatch.delenv("DISABLE_PAID_SERVICES", raising=False)
    assert _without_paid_services(load_settings()).ai_api_key == "test-placeholder-key"
