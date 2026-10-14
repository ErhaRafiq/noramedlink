"""FDA label text as supporting evidence for physicians (openFDA, public, no key).

Shown next to an alert as "what the FDA label says": it never sets or changes a severity (the CSV
rules do). Looked up by generic name, cached in memory, short timeout; when openFDA cannot be
reached (or in test runs, DISABLE_PAID_SERVICES=1) the answer says so instead of failing.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("nora.mscie")
URL = "https://api.fda.gov/drug/label.json"
SECTIONS = ("contraindications", "warnings_and_cautions", "drug_interactions", "dosage_and_administration")
MAX_CHARS = 900
CACHE_SECONDS = 24 * 3600
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _clip(texts: list[str] | None) -> str | None:
    text = " ".join(" ".join(texts or []).split())
    return (text[:MAX_CHARS].rsplit(" ", 1)[0] + "...") if len(text) > MAX_CHARS else (text or None)


def label_evidence(generic: str) -> dict[str, Any]:
    key = " ".join((generic or "").lower().split())
    if settings.paid_services_disabled:
        return {"generic": key, "available": False, "reason": "external lookups are off in this run"}
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        response = httpx.get(URL, params={"search": f'openfda.generic_name:"{key}"', "limit": 1}, timeout=8)
        if response.status_code == 404:
            result = {"generic": key, "available": False, "reason": "no FDA label found for this name"}
        else:
            response.raise_for_status()
            label = response.json()["results"][0]
            result = {
                "generic": key,
                "available": True,
                "sections": {section: _clip(label.get(section)) for section in SECTIONS},
                "set_id": label.get("set_id"),
                "effective_time": label.get("effective_time"),
                "source": "openFDA drug label (api.fda.gov), U.S. prescribing information",
            }
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.info("openFDA lookup failed for a medicine: %s", type(exc).__name__)
        return {"generic": key, "available": False, "reason": "the FDA label could not be reached"}
    _cache[key] = (time.monotonic(), result)
    return result
