"""AI wording for the clinical summary's "Key findings" (ICSE FE-2), for physicians.

The AI rewords only that one paragraph, from the facts the rules already put in the summary. It
never sees report titles, raw report text or the patient's identity, never sets or changes a flag
or a severity, and a paragraph with any number that is not in those facts is rejected (the
rule-built sentence is kept). Without an AI key the summary stays rule-based.
"""

from __future__ import annotations

import logging
from typing import Any

from services.ai_guard import numbers_not_in_source
from services.openai_service import generate_openai_text
from services.privacy import redact_identifiers

logger = logging.getLogger("nora.icse")
MAX_WORDS = 80

INSTRUCTIONS = (
    "You write the 'Key findings' paragraph of a clinical summary for a physician who has under a "
    "minute to read it.\n"
    "Use only the facts given. Do not add values, dates, diagnoses or advice that are not in them. "
    "Keep every number exactly as written. Do not change or soften any severity: high-risk findings "
    "come first. Conditions are 'mentioned in reports', not confirmed diagnoses.\n"
    f"Plain clinical English, one paragraph, at most {MAX_WORDS} words, no markdown, no lists."
)


def facts(content: dict[str, Any]) -> str:
    """The summary's facts as plain lines: no report titles, no source references."""
    lines = [f"- [{f['severity']}] {f['message']}" for f in content.get("abnormal_results", [])]
    lines += [f"- [{f['severity']}] {f['message']}" for f in content.get("flags", [])]
    conditions = [c["name"] + (" (long-term)" if c.get("chronic") else "") for c in content.get("conditions", [])]
    if conditions:
        lines.append("- Conditions mentioned in reports: " + ", ".join(conditions))
    medicines = content.get("medications", {})
    names = [m.get("name") for m in medicines.get("from_app", [])] + [
        m.get("medicine") for m in medicines.get("from_reports", [])
    ]
    if any(names):
        lines.append("- Medicines listed: " + ", ".join(n for n in names if n))
    allergies = content.get("allergies", {})
    if allergies.get("items"):
        lines.append("- Allergies mentioned: " + ", ".join(a["name"] for a in allergies["items"]))
    elif allergies.get("status") == "not_recorded":
        lines.append("- Allergy status: not recorded")
    lines += [f"- Missing: {m}" for m in content.get("missing_data", [])]
    return "\n".join(lines)


async def reword_key_findings(content: dict[str, Any], identity: list) -> tuple[str | None, str | None, str | None]:
    """(AI paragraph or None, its provider, why it was not used). Never raises."""
    source_facts = redact_identifiers(facts(content), identity)
    if not source_facts.strip():
        return None, None, "no findings to word"
    try:
        result = await generate_openai_text(instructions=INSTRUCTIONS, prompt=f"Facts:\n{source_facts}")
    except Exception as exc:  # an AI failure must never break the rule-built summary
        return None, None, f"AI unavailable ({type(exc).__name__})"
    if not result.text:
        return None, None, result.error or "no AI key configured"
    text = " ".join(result.text.split())
    invented = numbers_not_in_source(text, source_facts)
    if invented:
        logger.warning("AI key findings rejected: %d number(s) not in the summary's facts.", len(invented))
        return None, None, "the AI wording used numbers that are not in the summary, so it was not used"
    if len(text.split()) > MAX_WORDS * 1.5:
        return None, None, "the AI wording was too long, so it was not used"
    return text, result.provider or "openai", None
