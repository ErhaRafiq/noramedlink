from services.ai_guard import numbers_not_in_source
from services.ocr_service import detect_report_type
from services.ocr_space_service import detect_keywords
from services.openai_service import fallback_notice, generate_openai_text
from services.privacy import redact_identifiers

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


async def summarize_with_optional_llm(
    text: str, category: str | None = None, identity: list | None = None
) -> tuple[str, str, str | None]:
    """A plain-language summary of pasted or saved report text, for a reader with no medical training.

    The rules' alerts are shown next to it on the page, so the AI only explains the report.
    """
    result = await generate_openai_text(
        instructions=(
            "You explain medical report text to a person with no medical or technical background, in plain, "
            "warm, everyday English (aim for a 12-year-old's reading level).\n\n"
            "Write these sections, each heading on its own line:\n"
            "What this report is\n  One or two sentences about the kind of test and why it is usually done.\n"
            "Your results explained\n  One short bullet (starting with '- ') per result: the test, its value "
            "and unit exactly as written, and in simple words what the test measures.\n"
            "What the report marks\n  Only results the report itself marks as high, low or abnormal; if none, "
            "say so, and that this does not mean everything is normal.\n"
            "Questions to ask your doctor\n  Two or three short questions.\n\n"
            "Rules: use only values and words from the text; never invent, round, convert or correct a value. "
            "Do not decide yourself whether a value is high, low or dangerous. Do not diagnose or suggest "
            "treatment. Plain text only, no markdown symbols such as ** or #. About 300 words at most. "
            "End with: This is not a medical diagnosis. Please consult a doctor."
        ),
        prompt=f"Report category: {category or 'not selected'}\n\nReport text:\n{redact_identifiers(text[:12000], identity)}",
    )

    if result.text:
        summary = result.text.strip()
        if numbers_not_in_source(summary, text):
            # A number that is not in the report must never reach the reader (AGENTS.md 6).
            fallback = build_rule_based_summary(text, category)
            return (
                fallback,
                "rule_based",
                "The AI summary used numbers that are not in the report, so it was not shown.",
            )
        if DISCLAIMER.lower() not in summary.lower():
            summary = f"{summary}\n\n{DISCLAIMER}"
        return summary, result.provider or "openai", None

    fallback = build_rule_based_summary(text, category)
    notice = fallback_notice(result.error)
    if notice:
        fallback = f"{fallback}\n\n{notice}"
    return fallback, "rule_based", result.error
