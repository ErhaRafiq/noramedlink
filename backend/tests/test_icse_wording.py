"""AI wording of the clinical summary's key findings: facts only, numbers checked, never a flag."""

from datetime import date

import pytest

from services.ai_client import AiResult
from services.icse import wording
from services.icse.entities import extract_entities
from services.icse.flags import printed_date
from services.icse.summary import build_content
from services.privacy import identity_patterns

IDENTITY = identity_patterns("Ayesha Exampli", "0300-1234567", "12345-1234567-1")


def content():
    text = "Collected: 01-Mar-2026\nCreatinine 2.1 mg/dL\nK/C/O HTN\nTab Warfarin 5 mg OD"
    entities = extract_entities(text)
    source = {"report_id": 1, "title": "Ayesha Exampli kidney panel", "kind": "report",
              "date": printed_date(entities), "date_source": "printed in report", "entities": entities}  # fmt: skip
    return build_content([source], [], [], date(2026, 10, 15))


def stub(monkeypatch, text=None, error=None, provider="gemini"):
    prompts = []

    async def fake(instructions, prompt):
        prompts.append(prompt)
        return AiResult(text=text, error=error, provider=provider if text else None)

    monkeypatch.setattr(wording, "generate_text", fake)
    return prompts


@pytest.mark.anyio
async def test_a_grounded_paragraph_is_used(monkeypatch):
    stub(monkeypatch, "Creatinine 2.1 mg/dL is over 1.3 mg/dL. Hypertension is mentioned; warfarin is listed.")
    text, provider, why = await wording.reword_key_findings(content(), IDENTITY)
    assert text.startswith("Creatinine 2.1 mg/dL") and provider == "gemini" and why is None


@pytest.mark.anyio
async def test_a_paragraph_with_a_number_not_in_the_facts_is_rejected(monkeypatch):
    stub(monkeypatch, "Creatinine 3.4 mg/dL is high.")
    text, provider, why = await wording.reword_key_findings(content(), IDENTITY)
    assert text is None and provider is None and "numbers that are not in the summary" in why


@pytest.mark.anyio
@pytest.mark.parametrize("error", ["no AI key configured", "Gemini request failed"])
async def test_without_an_ai_the_rule_built_sentence_stays(monkeypatch, error):
    stub(monkeypatch, error=error)
    text, _provider, why = await wording.reword_key_findings(content(), IDENTITY)
    assert text is None and why == error


@pytest.mark.anyio
async def test_the_prompt_has_the_facts_but_no_titles_or_identity(monkeypatch):
    prompts = stub(monkeypatch, "Creatinine 2.1 mg/dL is over 1.3 mg/dL.")
    await wording.reword_key_findings(content(), IDENTITY)
    assert "Creatinine 2.1 mg/dL" in prompts[0] and "warfarin" in prompts[0]
    assert "Ayesha" not in prompts[0] and "kidney panel" not in prompts[0]


def test_the_facts_carry_every_severity_from_the_rules():
    lines = wording.facts(content()).splitlines()
    assert any(line.startswith("- [CAUTION] Creatinine 2.1 mg/dL") for line in lines)
