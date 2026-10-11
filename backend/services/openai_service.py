import asyncio
import json
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    OpenAI = None  # type: ignore[assignment]

from config import settings

OPENAI_BASE_URL = "https://api.openai.com/v1"


@dataclass
class OpenAIResult:
    text: str | None = None
    data: Any = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and (self.text is not None or self.data is not None)


def configured_model() -> str:
    return settings.openai_scan_model


def configured_openai_models() -> list[str]:
    primary = configured_model()
    return list(dict.fromkeys([primary, *settings.openai_fallback_models]))


def configured_groq_models() -> list[str]:
    return list(settings.groq_chat_models)


def _has_openai_provider() -> bool:
    return bool(settings.openai_api_key)


def _has_groq_provider() -> bool:
    return bool(settings.groq_api_key)


def openai_unavailable_message() -> str | None:
    if OpenAI is None:
        return "OpenAI Python SDK is not installed. Run backend dependency installation."
    if _has_openai_provider() or _has_groq_provider():
        return None
    return "No LLM API key configured. Add OPENAI_API_KEY or GROQ_API_KEY to the backend environment."


def safe_openai_error(error: Exception) -> str:
    status_code = getattr(error, "status_code", None)
    error_name = error.__class__.__name__.lower()
    message = str(error).lower()

    if status_code == 401 or "authentication" in error_name:
        return "OpenAI API authentication failed. Check the backend API key."
    if status_code == 429 or "ratelimit" in error_name or "quota" in message:
        return "OpenAI quota or rate limit was reached. Try again later."
    if "timeout" in error_name or "connection" in error_name:
        return "OpenAI request failed due to a network or timeout issue."
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
    if _has_openai_provider():
        for model in configured_openai_models():
            attempts.append(("openai", model, OPENAI_BASE_URL))
    if _has_groq_provider():
        for model in configured_groq_models():
            attempts.append(("groq", model, settings.groq_base_url))
    return attempts


def extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    payload: dict[str, Any]
    if hasattr(response, "model_dump"):
        payload = response.model_dump()
    elif isinstance(response, dict):
        payload = response
    else:
        payload = {}

    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

    return "\n".join(parts).strip()


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
        return OpenAIResult(error="No LLM provider configured. Add OPENAI_API_KEY or GROQ_API_KEY.")

    errors: list[str] = []
    for provider, model, base_url in attempts:
        api_key = settings.openai_api_key if provider == "openai" else settings.groq_api_key

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
                return OpenAIResult(text=text)
            errors.append(f"{provider}:{model} returned empty output")
        except Exception as error:
            errors.append(f"{provider}:{model} {safe_openai_error(error)}")
            if not is_retryable_error(error):
                continue

    if errors:
        return OpenAIResult(error="; ".join(errors[:3]))
    return OpenAIResult(error="All configured LLM models failed to generate a response.")


async def generate_openai_json(instructions: str, prompt: str) -> OpenAIResult:
    result = await generate_openai_text(
        instructions=(f"{instructions}\n\nReturn valid JSON only. Do not wrap it in markdown fences."),
        prompt=prompt,
    )
    if not result.text:
        return result

    try:
        return OpenAIResult(text=result.text, data=parse_json_from_text(result.text))
    except ValueError:
        return OpenAIResult(error="OpenAI returned an invalid response format.")


def fallback_notice(error: str | None) -> str:
    if not error:
        return ""
    return f"Clinical AI was unavailable: {error} Generated using the local rule-based fallback."
