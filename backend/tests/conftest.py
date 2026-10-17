"""Shared fixtures for the backend unit tests.

These tests never touch the database or the network. AI provider keys are blanked for
every test, so nothing can reach Gemini, OpenAI, openFDA or Stripe (AGENTS.md section 10).
"""

import os
from dataclasses import replace

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import pytest

from config import settings
from services import ai_client, payments, pmdc
from services.mscie import openfda

NO_EXTERNAL_KEYS = replace(
    settings,
    ai_api_key="",
    stripe_secret_key="",
    stripe_webhook_secret="",
    paid_services_disabled=True,
    pmdc_lookup_enabled=False,
)


@pytest.fixture
def anyio_backend() -> str:
    """Async tests (marked anyio) run on asyncio."""
    return "asyncio"


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_client, "settings", NO_EXTERNAL_KEYS)
    monkeypatch.setattr(openfda, "settings", NO_EXTERNAL_KEYS)  # no openFDA lookups
    monkeypatch.setattr(payments, "settings", NO_EXTERNAL_KEYS)  # no Stripe calls
    monkeypatch.setattr(pmdc, "settings", NO_EXTERNAL_KEYS)  # no PMDC register lookups
