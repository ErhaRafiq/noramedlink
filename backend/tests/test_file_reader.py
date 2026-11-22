"""Reading the text out of a file picked on the Summarize page (services/file_reader.py). OCR is faked."""

from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from services import file_reader, local_ocr
from services.local_ocr import OcrText


def upload(name: str, content_type: str, data: bytes) -> UploadFile:
    return UploadFile(BytesIO(data), filename=name, headers=Headers({"content-type": content_type}))


def png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return buffer.getvalue()


ROWS = [
    {
        "page": 1,
        "text": "Hemoglobin 10.2 g/dL 12 - 17",
        "cells": [
            {"text": "Hemoglobin", "score": 0.99},
            {"text": "10.2", "score": 0.97},
            {"text": "g/dL", "score": 0.98},
            {"text": "12 - 17", "score": 0.99},
        ],
    },
    {
        "page": 1,
        "text": "Glucose 8 mg/dL",
        "cells": [{"text": "Glucose", "score": 0.99}, {"text": "8", "score": 0.61}, {"text": "mg/dL", "score": 0.98}],
    },
]


@pytest.mark.anyio
async def test_a_photo_is_read_and_unsure_numbers_are_listed(monkeypatch):
    seen = {}

    def fake(path):
        seen["suffix"] = path.suffix
        seen["existed"] = path.exists()
        seen["path"] = path
        return OcrText("Hemoglobin 10.2 g/dL 12 - 17\nGlucose 8 mg/dL", 0.9, ROWS)

    monkeypatch.setattr(local_ocr, "read_text", fake)
    result = await file_reader.read_upload_text(upload("report.png", "image/png", png()))
    assert result["source"] == "ocr" and "Hemoglobin 10.2" in result["text"] and result["truncated"] is False
    assert result["uncertain_count"] == 1 and "8 (in: Glucose 8 mg/dL)" in result["uncertain"][0]
    assert seen["suffix"] == ".png" and seen["existed"] is True
    assert not seen["path"].exists()  # nothing is kept


@pytest.mark.anyio
async def test_the_temporary_file_is_removed_even_when_reading_fails(monkeypatch):
    seen = {}

    def fake(path):
        seen["path"] = path
        raise local_ocr.LocalOcrError("The OCR model could not be downloaded.")

    monkeypatch.setattr(local_ocr, "read_text", fake)
    with pytest.raises(HTTPException) as error:
        await file_reader.read_upload_text(upload("report.png", "image/png", png()))
    assert error.value.status_code == 503 and not seen["path"].exists()


@pytest.mark.anyio
async def test_a_file_with_no_text_asks_for_a_clearer_photo(monkeypatch):
    monkeypatch.setattr(local_ocr, "read_text", lambda path: OcrText("   ", None, []))
    with pytest.raises(HTTPException) as error:
        await file_reader.read_upload_text(upload("blank.png", "image/png", png()))
    assert error.value.status_code == 422 and "clearer" in error.value.detail


@pytest.mark.anyio
async def test_wrong_types_and_broken_files_are_refused_before_any_reading(monkeypatch):
    def never(path):
        raise AssertionError("OCR must not run")

    monkeypatch.setattr(local_ocr, "read_text", never)
    for name, kind, data in [("a.txt", "text/plain", b"hello"), ("a.png", "image/png", b"not an image")]:
        with pytest.raises(HTTPException) as error:
            await file_reader.read_upload_text(upload(name, kind, data))
        assert error.value.status_code == 400


@pytest.mark.anyio
async def test_a_file_over_the_size_limit_is_refused(monkeypatch):
    from dataclasses import replace

    monkeypatch.setattr(file_reader, "settings", replace(file_reader.settings, max_upload_mb=1))
    with pytest.raises(HTTPException) as error:
        await file_reader.read_upload_text(upload("big.png", "image/png", b"0" * (1024 * 1024 + 5)))
    assert error.value.status_code == 413


@pytest.mark.anyio
async def test_very_long_text_is_cut_and_says_so(monkeypatch):
    monkeypatch.setattr(local_ocr, "read_text", lambda path: OcrText("Glucose 90 mg/dL\n" * 2000, None, []))
    result = await file_reader.read_upload_text(upload("long.png", "image/png", png()))
    assert (
        result["truncated"] is True and len(result["text"]) == file_reader.MAX_TEXT and result["source"] == "text_layer"
    )
