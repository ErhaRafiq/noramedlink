"""Reads a stored report file into the OCR result the report pipeline uses.

OCR.space is used when OCR_SPACE_API_KEY is set; otherwise the local OCR in
services/local_ocr.py (no key, nothing leaves the server). Both produce the same result
shape (build_ocr_result) and raise OcrError on failure.
"""

import asyncio
from pathlib import Path
from typing import Any

from config import settings
from services import local_ocr
from services.ocr_space_service import OcrError, build_ocr_result, extract_report_with_ocr_space

# Local OCR is CPU-heavy: read one file at a time rather than slowing every upload.
_local_slot = asyncio.Semaphore(1)


async def extract_report_text(path: str, file_name: str = "", fallback_department: str | None = None) -> dict[str, Any]:
    if settings.ocr_space_api_key:
        return await extract_report_with_ocr_space(path, file_name, fallback_department)

    file_path = Path(path)
    if not file_path.is_file():
        raise OcrError("Uploaded report file was not found on the server.", 404)
    try:
        async with _local_slot:
            text, confidence = await asyncio.to_thread(local_ocr.read_text, file_path)
    except local_ocr.LocalOcrError as exc:
        raise OcrError(str(exc), 503) from exc
    if not text.strip():
        raise OcrError("No readable text was found in this file. You can type the text on the report page.", 422)

    result = build_ocr_result(text, file_name, fallback_department)
    result["structured_data_json"]["source"] = "local_ocr"
    result["confidence"] = confidence
    return result
