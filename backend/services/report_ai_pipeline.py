from typing import Any

from services.biobert_service import extract_medical_entities
from services.openai_service import fallback_notice, generate_openai_json, generate_openai_text
from services.rule_validation_service import validate_medical_rules


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
        str(item.get("message") or "")
        for item in validation.get("warnings", [])
        if item.get("severity") != "SAFE"
    ][:6]
    preview = " ".join(text.split())[:260]

    missing_data = []
    if not text.strip():
        missing_data.append("Readable OCR text is missing.")
    if not any(item.get("label") == "Allergy" for item in entities):
        missing_data.append("Allergy history was not found in this report.")

    summary = (
        f"{department} report processed with OCR and medical entity extraction. "
        f"Key structured fields: {', '.join(lab_values[:4]) or 'none detected'}. "
        f"Rule validation status: {validation.get('status', 'CAUTION')}."
    )
    if preview and not lab_values:
        summary = f"{summary} OCR preview: {preview}"

    if warning:
        summary = f"{summary} {fallback_notice(warning)}"

    return {
        "patient_overview": f"Uploaded {department.lower()} report. Use only as a support summary pending doctor review.",
        "key_findings": lab_values or list(structured_fields.keys())[:6] or ["No structured clinical fields were confidently extracted."],
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
        return _normalize_summary_json(result.data, fallback), "openai", None

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
            "confidence_level": str(result.data.get("confidence_level") or summary_json.get("confidence_level") or "Moderate"),
            "notes": _string_list(notes, ["LLM self-check completed."]),
            "source": "openai",
        }

    return {
        "passed": True,
        "confidence_level": str(summary_json.get("confidence_level") or "Moderate"),
        "notes": [fallback_notice(result.error) or "Self-check used local fallback because OpenAI was unavailable."],
        "source": "rule_based",
    }


def _build_patient_summary_fallback(
    clinical_json: dict[str, Any],
    department: str,
    validation: dict[str, Any],
) -> str:
    """Build a patient-friendly summary from the clinical JSON when OpenAI is unavailable."""
    parts = []

    overview = clinical_json.get("patient_overview", "")
    if overview:
        parts.append(overview)

    findings = clinical_json.get("key_findings", [])
    if findings and findings != ["No structured clinical fields were confidently extracted."]:
        parts.append("Key findings from your report: " + ", ".join(findings[:5]) + ".")

    diseases = clinical_json.get("detected_diseases", [])
    if diseases and diseases != ["No disease entity was confidently detected."]:
        parts.append("Possible conditions mentioned: " + ", ".join(diseases[:4]) + ".")

    medicines = clinical_json.get("medicines", [])
    if medicines and medicines != ["No medicine entity was confidently detected."]:
        parts.append("Medicines found in the report: " + ", ".join(medicines[:5]) + ".")

    alerts = clinical_json.get("risks_alerts", [])
    if alerts and alerts != ["No rule-based alert detected."]:
        parts.append("Alerts: " + " ".join(alerts[:3]))

    status = validation.get("status", "SAFE")
    if status == "HIGH_RISK":
        parts.append("This report contains values that need urgent doctor attention.")
    elif status == "CAUTION":
        parts.append("Some values in this report may need a doctor's review.")

    parts.append("Please consult your doctor for proper diagnosis and treatment.")

    return " ".join(parts)


async def _generate_patient_summary(
    text: str,
    department: str,
    clinical_json: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[str, str | None]:
    """Generate a patient-friendly summary using OpenAI.

    Returns the summary text and an optional warning if OpenAI was unavailable.
    """
    result = await generate_openai_text(
        instructions=(
            "You are a patient-friendly medical report summarizer for Nora MedLink. "
            "Your job is to explain medical report findings in simple, easy-to-understand language. "
            "Rules:\n"
            "- Write in simple English that any patient can understand.\n"
            "- Explain what each abnormal value means in plain terms.\n"
            "- Do NOT diagnose or prescribe treatment.\n"
            "- Highlight any values that seem abnormal and explain why they matter.\n"
            "- Mention detected medicines and what they are typically used for.\n"
            "- If there are risk alerts, explain them simply.\n"
            "- Always end with: 'Please consult your doctor for proper diagnosis and treatment.'\n"
            "- Keep the summary between 100-300 words.\n"
            "- Use bullet points for key findings."
        ),
        prompt=(
            f"Medical Department: {department}\n"
            f"Clinical Summary: {clinical_json}\n"
            f"Validation Status: {validation.get('status', 'SAFE')}\n\n"
            f"Original OCR Report Text:\n{_compact_text(text, 6000)}\n\n"
            "Write a patient-friendly summary of this medical report. "
            "The patient should be able to understand their results after reading this."
        ),
    )

    if result.text:
        summary = result.text.strip()
        if "consult your doctor" not in summary.lower() and "consult a doctor" not in summary.lower():
            summary += "\n\nPlease consult your doctor for proper diagnosis and treatment."
        return summary, None

    fallback = _build_patient_summary_fallback(clinical_json, department, validation)
    return fallback, result.error


async def run_report_ai_pipeline(
    *,
    cleaned_text: str,
    formatted_text: str,
    structured_payload: dict[str, Any],
    department_name: str,
) -> dict[str, Any]:
    fields = structured_payload.get("fields") if isinstance(structured_payload.get("fields"), dict) else {}
    source_text = formatted_text.strip() or cleaned_text.strip()

    entities, entity_metadata = await extract_medical_entities(source_text, fields)
    validation = validate_medical_rules(source_text, fields, entities)
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
    patient_summary, patient_summary_warning = await _generate_patient_summary(
        source_text,
        department_name,
        summary_json,
        validation,
    )

    return {
        "entities": entities,
        "entity_metadata": entity_metadata,
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
    }
