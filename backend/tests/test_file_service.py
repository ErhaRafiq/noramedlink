"""Upload validation and storage paths (services/file_service.py)."""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from services import file_service
from services.file_service import (
    sanitize_path_segment,
    save_upload_file,
    stored_path_to_disk_path,
    validate_stored_file,
    validate_upload,
)


def upload(name: str, content_type: str, data: bytes = b"") -> UploadFile:
    return UploadFile(BytesIO(data), filename=name, headers=Headers({"content-type": content_type}))


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Heart", "heart"),
        ("../../etc", "etc"),
        ("a b/c", "abc"),
        ("", "general"),
        ("..", "general"),
        ("lab_2-x", "lab_2-x"),
    ],
)
def test_path_segments_cannot_escape(value, expected):
    assert sanitize_path_segment(value) == expected


@pytest.mark.parametrize(
    ("name", "content_type", "suffix"),
    [("scan.PDF", "application/pdf", ".pdf"), ("photo.jpg", "image/jpeg", ".jpg"), ("x.webp", "image/webp", ".webp")],
)
def test_allowed_uploads(name, content_type, suffix):
    assert validate_upload(upload(name, content_type)) == suffix


@pytest.mark.parametrize(
    ("name", "content_type"),
    [
        ("script.exe", "application/octet-stream"),
        ("report.pdf", "text/html"),
        ("image.png.html", "image/png"),
        ("noext", "image/png"),
    ],
)
def test_rejected_uploads(name, content_type):
    with pytest.raises(HTTPException) as caught:
        validate_upload(upload(name, content_type))
    assert caught.value.status_code == 400


def test_file_contents_must_match_the_type(tmp_path: Path):
    good_pdf = tmp_path / "good.pdf"
    good_pdf.write_bytes(b"%PDF-1.7\n...")
    validate_stored_file(good_pdf, ".pdf")

    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"<html>not a pdf</html>")
    with pytest.raises(HTTPException):
        validate_stored_file(fake_pdf, ".pdf")
    assert not fake_pdf.exists()  # rejected files are deleted

    fake_png = tmp_path / "fake.png"
    fake_png.write_bytes(b"not an image")
    with pytest.raises(HTTPException):
        validate_stored_file(fake_png, ".png")
    assert not fake_png.exists()


@pytest.fixture
def upload_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "uploads"
    monkeypatch.setattr(file_service, "get_upload_root_path", lambda: root)
    return root


@pytest.mark.anyio
async def test_save_stores_under_patient_and_department(upload_root: Path):
    stored, file_type = await save_upload_file(upload("scan.png", "image/png", png_bytes()), "Heart", patient_id=7)
    assert file_type == "png"
    assert stored.startswith("uploads/7/heart/") and stored.endswith(".png")
    assert stored_path_to_disk_path(stored).read_bytes() == png_bytes()


@pytest.mark.anyio
async def test_save_rejects_files_over_the_limit(upload_root: Path, monkeypatch: pytest.MonkeyPatch):
    from dataclasses import replace

    monkeypatch.setattr(file_service, "settings", replace(file_service.settings, max_upload_mb=1))
    big = b"%PDF-" + b"0" * (1024 * 1024 + 10)
    with pytest.raises(HTTPException) as caught:
        await save_upload_file(upload("big.pdf", "application/pdf", big), "lab", patient_id=7)
    assert caught.value.status_code == 413
    assert not any(p.is_file() for p in upload_root.rglob("*"))  # partial file removed


def heic_bytes() -> bytes:
    import pillow_heif

    buffer = BytesIO()
    pillow_heif.from_pillow(Image.new("RGB", (16, 16), "white")).save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("content_type", ["image/heic", "image/heif", "application/octet-stream", ""])
def test_heic_photos_are_accepted_whatever_type_the_browser_sends(content_type: str):
    assert validate_upload(upload("IMG_0001.HEIC", content_type)) == ".heic"


def test_an_unrelated_type_is_still_refused_for_a_heic_name():
    with pytest.raises(HTTPException):
        validate_upload(upload("IMG_0001.heic", "text/html"))
    with pytest.raises(HTTPException):
        validate_upload(upload("notes.txt", "application/octet-stream"))


@pytest.mark.anyio
async def test_a_heic_photo_is_stored_as_a_jpeg(upload_root: Path):
    stored, file_type = await save_upload_file(
        upload("IMG_0001.heic", "image/heic", heic_bytes()), "general", patient_id=7
    )
    assert file_type == "jpg" and stored.endswith(".jpg")
    on_disk = stored_path_to_disk_path(stored)
    with Image.open(on_disk) as image:
        assert image.format == "JPEG" and image.size == (16, 16)
    assert not list(on_disk.parent.glob("*.heic"))  # the original is gone


@pytest.mark.anyio
async def test_a_broken_heic_file_is_refused(upload_root: Path):
    with pytest.raises(HTTPException) as error:
        await save_upload_file(upload("IMG_0002.heic", "image/heic", b"not a photo"), "general", patient_id=7)
    assert error.value.status_code == 400
