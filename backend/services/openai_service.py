import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    OpenAI = None  # type: ignore[assignment]

import contextlib

import httpx

from config import settings
from services.privacy import redact_identifiers

logger = logging.getLogger("nora.ai")

OPENAI_BASE_URL = "https://api.openai.com/v1"


@dataclass
class OpenAIResult:
    text: str | None = None
    data: Any = None
    error: str | None = None
    provider: str | None = None  # "gemini" or "openai": which model wrote the text

    @property
    def ok(self) -> bool:
        return self.error is None and (self.text is not None or self.data is not None)


def configured_model() -> str:
    return settings.openai_scan_model


def configured_openai_models() -> list[str]:
    primary = configured_model()
    return list(dict.fromkeys([primary, *settings.openai_fallback_models]))


def _has_openai_provider() -> bool:
    return bool(settings.openai_api_key)


def _has_gemini_provider() -> bool:
    return bool(settings.gemini_api_key)


def openai_unavailable_message() -> str | None:
    if _has_gemini_provider():
        return None  # Gemini is called over HTTPS; it does not need the OpenAI SDK
    if OpenAI is None:
        return "OpenAI Python SDK is not installed. Run backend dependency installation."
    if _has_openai_provider():
        return None
    return "No LLM API key configured. Add GEMINI_API_KEY or OPENAI_API_KEY to .env."


def safe_openai_error(error: Exception) -> str:
    status_code = getattr(error, "status_code", None)
    error_name = error.__class__.__name__.lower()
    message = str(error).lower()

    if status_code == 401 or "authentication" in error_name:
        return "AI provider authentication failed. Check the backend API key."
    if status_code == 429 or "ratelimit" in error_name or "quota" in message:
        return "AI provider quota or rate limit was reached. Try again later."
    if "timeout" in error_name or "connection" in error_name:
        return "AI request failed due to a network or timeout issue."
    if isinstance(status_code, int) and status_code >= 500:
        return "LLM service is temporarily unavailable."
    return "LLM request failed. Try again later."


def is_retryable_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    message = str(error).lower()
    error_name = error.__class__.__name__.lower()
    return bool(
        status_code in {408, 409, 425, 429, 500, 502, 503, 504}
        or "ratelimit" in error_name
        or "quota" in message
        or "timeout" in error_name
        or "temporarily unavailable" in message
        or "connection" in error_name
    )


def _provider_attempts() -> list[tuple[str, str, str]]:
    attempts: list[tuple[str, str, str]] = []
    if _has_gemini_provider():  # first when its key is set
        for model in dict.fromkeys([settings.gemini_model, *settings.gemini_fallback_models]):
            attempts.append(("gemini", model, settings.gemini_base_url))
    if _has_openai_provider():
        for model in configured_openai_models():
            attempts.append(("openai", model, OPENAI_BASE_URL))
    return attempts


def extract_chat_completion_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices and isinstance(response, dict):
        choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, dict):
        message = first.get("message")
    content = getattr(message, "content", None) if message is not None else None
    if content is None and isinstance(message, dict):
        content = message.get("content")
    return str(content or "").strip()


def parse_json_from_text(text: str) -> Any:
    candidates = [text.strip()]
    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start != -1 and object_end > object_start:
        candidates.append(text[object_start : object_end + 1])

    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start != -1 and array_end > array_start:
        candidates.append(text[array_start : array_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError("OpenAI returned non-JSON output.")


async def generate_openai_text(instructions: str, prompt: str) -> OpenAIResult:
    unavailable = openai_unavailable_message()
    if unavailable:
        return OpenAIResult(error=unavailable)

    attempts = _provider_attempts()
    if not attempts:
        return OpenAIResult(error="No LLM provider configured. Add GEMINI_API_KEY or OPENAI_API_KEY.")

    # Every prompt leaves the server: patient identifiers are removed first (services/privacy.py).
    prompt = redact_identifiers(prompt)

    errors: list[str] = []
    for provider, model, base_url in attempts:
        if provider == "gemini":
            try:
                text = await _gemini_generate(model, base_url, instructions, prompt)
                if text:
                    return OpenAIResult(text=text, provider="gemini")
                errors.append(f"gemini:{model} returned empty output")
            except Exception as error:
                errors.append(f"gemini:{model} {safe_openai_error(error)}")
            continue

        api_key = settings.openai_api_key

        # Bind this attempt's values now, so the closure never sees a later iteration's.
        def create_response(api_key=api_key, base_url=base_url, model=model):
            client = OpenAI(api_key=api_key, base_url=base_url)  # type: ignore[misc]
            return client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt},
                ],
            )

        try:
            response = await asyncio.to_thread(create_response)
            text = extract_chat_completion_text(response)
            if text:
                return OpenAIResult(text=text, provider=provider)
            errors.append(f"{provider}:{model} returned empty output")
        except Exception as error:
            errors.append(f"{provider}:{model} {safe_openai_error(error)}")
            if not is_retryable_error(error):
                continue

    if errors:
        return OpenAIResult(error="; ".join(errors[:3]))
    return OpenAIResult(error="All configured LLM models failed to generate a response.")


class GeminiError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


# A model name that Google has retired is replaced by the newest available "flash" model,
# found once through the ListModels endpoint and remembered for this process.
_gemini_model_override: dict[str, str] = {}


async def _gemini_generate(model: str, base_url: str, instructions: str, prompt: str) -> str:
    model = _gemini_model_override.get(model, model)
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{base_url}/models/{model}:generateContent",
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": instructions}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
            },
        )
        if response.status_code == 404 and model not in _gemini_model_override.values():
            replacement = await _newest_gemini_flash(client, base_url)
            if replacement and replacement != model:
                logger.warning("Gemini model %s is not available; using %s instead.", model, replacement)
                _gemini_model_override[model] = replacement
                return await _gemini_generate(replacement, base_url, instructions, prompt)
    if response.status_code >= 400:
        detail = ""
        with contextlib.suppress(ValueError):
            detail = response.json().get("error", {}).get("status", "")
        status = 401 if response.status_code in {400, 403} and "API_KEY" in response.text else response.status_code
        raise GeminiError(f"Gemini request failed ({response.status_code} {detail})".strip(), status)
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()


async def _newest_gemini_flash(client: httpx.AsyncClient, base_url: str) -> str | None:
    response = await client.get(
        f"{base_url}/models", params={"pageSize": 200}, headers={"x-goog-api-key": settings.gemini_api_key}
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


async def generate_openai_json(instructions: str, prompt: str) -> OpenAIResult:
    result = await generate_openai_text(
        instructions=(f"{instructions}\n\nReturn valid JSON only. Do not wrap it in markdown fences."),
        prompt=prompt,
    )
    if not result.text:
        return result

    try:
        return OpenAIResult(text=result.text, data=parse_json_from_text(result.text), provider=result.provider)
    except ValueError:
        return OpenAIResult(error="OpenAI returned an invalid response format.")


def fallback_notice(error: str | None) -> str:
    """Plain-language note for patients; the technical reason goes to the server log only."""
    if not error:
        return ""
    logger.info("AI text unavailable, rule-based fallback used: %s", error)
    return "The AI summary is not available right now, so this text was built by fixed rules."
