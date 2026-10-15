"""One AI key for the whole app: Gemini, OpenAI or Claude, picked from the key itself.

AI_API_KEY holds any one key; its prefix says which provider it is (AIza... Gemini, sk-ant-...
Claude, sk-... OpenAI). Without a key the app uses its fixed rules. Every prompt leaves the server,
so patient identifiers are removed first (services/privacy.py). Plain HTTPS calls, no vendor SDK.
"""

import contextlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from config import settings
from services.privacy import redact_identifiers

logger = logging.getLogger("nora.ai")

MODELS = {"gemini": "gemini-2.5-flash", "openai": "gpt-4.1-mini", "anthropic": "claude-haiku-4-5-20251001"}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
TIMEOUT_SECONDS = 90


@dataclass
class AiResult:
    text: str | None = None
    data: Any = None
    error: str | None = None
    provider: str | None = None  # "gemini", "openai" or "anthropic": which model wrote the text

    @property
    def ok(self) -> bool:
        return self.error is None and (self.text is not None or self.data is not None)


class AiError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def provider_for(key: str) -> str | None:
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("AIza"):
        return "gemini"
    if key.startswith("sk-"):
        return "openai"
    return None


def unavailable_message() -> str | None:
    key = settings.ai_api_key
    if not key:
        return "No AI key configured. Add AI_API_KEY to .env."
    if provider_for(key) is None:
        return "AI_API_KEY is not a Gemini, OpenAI or Claude key."
    return None


def safe_error(error: Exception) -> str:
    status_code = getattr(error, "status_code", None)
    name = error.__class__.__name__.lower()
    if status_code in {401, 403}:
        return "AI provider authentication failed. Check AI_API_KEY."
    if status_code == 429:
        return "AI provider quota or rate limit was reached. Try again later."
    if "timeout" in name or "connect" in name:
        return "AI request failed due to a network or timeout issue."
    if isinstance(status_code, int) and status_code >= 500:
        return "The AI service is temporarily unavailable."
    return "AI request failed. Try again later."


def parse_json_from_text(text: str) -> Any:
    candidates = [text.strip()]
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])
    for candidate in candidates:
        with contextlib.suppress(json.JSONDecodeError):
            return json.loads(candidate)
    raise ValueError("The AI returned non-JSON output.")


def _check(response: httpx.Response, name: str) -> None:
    if response.status_code >= 400:
        status = (
            401
            if response.status_code in {400, 403} and "api" in response.text.lower() and "key" in response.text.lower()
            else response.status_code
        )
        raise AiError(f"{name} request failed ({response.status_code})", status)


# A Gemini model name that Google has retired is replaced by the newest available "flash" model,
# found once through the ListModels endpoint and remembered for this process.
_gemini_model_override: dict[str, str] = {}


async def _newest_gemini_flash(client: httpx.AsyncClient) -> str | None:
    response = await client.get(
        f"{GEMINI_URL}/models", params={"pageSize": 200}, headers={"x-goog-api-key": settings.ai_api_key}
    )
    if response.status_code != 200:
        return None
    versions = []
    for item in response.json().get("models", []):
        name = str(item.get("name", "")).removeprefix("models/")
        match = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash", name)
        if match and "generateContent" in item.get("supportedGenerationMethods", []):
            versions.append((float(match.group(1)), name))
    return max(versions)[1] if versions else None


async def _gemini(instructions: str, prompt: str, model: str | None = None) -> str:
    model = _gemini_model_override.get(model or MODELS["gemini"], model or MODELS["gemini"])
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{GEMINI_URL}/models/{model}:generateContent",
            headers={"x-goog-api-key": settings.ai_api_key},
            json={
                "systemInstruction": {"parts": [{"text": instructions}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
            },
        )
        if response.status_code == 404 and model not in _gemini_model_override.values():
            replacement = await _newest_gemini_flash(client)
            if replacement and replacement != model:
                logger.warning("Gemini model %s is not available; using %s instead.", model, replacement)
                _gemini_model_override[model] = replacement
                return await _gemini(instructions, prompt, replacement)
    _check(response, "Gemini")
    candidates = response.json().get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()


async def _openai(instructions: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            json={
                "model": MODELS["openai"],
                "temperature": 0.2,
                "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}],
            },
        )
    _check(response, "OpenAI")
    choices = response.json().get("choices") or []
    return str(((choices[0].get("message") or {}).get("content") if choices else "") or "").strip()


async def _anthropic(instructions: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(
            ANTHROPIC_URL,
            headers={"x-api-key": settings.ai_api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": MODELS["anthropic"],
                "max_tokens": 4096,
                "temperature": 0.2,
                "system": instructions,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    _check(response, "Claude")
    blocks = response.json().get("content") or []
    return "".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()


_CALLS = {"gemini": _gemini, "openai": _openai, "anthropic": _anthropic}


async def generate_text(instructions: str, prompt: str) -> AiResult:
    unavailable = unavailable_message()
    if unavailable:
        return AiResult(error=unavailable)
    provider = provider_for(settings.ai_api_key)
    # Every prompt leaves the server: patient identifiers are removed first (services/privacy.py).
    prompt = redact_identifiers(prompt)
    try:
        text = await _CALLS[provider](instructions, prompt)
    except Exception as error:
        return AiResult(error=f"{provider} {safe_error(error)}")
    if not text:
        return AiResult(error=f"{provider} returned empty output")
    return AiResult(text=text, provider=provider)


async def generate_json(instructions: str, prompt: str) -> AiResult:
    result = await generate_text(
        instructions=f"{instructions}\n\nReturn valid JSON only. Do not wrap it in markdown fences.", prompt=prompt
    )
    if not result.text:
        return result
    try:
        return AiResult(text=result.text, data=parse_json_from_text(result.text), provider=result.provider)
    except ValueError:
        return AiResult(error="The AI returned an invalid response format.")


def fallback_notice(error: str | None) -> str:
    """Plain-language note for patients; the technical reason goes to the server log only."""
    if not error:
        return ""
    logger.info("AI text unavailable, rule-based fallback used: %s", error)
    return "The AI summary is not available right now, so this text was built by fixed rules."
