import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    OpenAI = None  # type: ignore[assignment]


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


@dataclass
class OpenAIResult:
    text: str | None = None
    data: Any = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and (self.text is not None or self.data is not None)


def configured_model() -> str:
    return os.getenv("OPENAI_SCAN_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL


def openai_unavailable_message() -> str | None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return "OpenAI API key is missing from the backend environment."
    if OpenAI is None:
        return "OpenAI Python SDK is not installed. Run backend dependency installation."
    return None


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
        return "OpenAI service is temporarily unavailable."
    return "OpenAI request failed. Try again later."


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

    def create_response():
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # type: ignore[misc]
        return client.responses.create(
            model=configured_model(),
            instructions=instructions,
            input=prompt,
            temperature=0.2,
        )

    try:
        response = await asyncio.to_thread(create_response)
        text = extract_response_text(response)
    except Exception as error:
        return OpenAIResult(error=safe_openai_error(error))

    if not text:
        return OpenAIResult(error="OpenAI returned an empty response.")

    return OpenAIResult(text=text)


async def generate_openai_json(instructions: str, prompt: str) -> OpenAIResult:
    result = await generate_openai_text(
        instructions=(
            f"{instructions}\n\nReturn valid JSON only. Do not wrap it in markdown fences."
        ),
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
    return f"OpenAI clinical AI was unavailable: {error} Generated using the local rule-based fallback."
