from services.ocr_service import detect_keywords, detect_report_type
from services.openai_service import fallback_notice, generate_openai_text


DISCLAIMER = "This is not a medical diagnosis. Please consult a doctor."


def build_rule_based_summary(text: str, category: str | None = None) -> str:
    cleaned = " ".join(text.split())
    keywords = detect_keywords(cleaned)
    report_type = detect_report_type(cleaned)
    category_name = category or "not selected"
    keyword_text = ", ".join(keywords[:8]) if keywords else "none"

    if not cleaned:
        return (
            f"Selected category: {category_name}. Detected medical keywords: {keyword_text}. "
            f"No readable text was available for summary. {DISCLAIMER}"
        )

    preview = cleaned[:220].strip()
    readable_hint = (
        "The document may contain medical values, prescriptions, or clinical notes that need a doctor's review."
        if keywords
        else f"The readable text begins with: {preview}. No strong medical keyword pattern was detected."
    )
    return (
        f"Selected category: {category_name}. Possible report type: {report_type}. "
        f"Detected medical keywords: {keyword_text}. {readable_hint} "
        f"{DISCLAIMER}"
    )


async def summarize_with_optional_llm(text: str, category: str | None = None) -> tuple[str, str, str | None]:
    result = await generate_openai_text(
        instructions=(
            "You generate concise clinical summaries for Nora MedLink. "
            "Summarize medical report text for a patient and doctor without diagnosing, prescribing, "
            "or giving unsafe instructions. Preserve abnormal values, key test names, symptoms, and negations. "
            "Mention that a qualified doctor must verify the summary."
        ),
        prompt=(
            f"Report category: {category or 'not selected'}\n\n"
            "Return a short doctor-friendly summary in plain text.\n\n"
            f"Medical text:\n{text[:12000]}"
        ),
    )

    if result.text:
        summary = result.text.strip()
        if DISCLAIMER.lower() not in summary.lower():
            summary = f"{summary} {DISCLAIMER}"
        return summary, "openai", None

    fallback = build_rule_based_summary(text, category)
    notice = fallback_notice(result.error)
    if notice:
        fallback = f"{fallback}\n\n{notice}"
    return fallback, "rule_based", result.error
