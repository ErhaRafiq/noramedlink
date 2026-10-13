"""Removes patient identifiers from text before it is sent to an external AI provider.

Reports start with a header (patient name, MR number, CNIC, phone, address). A summary needs
none of it, and every prompt leaves the server (OpenAI, Groq, Gemini). Labelled values are
replaced with "[removed]"; CNIC and Pakistani phone numbers are removed wherever they appear.
Medical values, ages, dates and the referring doctor are kept.
"""

import re

REMOVED = "[removed]"

# "Label: value", "Label - value" or "Label value" (a header cell), up to " | ", two spaces,
# the end of the line, or the next known label.
_LABELS = (
    r"patient\s*name|patient's\s*name|name\s*of\s*patient|name|father'?s?\s*name|husband'?s?\s*name|"
    r"mr\s*(?:no|number|#)|mrn(?:\s*/\s*pin)?|m\.r\.?\s*no|patient\s*id|pid|reg(?:istration)?\s*no|"
    r"cnic(?:\s*/\s*pp\s*no)?|nic|passport\s*no|"
    r"phone|mobile|cell|contact(?:\s*no)?|tel(?:ephone)?|address"
)
_LABELLED = re.compile(
    rf"(?im)\b(?P<label>{_LABELS})\b(?P<sep>\s*[:\-#./]\s*|\s+)(?P<value>.+?)(?=\s+\|\s|\s{{2,}}|$|\s(?:{_LABELS})\b\s*[:\-])"
)
# "Miss. Irha Rafiq", "Mr Bilal Khan": a name after a personal title (never "Dr.": doctors are kept).
_TITLED_NAME = re.compile(
    r"\b(?P<title>Mrs|Miss|Ms|Mr|Master)\.?\s+[A-Z][a-z]+(?: (?!(?:Age|Sex|Gender|Ref|Date|Dob)\b)[A-Z][a-z]+){0,3}"
)  # single spaces only (two or more end the cell), and the next header label ends the name
_CNIC = re.compile(r"\b\d{5}-?\d{7}-?\d\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?92[\s-]?|0)3\d{2}[\s-]?\d{7}(?!\d)")


def redact_identifiers(text: str) -> str:
    def replace(match: re.Match) -> str:
        if match.group("label").lower() == "name" and not match.group("sep").strip():
            return match.group(0)  # bare "name" without ":" is too common in report text to remove
        return f"{match.group('label')}{match.group('sep')}{REMOVED}"

    text = _LABELLED.sub(replace, text or "")
    text = _TITLED_NAME.sub(lambda m: f"{m.group('title')}. {REMOVED}", text)
    text = _CNIC.sub(REMOVED, text)
    return _PHONE.sub(REMOVED, text)
