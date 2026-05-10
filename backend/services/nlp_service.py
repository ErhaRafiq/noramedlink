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
            "Summarize report evidence for care support without diagnosing, prescribing, or inventing facts. "
            "Preserve abnormal values, units, key tests, symptoms, and explicit negations."
        ),
        prompt=(
            f"Report category: {category or 'not selected'}\n\n"
            "Write a doctor-friendly summary with this exact structure:\n"
            "1) Clinical context (1 sentence)\n"
            "2) Key findings (2-5 bullets; include exact values/units when present)\n"
            "3) Risk signals or red flags (1-3 bullets)\n"
            "4) Data quality notes (missing/unclear OCR info)\n"
            "5) Final safety line: This is not a medical diagnosis. Please consult a doctor.\n\n"
            "Constraints:\n"
            "- If a result is negated, state that it was explicitly absent.\n"
            "- If no clear abnormalities exist, say so plainly.\n"
            "- Keep total output under 220 words.\n\n"
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
