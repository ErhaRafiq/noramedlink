"""Local OCR (services/local_ocr.py) and the choice of OCR engine (services/report_ocr.py).

The OCR engine is replaced with a fake, so these tests need no model download.
"""

from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from services import local_ocr, report_ocr
from services.ocr_space_service import OcrError


class FakeEngine:
    def __init__(self, lines):
        self.lines = lines
        self.calls = 0

    def __call__(self, image, use_cls=True):
        self.calls += 1
        return [([[0, 0], [1, 0], [1, 1], [0, 1]], text, score) for text, score in self.lines], [0.0, 0.0, 0.0]


@pytest.fixture
def fake_engine(monkeypatch: pytest.MonkeyPatch):
    def install(lines):
        engine = FakeEngine(lines)
        monkeypatch.setattr(local_ocr, "_engine", lambda: engine)
        return engine

    return install


def png(tmp_path: Path) -> Path:
    path = tmp_path / "scan.png"
    Image.new("RGB", (40, 40), "white").save(path)
    return path


# A one-page PDF with a text layer ("Hemoglobin 10.8 g/dL ..."), written by hand.
TEXT_PDF = b"""%PDF-1.4
1 0 obj <</Type/Catalog/Pages 2 0 R>> endobj
2 0 obj <</Type/Pages/Kids[3 0 R]/Count 1>> endobj
3 0 obj <</Type/Page/Parent 2 0 R/MediaBox[0 0 400 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>> endobj
4 0 obj <</Length 88>> stream
BT /F1 12 Tf 20 150 Td (Hemoglobin 10.8 g/dL. Platelets 230. Glucose 95 mg/dL.) Tj ET
endstream endobj
5 0 obj <</Type/Font/Subtype/Type1/BaseFont/Helvetica>> endobj
trailer <</Root 1 0 R>>
%%EOF
"""


def test_image_lines_are_joined_and_cleaned(tmp_path, fake_engine):
    fake_engine([("Hemoglobin 10.8 g/dL", 0.98), ("IDC 鑫品 IMAGING", 0.9), ("smudge", 0.2)])
    text, confidence = local_ocr.read_text(png(tmp_path))
    assert text == "Hemoglobin 10.8 g/dL\nIDC IMAGING"  # logo characters dropped; low-score line skipped
    assert confidence == pytest.approx(0.94)


def test_pdf_text_layer_is_used_without_ocr(tmp_path, fake_engine):
    engine = fake_engine([("should not be used", 0.99)])
    path = tmp_path / "digital.pdf"
    path.write_bytes(TEXT_PDF)
    text, confidence = local_ocr.read_text(path)
    assert "Hemoglobin 10.8 g/dL" in text
    assert engine.calls == 0 and confidence is None


def test_unreadable_file_is_a_local_ocr_error(tmp_path, fake_engine):
    fake_engine([])
    path = tmp_path / "broken.png"
    path.write_bytes(b"not an image")
    with pytest.raises(local_ocr.LocalOcrError):
        local_ocr.read_text(path)


def test_a_model_with_the_wrong_checksum_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(local_ocr, "settings", replace(local_ocr.settings, ocr_model_dir=str(tmp_path)))

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def raise_for_status(self):
            pass

        def iter_bytes(self):
            yield b"tampered model"

    monkeypatch.setattr(local_ocr.httpx, "stream", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(local_ocr.LocalOcrError, match="checksum"):
        local_ocr.ensure_model()
    assert not any(tmp_path.iterdir())  # nothing left behind


@pytest.mark.anyio
async def test_local_ocr_is_used_without_an_ocr_space_key(tmp_path, fake_engine):
    fake_engine([("Hemoglobin 10.8 g/dL", 0.97)])
    result = await report_ocr.extract_report_text(str(png(tmp_path)), "scan.png", None)
    assert result["structured_data_json"]["source"] == "local_ocr"
    assert "Hemoglobin 10.8" in result["cleaned_text"] and result["confidence"] == pytest.approx(0.97)


@pytest.mark.anyio
async def test_no_text_found_is_an_error_not_an_empty_report(tmp_path, fake_engine):
    fake_engine([])
    with pytest.raises(OcrError) as caught:
        await report_ocr.extract_report_text(str(png(tmp_path)), "scan.png", None)
    assert caught.value.status_code == 422


@pytest.mark.anyio
async def test_ocr_space_is_used_when_a_key_is_set(tmp_path, monkeypatch):
    monkeypatch.setattr(report_ocr, "settings", replace(report_ocr.settings, ocr_space_api_key="test-key"))
    called = {}

    async def fake_ocr_space(path, file_name="", fallback_department=None):
        called["path"] = path
        return {"source": "ocr_space"}

    monkeypatch.setattr(report_ocr, "extract_report_with_ocr_space", fake_ocr_space)
    assert await report_ocr.extract_report_text(str(png(tmp_path)), "scan.png") == {"source": "ocr_space"}
    assert called["path"].endswith("scan.png")
