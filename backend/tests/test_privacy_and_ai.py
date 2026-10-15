"""Gemini provider, identifier removal and the number check (no request leaves the machine)."""

import json
from dataclasses import replace

import httpx
import pytest

from services import ai_client, report_ai_pipeline
from services.ai_client import AiResult, generate_text
from services.ai_guard import numbers_not_in_source
from services.privacy import REMOVED, redact_identifiers

KEY = "AIza-test-gemini-key"


# --- identifiers --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kept", "removed"),
    [
        ("Patient Name: Ayesha Testani | Age/Sex: 34 Y / F", "Age/Sex: 34 Y / F", "Ayesha"),
        ("Miss. Irha Rafiq  Age/Gender:23Y8M21D/F", "Age/Gender:23Y8M21D/F", "Irha"),
        ("MRN/PIN:K-4-43102/2609-01-29526E", "MRN/PIN:", "43102"),
        ("MR No: SYN-26134-42 | Referred By: Dr. Example Physician", "Dr. Example Physician", "SYN-26134"),
        ("CNIC/PP No: 12345-1234567-1", "CNIC/PP No:", "1234567"),
        ("Call 0300 1234567 or +92 321-7654321", "Call", "1234567"),
        ("Address: 12 Sample Road, Lahore", "Address:", "Sample Road"),
        ("Mrs. Sana Example Age 40", "Age 40", "Sana"),
    ],
)
def test_identifiers_are_removed_and_the_rest_kept(text, kept, removed):
    out = redact_identifiers(text)
    assert kept in out and removed not in out and REMOVED in out


@pytest.mark.parametrize(
    "text",
    [
        "Hemoglobin 10.8 g/dL. Platelets 230. Creatinine 1.1",
        "L4-L5 broad-based disc bulge",
        "The name of the test is CBC",
    ],
)
def test_medical_text_is_unchanged(text):
    assert redact_identifiers(text) == text


# --- number check -------------------------------------------------------------------------------

SOURCE = "Hemoglobin 9.5 g/dL (12 - 17.5). Platelet Count 2,31,000 /uL. Glucose 186 mg/dL."


def test_numbers_from_the_report_pass():
    summary = (
        "- Hemoglobin is 9.5 g/dL; the report range is 12 to 17.5.\n- Platelets 2,31,000.\n2 questions for your doctor."
    )
    assert numbers_not_in_source(summary, SOURCE) == []


@pytest.mark.parametrize(("summary", "invented"), [("Hemoglobin is 9.8 g/dL", "9.8"), ("Glucose 168 mg/dL", "168")])
def test_a_number_not_in_the_report_is_caught(summary, invented):
    assert numbers_not_in_source(summary, SOURCE) == [invented]


# --- Gemini provider ----------------------------------------------------------------------------


@pytest.fixture
def gemini(monkeypatch):
    """Gemini configured, every HTTP call answered by `handler` (set by the test)."""
    monkeypatch.setattr(ai_client, "settings", replace(ai_client.settings, ai_api_key=KEY))
    monkeypatch.setattr(ai_client, "MODELS", {**ai_client.MODELS, "gemini": "gemini-old-flash"})
    ai_client._gemini_model_override.clear()
    calls: list[httpx.Request] = []
    state = {"handler": None}

    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return state["handler"](request)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        ai_client.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(transport), **kw)
    )
    return state, calls


def answer(text: str) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


@pytest.mark.anyio
async def test_gemini_writes_the_text_and_never_sees_the_patient_name(gemini):
    state, calls = gemini
    state["handler"] = lambda request: answer("What this report is\nA blood test.")
    result = await generate_text("Explain simply.", "Patient Name: Ayesha Testani\nHemoglobin 9.5 g/dL")
    assert result.ok and result.provider == "gemini" and result.text.startswith("What this report is")
    sent = json.loads(calls[0].content)
    assert calls[0].headers["x-goog-api-key"] == KEY and KEY not in str(calls[0].url)  # key in a header, not the URL
    assert "Ayesha" not in json.dumps(sent) and "Hemoglobin 9.5 g/dL" in json.dumps(sent)
    assert sent["systemInstruction"]["parts"][0]["text"] == "Explain simply."


@pytest.mark.anyio
async def test_a_retired_model_is_replaced_by_the_newest_flash(gemini):
    state, calls = gemini

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
                    ]
                },
            )
        if "gemini-old-flash" in str(request.url):
            return httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})
        return answer("ok")

    state["handler"] = handler
    result = await generate_text("i", "p")
    assert result.text == "ok"
    assert "models/gemini-2.5-flash:generateContent" in str(calls[-1].url)


@pytest.mark.anyio
async def test_a_bad_key_is_an_error_that_does_not_repeat_the_key(gemini):
    state, _ = gemini
    state["handler"] = lambda request: httpx.Response(
        400, json={"error": {"status": "INVALID_ARGUMENT", "message": "API_KEY_INVALID"}}
    )
    result = await generate_text("i", "p")
    assert not result.ok and "authentication failed" in result.error and KEY not in result.error


# --- patient summary ----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_patient_summary_with_an_invented_number_is_not_shown(monkeypatch):
    async def fake_ai(**_):
        return AiResult(text="Your hemoglobin is 9.8 g/dL.", provider="gemini")

    monkeypatch.setattr(report_ai_pipeline, "generate_text", fake_ai)
    summary, warning, source = await report_ai_pipeline._generate_patient_summary(
        "Hemoglobin 9.5 g/dL", "Lab", {}, {"status": "CAUTION", "warnings": []}
    )
    assert source == "rule_based" and "9.8" not in summary and "not in the report" in warning


@pytest.mark.anyio
async def test_a_grounded_patient_summary_is_kept_with_its_source(monkeypatch):
    async def fake_ai(**_):
        return AiResult(text="Your hemoglobin is 9.5 g/dL.", provider="gemini")

    monkeypatch.setattr(report_ai_pipeline, "generate_text", fake_ai)
    summary, warning, source = await report_ai_pipeline._generate_patient_summary(
        "Hemoglobin 9.5 g/dL", "Lab", {}, {"status": "CAUTION", "warnings": []}
    )
    assert source == "gemini" and warning is None
    # The AI kept a medical word as it was; it gets its everyday wording, with the word in brackets.
    assert summary.startswith("Your oxygen-carrying blood protein (hemoglobin) is 9.5 g/dL.")
    assert "consult your doctor" in summary.lower()
