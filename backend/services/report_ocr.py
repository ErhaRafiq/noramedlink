"""Reads a stored report file into the OCR result the report pipeline uses: the local OCR in
services/local_ocr.py (no key; nothing leaves the server). Raises OcrError on failure.
"""

import asyncio
from pathlib import Path
from typing import Any

from services import local_ocr
from services.report_text import OcrError, build_ocr_result

# Local OCR is CPU-heavy: read one file at a time rather than slowing every upload.
_local_slot = asyncio.Semaphore(1)


async def extract_report_text(path: str, file_name: str = "", fallback_department: str | None = None) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_file():
        raise OcrError("Uploaded report file was not found on the server.", 404)
    try:
        async with _local_slot:
            read = await asyncio.to_thread(local_ocr.read_text, file_path)
    except local_ocr.LocalOcrError as exc:
        raise OcrError(str(exc), 503) from exc
    if not read.text.strip():
        raise OcrError("No readable text was found in this file. You can type the text on the report page.", 422)

    result = build_ocr_result(read.text, file_name, fallback_department)
    structured = result["structured_data_json"]
    # Each OCR'd row with its cells' scores (digital PDF pages have none: their text is exact). The
    # text is never changed; the report analysis lists the numbers OCR was unsure of for checking.
    structured["ocr_rows"] = read.rows
    result["confidence"] = read.confidence
    return result
