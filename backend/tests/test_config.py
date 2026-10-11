"""Settings parsing (config.py)."""

import pytest

from config import Settings, env_bool, env_float, env_int, env_list, env_str, load_settings

NAME = "NORA_UNIT_TEST_VALUE"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(NAME, raising=False)


def test_unset_and_blank_values_use_the_default(monkeypatch):
    assert env_str(NAME, "fallback") == "fallback"
    monkeypatch.setenv(NAME, "   ")
    assert env_str(NAME, "fallback") == "fallback"
    assert env_int(NAME, 7) == 7
    assert env_float(NAME, 1.5) == 1.5


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


def test_lists_split_on_commas_and_drop_blanks(monkeypatch):
    monkeypatch.setenv(NAME, " a, b ,,c ")
    assert env_list(NAME) == ["a", "b", "c"]
    monkeypatch.setenv(NAME, " , ")
    assert env_list(NAME, ["x"]) == ["x"]


def test_invalid_number_fails_loudly(monkeypatch):
    monkeypatch.setenv(NAME, "ten")
    with pytest.raises(ValueError):
        env_int(NAME, 10)


def test_load_settings_reads_the_environment(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AI", "3/minute")
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.1, 10.0.0.2")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("FASTAPI_DATABASE_URL", "")
    monkeypatch.setenv("DATABASE_URL", "'sqlite:///x.db'")
    loaded = load_settings()
    assert loaded.rate_limit_ai == "3/minute"
    assert loaded.trusted_proxy_ips == ["10.0.0.1", "10.0.0.2"]
    assert loaded.log_level == "DEBUG"
    assert loaded.database_url == "sqlite:///x.db"


def test_jwt_secret_falls_back_through_the_old_names(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setenv("NORA_JWT_SECRET", "third-name")
    assert load_settings().jwt_secret == "third-name"


def test_defaults():
    defaults = Settings()
    assert defaults.rate_limit_default == "200/minute"
    assert defaults.rate_limit_login_account == "5/minute"
    assert defaults.max_upload_mb == 10
    assert defaults.access_token_expire_minutes == 1440
    assert defaults.trusted_proxy_ips == ["127.0.0.1", "::1"]
