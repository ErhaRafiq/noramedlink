"""LLM provider selection and the no-key fallback (services/openai_service.py).

The autouse fixture in conftest.py blanks every key, so no test here reaches a provider.
"""

from dataclasses import replace

import pytest

from services import openai_service
from services.openai_service import fallback_notice, generate_openai_json, generate_openai_text, parse_json_from_text


@pytest.mark.anyio
async def test_without_keys_generation_returns_an_error_not_a_request():
    for generate in (generate_openai_text, generate_openai_json):
        result = await generate(instructions="i", prompt="p")
        assert not result.ok
        assert "API key" in result.error or "provider" in result.error


def test_fallback_notice():
    assert fallback_notice(None) == ""
    assert "built by fixed rules" in fallback_notice("No key.")
    assert "key" not in fallback_notice("No API key configured.").lower()  # no developer detail for patients


def test_provider_order_and_model_dedupe(monkeypatch: pytest.MonkeyPatch):
    configured = replace(
        openai_service.settings,
        gemini_api_key="test-gemini",
        gemini_model="gemini-a",
        openai_api_key="test-openai",
        openai_scan_model="model-a",
        openai_fallback_models=["model-b", "model-a"],
    )
    monkeypatch.setattr(openai_service, "settings", configured)
    attempts = openai_service._provider_attempts()
    assert [(provider, model) for provider, model, _ in attempts] == [
        ("gemini", "gemini-a"),
        ("openai", "model-a"),
        ("openai", "model-b"),
    ]


@pytest.mark.parametrize(
    "text",
    ['{"status": "ok"}', '```json\n{"status": "ok"}\n```', 'Here you go: {"status": "ok"} thanks'],
)
def test_json_is_found_in_model_text(text):
    assert parse_json_from_text(text) == {"status": "ok"}


def test_unparseable_model_text_raises():
    with pytest.raises(ValueError):
        parse_json_from_text("no json here")
