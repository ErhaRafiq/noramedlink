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


def redact_identifiers(text: str, known: list[re.Pattern] | None = None) -> str:
    """Generic identifier removal, plus `known` patterns for one patient (see identity_patterns)."""

    def replace(match: re.Match) -> str:
        if match.group("label").lower() == "name" and not match.group("sep").strip():
            return match.group(0)  # bare "name" without ":" is too common in report text to remove
        return f"{match.group('label')}{match.group('sep')}{REMOVED}"

    for pattern in known or []:  # first, so an unlabelled name in a report header goes too
        text = pattern.sub(REMOVED, text or "")
    text = _LABELLED.sub(replace, text or "")
    text = _TITLED_NAME.sub(lambda m: f"{m.group('title')}. {REMOVED}", text)
    text = _CNIC.sub(REMOVED, text)
    return _PHONE.sub(REMOVED, text)


# Name parts that are titles or too short to remove safely on their own.
_NOT_A_NAME_PART = {"mr", "mrs", "miss", "ms", "dr", "muhammad", "mohammad", "syed", "bibi", "begum", "khan"}


def identity_patterns(
    full_name: str | None = None, phone: str | None = None, cnic: str | None = None
) -> list[re.Pattern]:
    """Patterns for one patient's own identifiers, wherever they appear in their report text.

    The generic rules above only catch labelled or titled names. OCR often loses the label, and
    the entity model joins words ("Irha Rafiq" became the entity "irharafiq"), so the account's
    own name is removed as a whole, run together, and part by part (parts of 3+ letters that are
    not titles or very common name words). Phone and CNIC digits match with any separators.
    """
    patterns: list[re.Pattern] = []
    parts = [p for p in re.findall(r"[A-Za-z]+", full_name or "") if len(p) >= 3 and p.lower() not in _NOT_A_NAME_PART]
    if len(parts) >= 2:
        patterns.append(re.compile(r"\b" + r"[\s.\-]*".join(map(re.escape, parts)) + r"\b", re.IGNORECASE))
    patterns += [re.compile(rf"\b{re.escape(part)}\b", re.IGNORECASE) for part in parts]
    for number in (phone, cnic):
        digits = re.sub(r"\D", "", number or "")
        if len(digits) >= 7:
            patterns.append(re.compile(r"(?<!\d)" + r"[\s\-]*".join(digits[-10:]) + r"(?!\d)"))
    return patterns


def patient_identity_patterns(user) -> list[re.Pattern]:
    """identity_patterns for a User (name, phone, and CNIC from the patient profile)."""
    if user is None:
        return []
    profile = getattr(user, "patient_profile", None)
    return identity_patterns(
        getattr(user, "full_name", None), getattr(user, "phone", None), getattr(profile, "cnic", None)
    )


# Structured fields that hold identity rather than medical data; dropped before analysis.
IDENTITY_FIELDS = {"patient_name", "name", "phone", "mobile", "cnic", "address", "mr_no", "mrn", "patient_id"}
