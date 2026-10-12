"""POST /patient/medicine-safety/check: the AI explains but never changes the status (AGENTS.md 6.2).

The database and the LLM are replaced with stubs, so this runs without either.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from database import get_db
from dependencies import require_patient
from main import app
from routers import patient_medicines
from services.openai_service import OpenAIResult

URL = "/patient/medicine-safety/check"


class EmptyQuery:
    def order_by(self, *_):
        return self

    def all(self):
        return []


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(patient_medicines, "get_patient_profile", lambda db, user: SimpleNamespace(user_id=user.id))
    monkeypatch.setattr(patient_medicines, "patient_medicine_query", lambda db, profile: EmptyQuery())
    app.dependency_overrides[require_patient] = lambda: SimpleNamespace(id=1, role="patient")
    app.dependency_overrides[get_db] = lambda: None
    try:
        yield TestClient(app)  # no `with`: startup (migrations) does not run
    finally:
        app.dependency_overrides.clear()


def ai_returns(monkeypatch: pytest.MonkeyPatch, result: OpenAIResult) -> None:
    async def fake_generate(**_):
        return result

    monkeypatch.setattr(patient_medicines, "generate_openai_json", fake_generate)


@pytest.mark.parametrize("ai_status", ["High Risk", "Safe", "Caution"])
def test_ai_status_is_ignored(client, monkeypatch, ai_status):
    ai_returns(
        monkeypatch, OpenAIResult(data={"status": ai_status, "reason": "Model view.", "warnings": ["Ask a GP."]})
    )
    body = client.post(URL, json={"medicine_name": "Paracetamol"}).json()
    assert body["status"] == "No data"


def test_ai_cannot_lower_a_rule_status(client, monkeypatch):
    ai_returns(monkeypatch, OpenAIResult(data={"status": "Safe", "reason": "Fine.", "warnings": []}))
    body = client.post(URL, json={"medicine_name": "Penicillin", "known_allergies": "penicillin"}).json()
    assert body["status"] == "High Risk"


def test_ai_text_is_labelled(client, monkeypatch):
    ai_returns(monkeypatch, OpenAIResult(data={"reason": "Model view.", "warnings": ["Ask a GP."]}))
    body = client.post(URL, json={"medicine_name": "Paracetamol"}).json()
    assert "AI observation: Ask a GP." in body["warnings"]
    assert "AI-generated explanation (advisory, verify with a clinician): Model view." in body["reason"]


def test_without_ai_the_rules_still_answer(client, monkeypatch):
    ai_returns(monkeypatch, OpenAIResult(error="No LLM provider configured."))
    response = client.post(URL, json={"medicine_name": "Aspirin", "dosage": "double"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Caution"
    assert any("built by fixed rules" in w for w in body["warnings"])
