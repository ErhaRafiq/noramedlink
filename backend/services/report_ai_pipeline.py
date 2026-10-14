import logging
import re
from typing import Any

from services.ai_guard import numbers_not_in_source
from services.biobert_service import extract_medical_entities
from services.icse.entities import ENTITIES_VERSION, extract_entities
from services.openai_service import fallback_notice, generate_openai_json, generate_openai_text
from services.patient_summary import build_patient_summary
from services.plain_language import glossary, rewrite_sections
from services.privacy import IDENTITY_FIELDS, redact_identifiers
from services.report_breakdown import measured_values, report_conclusion
from services.rule_validation_service import validate_medical_rules

logger = logging.getLogger("nora.ai")

_MEASUREMENT = re.compile(r"[A-Za-z]{3,}\D{0,12}\d")  # a name, then a number: "Hemoglobin 10.8"


def _rule_check_sentence(validation: dict[str, Any]) -> str:
    """The rule result in words; no alerts is never described as normal or safe (AGENTS.md 6.2)."""
    status = validation.get("status")
    alerts = [w for w in validation.get("warnings", []) if w.get("severity") in {"CAUTION", "HIGH_RISK"}]
    if status == "HIGH_RISK":
        return "Rule check: at least one value needs prompt review by a doctor."
    if status == "CAUTION":
        return f"Rule check: {len(alerts)} point(s) to go over with a doctor."
    return "Rule check: no rule raised an alert. That does not mean the report is normal."


SUMMARY_SCHEMA_KEYS = [
    "patient_overview",
    "key_findings",
    "detected_diseases",
    "medicines",
    "risks_alerts",
    "doctor_notes",
    "confidence_level",
    "missing_data",
    "summary",
]


def _string_list(value: Any, fallback: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:8]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback or []


def _compact_text(value: str, limit: int = 12000) -> str:
    return "\n".join(line.strip() for line in (value or "").splitlines() if line.strip())[:limit]


def _fallback_summary_json(
    text: str,
    department: str,
    entities: list[dict[str, Any]],
    validation: dict[str, Any],
    structured_fields: dict[str, Any],
    warning: str | None = None,
) -> dict[str, Any]:
    disease_terms = [item["text"] for item in entities if item.get("label") == "Disease"][:6]
    medicines = [item["text"] for item in entities if item.get("label") == "Medicine"][:8]
    lab_values = [item["text"] for item in entities if item.get("label") == "Lab Value"][:8]
    rule_warnings = [
        str(item.get("message") or "") for item in validation.get("warnings", []) if item.get("severity") != "SAFE"
    ][:6]
    preview = " ".join(text.split())[:260]

    missing_data = []
    if not text.strip():
        missing_data.append("Readable OCR text is missing.")
    if not any(item.get("label") == "Allergy" for item in entities):
        missing_data.append("Allergy history was not found in this report.")

    conclusion = report_conclusion(text)
    # Deterministic values first; the NER model also tags header words ("mri", "age") as lab values.
    values = measured_values(text)[:8] or [value for value in lab_values if _MEASUREMENT.search(value)]
    parts = [f"{department} report."]
    if conclusion:
        parts.append(f"The report's conclusion, as written: {conclusion}")
    elif preview:
        parts.append(f"Start of the report text: {preview}")
    if values:
        parts.append(f"Values found: {', '.join(values[:6])}.")
    parts.append(_rule_check_sentence(validation))
    summary = " ".join(parts)

    if warning:
        summary = f"{summary} {fallback_notice(warning)}"

    return {
        "patient_overview": f"Uploaded {department.lower()} report. Use only as a support summary pending doctor review.",
        "report_conclusion": conclusion,
        # Real values only; the old fallback listed field names such as "age" or "gender".
        # Narrative reports (MRI, X-ray) have no values; their conclusion sentences are the findings.
        "key_findings": values
        or [s.strip() for s in re.split(r"(?<=\.)\s+", conclusion or "") if s.strip()][:4]
        or ["No structured clinical fields were confidently extracted."],
        "detected_diseases": disease_terms or ["No disease entity was confidently detected."],
        "medicines": medicines or ["No medicine entity was confidently detected."],
        "risks_alerts": rule_warnings or ["No rule-based alert detected."],
        "doctor_notes": [
            "Verify OCR values against the uploaded file.",
            "This summary does not diagnose or prescribe.",
        ],
        "confidence_level": "Low" if validation.get("status") == "HIGH_RISK" and len(text.split()) < 20 else "Moderate",
        "missing_data": missing_data or ["No major missing data note detected from the available text."],
        "summary": summary,
    }


def _normalize_summary_json(data: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return fallback

    output = dict(fallback)
    for key in SUMMARY_SCHEMA_KEYS:
        if key not in data:
            continue
        if key in {"key_findings", "detected_diseases", "medicines", "risks_alerts", "doctor_notes", "missing_data"}:
            output[key] = _string_list(data.get(key), fallback.get(key, []))
        else:
            text = str(data.get(key) or "").strip()
            if text:
                output[key] = text[:1600] if key == "summary" else text[:320]

    if not output.get("summary"):
        output["summary"] = fallback["summary"]
    return output


def _summary_prompt(
    text: str,
    department: str,
    entities: list[dict[str, Any]],
    validation: dict[str, Any],
    structured_fields: dict[str, Any],
) -> str:
    return (
        f"Department: {department}\n"
        f"Structured fields JSON: {structured_fields}\n"
        f"Medical entities JSON: {entities[:40]}\n"
        f"Rule validation JSON: {validation}\n\n"
        "Generate a concise clinical-support JSON object with these exact keys:\n"
        "patient_overview, key_findings, detected_diseases, medicines, risks_alerts, "
        "doctor_notes, confidence_level, missing_data, summary.\n\n"
        "Rules:\n"
        "- Use only the provided OCR text, entities, structured fields, and rule validation.\n"
        "- Do not diagnose.\n"
        "- Do not prescribe or change medicines.\n"
        "- Flag possible risks as observations only.\n"
        "- Clearly mention missing allergy data or incomplete OCR when present.\n"
        "- Keep the summary professional and brief.\n\n"
        f"OCR text:\n{_compact_text(text)}"
    )


async def _generate_summary_json(
    text: str,
    department: str,
    entities: list[dict[str, Any]],
    validation: dict[str, Any],
    structured_fields: dict[str, Any],
) -> tuple[dict[str, Any], str, str | None]:
    fallback = _fallback_summary_json(text, department, entities, validation, structured_fields)
    result = await generate_openai_json(
        instructions=(
            "You are a cautious healthcare AI summarizer for Nora MedLink. "
            "You only summarize provided patient report text and validation output. "
            "You never diagnose, prescribe, or infer facts outside the supplied data."
        ),
        prompt=_summary_prompt(text, department, entities, validation, structured_fields),
    )

    if result.data:
        return _normalize_summary_json(result.data, fallback), result.provider or "openai", None

    fallback = _fallback_summary_json(text, department, entities, validation, structured_fields, result.error)
    return fallback, "rule_based", result.error


async def _self_check_summary(
    summary_json: dict[str, Any],
    text: str,
    validation: dict[str, Any],
) -> dict[str, Any]:
    result = await generate_openai_json(
        instructions=(
            "You verify clinical-support summaries. Return JSON only. "
            "Check for unsupported diagnoses, prescribing advice, missing-data disclosure, and consistency with rule validation."
        ),
        prompt=(
            f"Summary JSON: {summary_json}\n\n"
            f"Rule validation JSON: {validation}\n\n"
            f"OCR evidence:\n{_compact_text(text, 5000)}\n\n"
            "Return keys: passed (boolean), confidence_level (Low|Moderate|High), notes (array of strings)."
        ),
    )

    if isinstance(result.data, dict):
        notes = result.data.get("notes")
        return {
            "passed": bool(result.data.get("passed", False)),
            "confidence_level": str(
                result.data.get("confidence_level") or summary_json.get("confidence_level") or "Moderate"
            ),
            "notes": _string_list(notes, ["LLM self-check completed."]),
            "source": "openai",
        }

    return {
        "passed": True,
        "confidence_level": str(summary_json.get("confidence_level") or "Moderate"),
        "notes": [fallback_notice(result.error) or "Self-check used local fallback because OpenAI was unavailable."],
        "source": "rule_based",
    }


async def _generate_patient_summary(
    text: str,
    department: str,
    clinical_json: dict[str, Any],
    validation: dict[str, Any],
    entities: list[dict[str, Any]] | None = None,
) -> tuple[str, str | None, str]:
    """A summary in everyday words for a patient with no medical training.

    The AI writes it when a key is set; otherwise (or when the AI's summary is rejected) it is built
    by fixed rules (services/patient_summary.py). Either way every medical word then gets its
    everyday wording, with the term in brackets once (services/plain_language.py). Returns the
    summary, a warning when the AI one could not be used, and its source ("gemini", "openai",
    "groq" or "rule_based").
    """
    entities = extract_entities(text) if entities is None else entities

    def rule_based() -> str:
        return build_patient_summary(text, entities, validation, department, clinical_json.get("report_conclusion"))

    alerts = [
        w.get("patient_message") or w["message"]
        for w in validation.get("warnings", [])
        if w.get("severity") in {"CAUTION", "HIGH_RISK"}
    ]
    result = await generate_openai_text(
        instructions=PATIENT_SUMMARY_INSTRUCTIONS, prompt=_patient_summary_prompt(text, department, alerts)
    )

    if result.text:
        summary = result.text.strip()
        invented = numbers_not_in_source(summary, text)
        if invented:
            # A number that is not in the report must never reach the patient (AGENTS.md 6).
            logger.warning("AI patient summary rejected: %d number(s) not found in the report text.", len(invented))
            return (
                rule_based(),
                "The AI summary used numbers that are not in the report, so it was not shown.",
                "rule_based",
            )
        if "consult your doctor" not in summary.lower() and "consult a doctor" not in summary.lower():
            summary += "\n\nPlease consult your doctor for proper diagnosis and treatment."
        # Any medical word the AI left as it was gets its everyday wording here.
        return rewrite_sections(summary), None, result.provider or "openai"

    return rule_based(), result.error, "rule_based"


PATIENT_SUMMARY_INSTRUCTIONS = (
    "You explain a person's medical test report to them in plain, warm, everyday English, for someone "
    "with no medical or technical background (aim for a 12-year-old's reading level).\n\n"
    "Write these sections, each starting with its heading on its own line:\n"
    "What this report is\n"
    "  One or two sentences: what kind of test or scan this is and why doctors usually order it.\n"
    "Your results explained\n"
    "  One short bullet (starting with '- ') per result or finding. Name the test, give the value and "
    "unit exactly as written in the report, then say in simple words what that test measures.\n"
    "What may need attention\n"
    "  Only results the report itself marks as high/low/abnormal (for example with H or L), and the "
    "alerts listed in the prompt. Explain each one simply and calmly. If there are none, say that "
    "nothing on the report was marked for attention, and that this does not mean everything is normal.\n"
    "Words you might see\n"
    "  Two to four medical words from the report, each explained in one simple sentence.\n"
    "Questions to ask your doctor\n"
    "  Two or three short, useful questions.\n\n"
    "Rules you must follow:\n"
    "- Use only numbers, values and words that appear in the report text. Never invent, round, "
    "convert or correct a value. If something is unclear in the report, say it is unclear.\n"
    "- Do not decide yourself whether a value is high, low, normal or dangerous: only repeat what the "
    "report marks and the alerts you are given.\n"
    "- Do not diagnose, do not name a disease the report does not name, and do not suggest medicines, "
    "doses or treatment.\n"
    "- Plain text only: no markdown symbols such as ** or #. Short sentences. No more than about 350 words.\n"
    "- End with: Please consult your doctor for proper diagnosis and treatment."
)


def _patient_summary_prompt(text: str, department: str, alerts: list[str]) -> str:
    alert_lines = "\n".join(f"- {alert}" for alert in alerts) or "- none"
    words = glossary(text, limit=20)
    word_lines = "\n".join(f'- {w["term"]}: say "{w["plain"]}" ({w["explain"]})' for w in words) or "- none"
    return (
        f"Department: {department}\n"
        f"Alerts from the app's safety rules (explain these; do not add others):\n{alert_lines}\n\n"
        "Everyday words to use for the medical words in this report (write the everyday words, and put "
        f"the medical word in brackets the first time):\n{word_lines}\n\n"
        f"Report text (as read from the file; it may contain reading mistakes):\n{_compact_text(text, 6000)}"
    )


async def run_report_ai_pipeline(
    *,
    cleaned_text: str,
    formatted_text: str,
    structured_payload: dict[str, Any],
    department_name: str,
    uncertain_values: list[dict[str, Any]] | None = None,
    identity: list | None = None,
) -> dict[str, Any]:
    # Privacy: the patient's identity is removed before entity extraction, rules, summaries and AI
    # prompts, so none of them can carry it (stored entities, stored summaries, external AI).
    fields = structured_payload.get("fields") if isinstance(structured_payload.get("fields"), dict) else {}
    fields = {
        key: redact_identifiers(str(value), identity) if isinstance(value, str) else value
        for key, value in fields.items()
        if str(key).lower() not in IDENTITY_FIELDS
    }
    source_text = redact_identifiers(formatted_text.strip() or cleaned_text.strip(), identity)

    entities, entity_metadata = await extract_medical_entities(source_text, fields)
    # Typed entities for the clinical summary: rules and the knowledge base first, BioBERT only as
    # a low-confidence suggestion. Built from the same identity-free text.
    ocr_rows = structured_payload.get("ocr_rows") or []
    clinical_entities = extract_entities(source_text, entities, fields, ocr_rows)
    validation = validate_medical_rules(source_text, fields, entities, uncertain_values, ocr_rows)
    summary_json, summary_source, summary_warning = await _generate_summary_json(
        source_text,
        department_name,
        entities,
        validation,
        fields,
    )
    self_check = await _self_check_summary(summary_json, source_text, validation)
    confidence_level = str(self_check.get("confidence_level") or summary_json.get("confidence_level") or "Moderate")

    # Generate patient-friendly summary via OpenAI
    patient_summary, patient_summary_warning, patient_summary_source = await _generate_patient_summary(
        source_text,
        department_name,
        summary_json,
        validation,
        clinical_entities,
    )

    return {
        "entities": entities,
        "entity_metadata": entity_metadata,
        "clinical_entities": clinical_entities,
        "clinical_entities_version": ENTITIES_VERSION,
        "validation_results": validation,
        "rule_warnings": validation.get("warnings", []),
        "validation_status": validation.get("status", "CAUTION"),
        "clinical_summary_json": summary_json,
        "summary_text": str(summary_json.get("summary") or "").strip(),
        "summary_source": summary_source,
        "summary_warning": summary_warning,
        "llm_self_check": self_check,
        "confidence_level": confidence_level,
        "patient_summary": patient_summary,
        "patient_summary_warning": patient_summary_warning,
        "patient_summary_source": patient_summary_source,
    }
