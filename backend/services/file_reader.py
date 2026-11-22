"""Reads the text out of a file the user picks on the Summarize page, without keeping the file.

The file goes to a temporary folder, is checked like a report upload (type, size, readable), read with the same
local OCR as reports (nothing leaves the server), and is deleted before the answer is sent. The reader gets the
text back to check and correct before asking for a summary, with the numbers the OCR was unsure of listed.
"""

import asyncio
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from config import settings
from services import local_ocr
from services.file_service import validate_stored_file, validate_upload
from services.ocr_layout import uncertain_values
from services.report_ocr import _local_slot
from services.report_text import clean_ocr_text

MAX_TEXT = 20000  # the Summarize page's own limit
MAX_UNCERTAIN_SHOWN = 12


async def read_upload_text(file: UploadFile) -> dict:
    suffix = validate_upload(file)
    limit = settings.max_upload_mb * 1024 * 1024
    with tempfile.TemporaryDirectory(prefix="nora-read-") as folder:
        path = Path(folder) / f"upload{suffix}"
        size = 0
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
                    )
                output.write(chunk)
        validate_stored_file(path, suffix)
        try:
            async with _local_slot:  # OCR is CPU-heavy: one file at a time
                read = await asyncio.to_thread(local_ocr.read_text, path)
        except local_ocr.LocalOcrError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    text = clean_ocr_text(read.text).strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No readable text was found in this file. Try a clearer, well-lit photo of the flat page, "
            "or the original PDF.",
        )
    unsure = uncertain_values(text, read.rows)
    return {
        "text": text[:MAX_TEXT],
        "truncated": len(text) > MAX_TEXT,
        "source": "ocr" if read.rows else "text_layer",
        "confidence": read.confidence,
        "uncertain": [f"{item['text']} (in: {item['line'][:60]})" for item in unsure[:MAX_UNCERTAIN_SHOWN]],
        "uncertain_count": len(unsure),
    }
