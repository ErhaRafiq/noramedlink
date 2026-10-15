"""AI key handling: provider by key prefix, request shape per provider, the no-key fallback (services/ai_client.py).

The autouse fixture in conftest.py blanks every key, so no test here reaches a provider.
"""

import json
from dataclasses import replace

import httpx
import pytest

from services import ai_client
from services.ai_client import fallback_notice, generate_json, generate_text, parse_json_from_text


@pytest.mark.anyio
async def test_without_keys_generation_returns_an_error_not_a_request():
    for generate in (generate_text, generate_json):
        result = await generate(instructions="i", prompt="p")
        assert not result.ok
        assert "AI_API_KEY" in result.error


def test_fallback_notice():
    assert fallback_notice(None) == ""
    assert "built by fixed rules" in fallback_notice("No key.")
    assert "key" not in fallback_notice("No API key configured.").lower()  # no developer detail for patients


@pytest.mark.parametrize(
    ("key", "provider"),
    [
        ("AIzaSyExample", "gemini"),
        ("sk-ant-api03-example", "anthropic"),
        ("sk-proj-example", "openai"),
        ("nonsense", None),
    ],
)
def test_the_provider_is_picked_from_the_key(key, provider):
    assert ai_client.provider_for(key) == provider


def test_an_unrecognised_key_is_refused_before_any_request(monkeypatch):
    monkeypatch.setattr(ai_client, "settings", replace(ai_client.settings, ai_api_key="nonsense"))
    assert "not a Gemini, OpenAI or Claude key" in ai_client.unavailable_message()


@pytest.fixture
def provider_api(monkeypatch):
    """Every HTTP call answered by `state["handler"]`; the requests are collected in `calls`."""
    calls: list[httpx.Request] = []
    state = {"handler": None}

    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return state["handler"](request)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        ai_client.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(transport), **kw)
    )

    def use(key: str):
        monkeypatch.setattr(ai_client, "settings", replace(ai_client.settings, ai_api_key=key))

    return state, calls, use


@pytest.mark.anyio
async def test_claude_is_called_with_its_own_headers_and_never_sees_the_patient_name(provider_api):
    state, calls, use = provider_api
    use("sk-ant-test-key")
    state["handler"] = lambda request: httpx.Response(
        200, json={"content": [{"type": "text", "text": "A blood test."}]}
    )
    result = await generate_text("Explain simply.", "Patient Name: Ayesha Testani | Hemoglobin 9.5 g/dL")
    assert result.ok and result.provider == "anthropic" and result.text == "A blood test."
    sent = json.loads(calls[0].content)
    assert calls[0].headers["x-api-key"] == "sk-ant-test-key" and "anthropic-version" in calls[0].headers
    assert sent["system"] == "Explain simply." and "Ayesha" not in json.dumps(sent)


@pytest.mark.anyio
async def test_openai_is_called_with_a_bearer_key(provider_api):
    state, calls, use = provider_api
    use("sk-test-key")
    state["handler"] = lambda request: httpx.Response(
        200, json={"choices": [{"message": {"content": "A blood test."}}]}
    )
    result = await generate_text("i", "p")
    assert result.ok and result.provider == "openai"
    assert calls[0].headers["authorization"] == "Bearer sk-test-key"


@pytest.mark.anyio
async def test_a_rejected_key_gives_a_plain_error_without_the_key(provider_api):
    state, _, use = provider_api
    use("sk-ant-test-key")
    state["handler"] = lambda request: httpx.Response(401, json={"error": {"message": "invalid x-api-key"}})
    result = await generate_text("i", "p")
    assert not result.ok and "authentication failed" in result.error and "sk-ant-test-key" not in result.error


@pytest.mark.parametrize(
    "text",
    ['{"status": "ok"}', '```json\n{"status": "ok"}\n```', 'Here you go: {"status": "ok"} thanks'],
)
def test_json_is_found_in_model_text(text):
    assert parse_json_from_text(text) == {"status": "ok"}


def test_unparseable_model_text_raises():
    with pytest.raises(ValueError):
        parse_json_from_text("no json here")
