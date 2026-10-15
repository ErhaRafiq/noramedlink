"""Shared fixtures for the backend unit tests.

These tests never touch the database or the network. AI provider keys are blanked for
every test, so nothing can reach Gemini, OpenAI, Groq, OCR.space, openFDA or Stripe (AGENTS.md section 10).
"""

import os
from dataclasses import replace

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import pytest

from config import settings
from services import ocr_space_service, openai_service, payments
from services.mscie import openfda

NO_EXTERNAL_KEYS = replace(
    settings,
    openai_api_key="",
    groq_api_key="",
    gemini_api_key="",
    ocr_space_api_key="",
    stripe_secret_key="",
    stripe_webhook_secret="",
    paid_services_disabled=True,
)


@pytest.fixture
def anyio_backend() -> str:
    """Async tests (marked anyio) run on asyncio."""
    return "asyncio"


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_service, "settings", NO_EXTERNAL_KEYS)
    monkeypatch.setattr(ocr_space_service, "settings", NO_EXTERNAL_KEYS)
    monkeypatch.setattr(openfda, "settings", NO_EXTERNAL_KEYS)  # no openFDA lookups
    monkeypatch.setattr(payments, "settings", NO_EXTERNAL_KEYS)  # no Stripe calls
