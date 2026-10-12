"""Structured breakdown of report text for the summarize page.

- key_findings: values and terms found in the text, as written (no judgement).
- risk_indicators: alerts from the deterministic report rules (validate_medical_rules) only,
  so this page and report validation never disagree (AGENTS.md 6.2).
- recommendations: fixed next-step wording.

This replaced a second rule engine that ran in the browser (lib/medical-summarizer.ts).
"""

import re

from services.rule_validation_service import validate_medical_rules

MAX_ITEMS = 8

# Name, aliases (regex) as they appear in reports. Values are reported, not judged.
MEASUREMENTS = [
    ("Hemoglobin", r"hb|hemoglobin|haemoglobin"),
    ("WBC", r"wbc|white blood cells?"),
    ("Platelets", r"platelets?"),
    ("Glucose", r"glucose|blood sugar|fbs|rbs"),
    ("HbA1c", r"hba1c|a1c"),
    ("Creatinine", r"creatinine"),
    ("Urea", r"urea"),
    ("eGFR", r"e-?gfr"),
    ("Bilirubin", r"bilirubin"),
    ("ALT", r"alt|sgpt"),
    ("AST", r"ast|sgot"),
    ("LDL", r"ldl"),
    ("HDL", r"hdl"),
    ("Triglycerides", r"triglycerides?|tg"),
    ("SpO2", r"spo2|oxygen saturation"),
]
UNIT = r"(?:g/dl|mg/dl|mmol/l|u/l|iu/l|%|x\s?10\^?\d+/l|/[uµ]l|cells/[uµ]l)"

TERMS = [
    "fever", "cough", "chest pain", "shortness of breath", "breathlessness", "vomiting", "nausea",
    "diarrhea", "infection", "pneumonia", "asthma", "diabetes", "hypertension", "anemia", "anaemia",
    "jaundice", "hepatitis", "stroke", "seizure", "pregnancy", "allergy", "edema", "swelling",
    "bleeding", "dizziness", "fatigue",
]  # fmt: skip
NEGATIONS = ["no ", "not ", "without ", "denies ", "denied ", "negative for ", "absence of ", "free of "]

# Rule alerts about the scan itself, which do not apply to pasted text.
NOT_FOR_TEXT = {"NO_RULE_ALERTS", "MISSING_ALLERGY_DATA", "INCOMPLETE_OCR_TEXT"}


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))[:MAX_ITEMS]


def measured_values(text: str) -> list[str]:
    found: list[str] = []
    for name, aliases in MEASUREMENTS:
        pattern = rf"\b(?:{aliases})\b\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*({UNIT})?"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            unit = f" {match.group(2)}" if match.group(2) else ""
            found.append(f"{name}: {match.group(1)}{unit}")
    for match in re.finditer(r"\b(?:bp|blood pressure)\s*[:=-]?\s*(\d{2,3})\s*/\s*(\d{2,3})\b", text, re.IGNORECASE):
        found.append(f"Blood pressure: {match.group(1)}/{match.group(2)}")
    return found


# The report's own conclusion: text after an "Impression:" (or similar) heading, up to the
# next "Label:" line, a blank line or the end.
_CONCLUSION = re.compile(
    r"^[ \t]*(?i:impression|conclusion|opinion|final diagnosis)[ \t]*[:\-][ \t]*(?P<body>.*?)"
    r"(?=^[ \t]*[A-Z][A-Za-z .&/]{1,40}:|\n[ \t]*\n|\Z)",
    re.MULTILINE | re.DOTALL,
)


def report_conclusion(text: str, limit: int = 700) -> str | None:
    """The conclusion as the reporting doctor wrote it, or None when the report has none."""
    match = _CONCLUSION.search(text or "")
    if not match:
        return None
    body = " ".join(match.group("body").split())
    if len(body) < 15:
        return None
    return body if len(body) <= limit else body[:limit].rsplit(" ", 1)[0] + "..."


def mentioned_terms(text: str) -> tuple[list[str], list[str]]:
    """Terms the text mentions, split into present and stated as absent ("no chest pain")."""
    present: list[str] = []
    absent: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text.lower()):
        for term in TERMS:
            index = sentence.find(term)
            if index < 0 or not re.search(rf"\b{re.escape(term)}\b", sentence):
                continue
            before = sentence[max(0, index - 36) : index]
            (absent if any(word in before for word in NEGATIONS) else present).append(term)
    return _unique(present), _unique(absent)


def rule_alerts(text: str) -> list[str]:
    alerts = []
    for warning in validate_medical_rules(text)["warnings"]:
        if warning["code"] in NOT_FOR_TEXT:
            continue
        evidence = warning.get("evidence")
        short_evidence = f" ({evidence})" if evidence and len(evidence) <= 40 else ""
        alerts.append(f"{warning['message']}{short_evidence}")
    return _unique(alerts)


def build_breakdown(text: str) -> dict[str, list[str]]:
    present, absent = mentioned_terms(text)
    findings = measured_values(text)
    if present:
        findings.append(f"Mentions: {', '.join(present)}")
    if absent:
        findings.append(f"Stated as absent: {', '.join(absent)}")
    alerts = rule_alerts(text)

    recommendations = [
        "Review this summary with a qualified clinician before making care decisions.",
        "Compare the values with the reference ranges printed on the original report.",
    ]
    if alerts:
        recommendations.append("Discuss the alerts listed above with a doctor.")
        recommendations.append(
            "Seek prompt medical advice if symptoms are severe, worsening, or come with chest pain, "
            "breathing difficulty, confusion or bleeding."
        )
    return {"key_findings": _unique(findings), "risk_indicators": alerts, "recommendations": recommendations}
