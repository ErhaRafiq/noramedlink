import mimetypes
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


OCR_SPACE_ENDPOINT = "https://api.ocr.space/parse/image"
DEFAULT_TIMEOUT_SECONDS = 60

DEPARTMENTS = [
    {
        "name": "Heart",
        "slug": "heart",
        "icon": "heart-pulse",
        "description": "Cardiology, ECG, lipids, blood pressure, and heart-related reports.",
    },
    {
        "name": "Kidney",
        "slug": "kidney",
        "icon": "activity",
        "description": "Renal, creatinine, urea, eGFR, and kidney function reports.",
    },
    {
        "name": "Ortho",
        "slug": "ortho",
        "icon": "bone",
        "description": "Orthopedic, x-ray, fracture, spine, knee, and bone-related reports.",
    },
    {
        "name": "General",
        "slug": "general",
        "icon": "stethoscope",
        "description": "General medical records and reports that do not match a specialist department.",
    },
    {
        "name": "Medicine",
        "slug": "medicine",
        "icon": "pill",
        "description": "Prescriptions, dosage plans, tablets, capsules, and medicine notes.",
    },
    {
        "name": "Lab",
        "slug": "lab",
        "icon": "test-tube",
        "description": "CBC, glucose, hemoglobin, platelet, lipid profile, and blood test reports.",
    },
]

DEPARTMENT_KEYWORDS = {
    "Heart": [
        "ecg",
        "cardiac",
        "troponin",
        "cholesterol",
        "heart",
        "cardiology",
        "blood pressure",
    ],
    "Kidney": ["creatinine", "kidney", "renal", "nephro", "urea", "egfr"],
    "Ortho": ["fracture", "bone", "spine", "knee", "orthopedic", "xray", "x-ray"],
    "Lab": ["cbc", "glucose", "hemoglobin", "haemoglobin", "blood test", "platelet", "lipid profile"],
    "Medicine": ["prescription", "tablet", "capsule", "dosage", "medicine"],
}

STRUCTURED_FIELDS = {
    "patient_name": ["patient name", "name"],
    "age": ["age"],
    "gender": ["gender", "sex"],
    "test": ["test", "investigation", "report"],
    "hemoglobin": ["hemoglobin", "haemoglobin", "hb"],
    "platelets": ["platelets", "platelet", "plt"],
    "glucose": ["glucose", "blood sugar", "sugar", "fbs", "rbs"],
    "creatinine": ["creatinine"],
    "urea": ["urea", "blood urea", "bun"],
    "egfr": ["egfr", "e-gfr"],
    "cholesterol": ["cholesterol", "total cholesterol"],
    "ldl": ["ldl"],
    "hdl": ["hdl"],
    "triglycerides": ["triglycerides", "triglyceride"],
    "troponin": ["troponin"],
    "blood_pressure": ["blood pressure", "bp", "b.p", "b/p"],
    "doctor_notes": ["doctor notes", "advice", "impression", "diagnosis", "remarks"],
    "medicine": ["medicine", "tablet", "capsule", "drug"],
    "dosage": ["dosage", "dose"],
}


class OcrSpaceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def department_slug(name: str) -> str:
    normalized = normalize_department_name(name)
    return next((item["slug"] for item in DEPARTMENTS if item["name"] == normalized), "general")


def normalize_department_name(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()
    aliases = {
        "heart": "Heart",
        "cardiology": "Heart",
        "cardiac": "Heart",
        "kidney": "Kidney",
        "renal": "Kidney",
        "nephrology": "Kidney",
        "ortho": "Ortho",
        "orthopedics": "Ortho",
        "orthopedic": "Ortho",
        "general": "General",
        "general medicine": "General",
        "medicine": "Medicine",
        "prescription": "Medicine",
        "lab": "Lab",
        "laboratory": "Lab",
        "pathology": "Lab",
    }
    return aliases.get(normalized, "General")


def normalize_for_matching(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    normalized = re.sub(r"[^a-z0-9/.\s-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return f" {normalized.strip()} "


def clean_ocr_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    normalized = normalized.replace("\u00a0", " ")
    normalized = re.sub(r"[^\S\n]+", " ", normalized)
    normalized = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]+", " ", normalized)
    normalized = re.sub(r"\s+([:;,])", r"\1", normalized)
    lines = [re.sub(r"\s{2,}", " ", line).strip(" -|") for line in normalized.splitlines()]
    normalized = "\n".join(line for line in lines if line)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def detect_keywords(text: str) -> list[str]:
    normalized = normalize_for_matching(text)
    detected: list[str] = []

    for keywords in DEPARTMENT_KEYWORDS.values():
        for keyword in keywords:
            pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
            if re.search(pattern, normalized) and keyword not in detected:
                detected.append(keyword)

    return detected


def detect_department(text: str, fallback: str | None = None) -> str:
    normalized = normalize_for_matching(text)
    scores: dict[str, int] = {department: 0 for department in DEPARTMENT_KEYWORDS}

    for department, keywords in DEPARTMENT_KEYWORDS.items():
        for keyword in keywords:
            pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
            if re.search(pattern, normalized):
                scores[department] += 1

    best_department, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score > 0:
        return best_department

    return normalize_department_name(fallback)


def snake_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized[:60] or "field"


def find_value_after_alias(line: str, alias: str) -> str | None:
    pattern = re.compile(rf"\b{re.escape(alias)}\b\s*[:\-]?\s*(.+)$", re.IGNORECASE)
    match = pattern.search(line)
    if not match:
        return None
    value = match.group(1).strip(" :-")
    if value.lower() == alias.lower():
        return None
    return value[:160] if value else None


def extract_structured_data(cleaned_text: str) -> dict[str, str]:
    structured: dict[str, str] = {}
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]

    for line in lines:
        colon_match = re.match(r"^([A-Za-z][A-Za-z0-9 /().%-]{1,48})\s*[:\-]\s*(.{1,180})$", line)
        if colon_match:
            key = snake_key(colon_match.group(1))
            value = colon_match.group(2).strip()
            if key not in structured and value:
                structured[key] = value

        for field, aliases in STRUCTURED_FIELDS.items():
            if field in structured:
                continue
            for alias in aliases:
                value = find_value_after_alias(line, alias)
                if value:
                    structured[field] = value
                    break

    compact_text = " ".join(lines)
    for field, aliases in STRUCTURED_FIELDS.items():
        if field in structured:
            continue
        for alias in aliases:
            number_match = re.search(
                rf"\b{re.escape(alias)}\b[^0-9<>+-]{{0,35}}([<>+-]?\s*\d+(?:\.\d+)?(?:\s*[a-zA-Z/%]+)?)",
                compact_text,
                re.IGNORECASE,
            )
            if number_match:
                structured[field] = number_match.group(1).strip()
                break

    return structured


def display_label(key: str) -> str:
    return key.replace("_", " ").strip().title()


def format_report_text(cleaned_text: str, structured_data: dict[str, str]) -> str:
    if not cleaned_text:
        return ""

    preferred_order = [
        "patient_name",
        "age",
        "gender",
        "test",
        "hemoglobin",
        "platelets",
        "glucose",
        "creatinine",
        "urea",
        "egfr",
        "cholesterol",
        "ldl",
        "hdl",
        "triglycerides",
        "troponin",
        "blood_pressure",
        "medicine",
        "dosage",
        "doctor_notes",
    ]

    blocks: list[str] = []
    used_keys: set[str] = set()
    for key in preferred_order:
        value = structured_data.get(key)
        if value:
            blocks.append(f"{display_label(key)}:\n{value}")
            used_keys.add(key)

    for key, value in structured_data.items():
        if key not in used_keys and value:
            blocks.append(f"{display_label(key)}:\n{value}")

    remaining_lines = [
        line
        for line in cleaned_text.splitlines()
        if line.strip() and not any(line.strip() in block for block in blocks)
    ]
    if remaining_lines:
        blocks.append("Readable OCR Text:\n" + "\n".join(remaining_lines[:80]))

    return "\n\n".join(blocks).strip()


def build_summary(department_name: str, structured_data: dict[str, str], cleaned_text: str) -> str:
    findings = []
    for key in ["hemoglobin", "platelets", "glucose", "creatinine", "urea", "egfr", "cholesterol", "troponin"]:
        value = structured_data.get(key)
        if value:
            findings.append(f"{display_label(key)} {value}")

    if findings:
        return f"{department_name} report with extracted findings: {', '.join(findings[:6])}. Verify values against the original report before clinical decisions."

    preview = " ".join(cleaned_text.split())[:220]
    if preview:
        return f"{department_name} report processed by OCR. Preview: {preview}"

    return f"{department_name} report uploaded, but no readable OCR text was extracted."


def parse_error_message(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    if value:
        return str(value)
    return "OCR.Space could not process this file."


def parse_confidence(payload: dict[str, Any]) -> float | None:
    confidences: list[float] = []
    for result in payload.get("ParsedResults") or []:
        if not isinstance(result, dict):
            continue
        value = result.get("MeanConfidence") or result.get("Confidence")
        try:
            if value is not None:
                confidences.append(float(value))
        except (TypeError, ValueError):
            pass

    if confidences:
        confidence = sum(confidences) / len(confidences)
        return confidence / 100 if confidence > 1 else confidence

    exit_code = payload.get("OCRExitCode")
    if exit_code == 1:
        return 0.88
    if exit_code == 2:
        return 0.65
    return None


async def call_ocr_space(file_path: Path, file_name: str) -> tuple[str, float | None]:
    api_key = os.getenv("OCR_SPACE_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise OcrSpaceError("OCR_SPACE_API_KEY is missing. Add it to the backend environment.", 503)

    content_type = mimetypes.guess_type(file_name or file_path.name)[0] or "application/octet-stream"
    timeout_seconds = float(os.getenv("OCR_SPACE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))

    data = {
        "apikey": api_key,
        "language": os.getenv("OCR_SPACE_LANGUAGE", "eng"),
        "OCREngine": os.getenv("OCR_SPACE_ENGINE", "2"),
        "isTable": "true",
        "scale": "true",
        "detectOrientation": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            with file_path.open("rb") as input_file:
                response = await client.post(
                    OCR_SPACE_ENDPOINT,
                    data=data,
                    files={"file": (file_name or file_path.name, input_file, content_type)},
                )
    except httpx.TimeoutException as exc:
        raise OcrSpaceError("OCR.Space timed out while reading the report. Try again with a clearer or smaller file.", 504) from exc
    except httpx.RequestError as exc:
        raise OcrSpaceError("Unable to reach OCR.Space. Check internet connectivity and try again.", 502) from exc

    if response.status_code in {401, 403}:
        raise OcrSpaceError("OCR.Space rejected the API key. Verify OCR_SPACE_API_KEY.", 502)
    if response.status_code == 429:
        raise OcrSpaceError("OCR.Space rate limit reached. Please retry after a short wait.", 429)
    if response.status_code >= 500:
        raise OcrSpaceError("OCR.Space is temporarily unavailable. Please try again.", 502)
    if response.status_code >= 400:
        raise OcrSpaceError(f"OCR.Space request failed with status {response.status_code}.", 502)

    try:
        payload = response.json()
    except ValueError as exc:
        raise OcrSpaceError("OCR.Space returned an invalid response.", 502) from exc

    if payload.get("IsErroredOnProcessing"):
        message = parse_error_message(payload.get("ErrorMessage") or payload.get("ErrorDetails"))
        lowered = message.lower()
        if "api key" in lowered or "apikey" in lowered:
            raise OcrSpaceError("OCR.Space rejected the API key. Verify OCR_SPACE_API_KEY.", 502)
        if "rate" in lowered or "quota" in lowered:
            raise OcrSpaceError("OCR.Space rate limit or quota was reached.", 429)
        raise OcrSpaceError(message, 502)

    parsed_results = payload.get("ParsedResults")
    if not isinstance(parsed_results, list) or not parsed_results:
        raise OcrSpaceError("OCR.Space returned no parsed text for this report.", 422)

    raw_text = "\n\n".join(
        str(result.get("ParsedText") or "").strip()
        for result in parsed_results
        if isinstance(result, dict) and str(result.get("ParsedText") or "").strip()
    )
    if not raw_text.strip():
        raise OcrSpaceError("OCR.Space found no readable text. Try a sharper image or a clearer PDF.", 422)

    return raw_text, parse_confidence(payload)


def build_ocr_result(raw_text: str, file_name: str = "", fallback_department: str | None = None) -> dict[str, Any]:
    cleaned_text = clean_ocr_text(raw_text)
    department_name = detect_department(f"{file_name}\n{cleaned_text}", fallback_department)
    structured_data = extract_structured_data(cleaned_text)
    formatted_text = format_report_text(cleaned_text, structured_data)

    structured_payload: dict[str, Any] = {
        "fields": structured_data,
        "department": department_name,
        "department_slug": department_slug(department_name),
        "detected_keywords": detect_keywords(cleaned_text),
        "source": "ocr_space",
    }
    structured_payload["summary"] = build_summary(department_name, structured_data, cleaned_text)

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "formatted_text": formatted_text,
        "structured_data_json": structured_payload,
        "department_name": department_name,
        "detected_keywords": structured_payload["detected_keywords"],
        "summary": structured_payload["summary"],
    }


async def extract_report_with_ocr_space(
    path: str,
    file_name: str = "",
    fallback_department: str | None = None,
) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise OcrSpaceError("Uploaded report file was not found on the server.", 404)

    raw_text, confidence = await call_ocr_space(file_path, file_name)
    result = build_ocr_result(raw_text, file_name, fallback_department)
    result["confidence"] = confidence
    return result
