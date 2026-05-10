from typing import Any

from services.ocr_space_service import (
    build_ocr_result,
    clean_ocr_text,
    detect_department,
    detect_keywords,
)


def detect_report_type(text: str, file_name: str = "") -> str:
    department = detect_department(f"{file_name}\n{text}")
    return f"{department} report"


def format_ocr_output(raw_text: str, file_name: str = "") -> dict[str, Any]:
    result = build_ocr_result(raw_text, file_name)
    fields = result.get("structured_data_json", {}).get("fields", {})
    return {
        "raw_text": raw_text,
        "cleaned_text": result.get("cleaned_text") or clean_ocr_text(raw_text),
        "possible_report_type": detect_report_type(raw_text, file_name),
        "detected_keywords": result.get("detected_keywords") or [],
        "structured_sections": {key: str(value) for key, value in fields.items()} if isinstance(fields, dict) else {},
    }


def extract_ocr_result(path: str, file_name: str = "") -> dict[str, Any]:
    raise RuntimeError(
        "Local OCR is disabled. Use services.ocr_space_service.extract_report_with_ocr_space from an async FastAPI route."
    )
