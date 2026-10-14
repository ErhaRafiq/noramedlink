"""FDA label evidence (services/mscie/openfda.py): never called in tests, never fails loudly."""

from dataclasses import replace

import httpx

from services.mscie import openfda


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code, self.payload = status_code, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self.payload


def enabled(monkeypatch, response):
    monkeypatch.setattr(openfda, "settings", replace(openfda.settings, paid_services_disabled=False))
    monkeypatch.setattr(openfda, "_cache", {})
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(openfda.httpx, "get", fake_get)
    return calls


def test_off_in_test_runs(monkeypatch):
    monkeypatch.setattr(openfda, "settings", replace(openfda.settings, paid_services_disabled=True))
    result = openfda.label_evidence("warfarin")
    assert result["available"] is False and "off" in result["reason"]


def test_label_sections_are_returned_trimmed_and_cached(monkeypatch):
    label = {"drug_interactions": ["x " * 1000], "contraindications": ["Hypersensitivity."], "set_id": "abc"}
    calls = enabled(monkeypatch, FakeResponse(200, {"results": [label]}))
    first = openfda.label_evidence("Warfarin")
    second = openfda.label_evidence("warfarin")
    assert first["available"] and first["sections"]["contraindications"] == "Hypersensitivity."
    assert len(first["sections"]["drug_interactions"]) <= openfda.MAX_CHARS + 3
    assert second is first and len(calls) == 1  # cached


def test_no_label_and_network_errors_are_reported_not_raised(monkeypatch):
    enabled(monkeypatch, FakeResponse(404))
    assert openfda.label_evidence("rifaximin")["reason"] == "no FDA label found for this name"
    enabled(monkeypatch, httpx.ConnectError("down"))
    assert openfda.label_evidence("warfarin")["reason"] == "the FDA label could not be reached"
