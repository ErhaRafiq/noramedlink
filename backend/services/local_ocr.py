"""Local OCR: reads report text on this server, with no external service and no API key.

- PDFs: each page's text layer is used when it has one (digital PDFs: exact and instant); pages
  without one (scans) are rendered and read with OCR.
- Images (JPG, PNG, WebP): read with OCR.

OCR is RapidOCR 3 (ONNX Runtime, CPU) with the PP-OCRv5 mobile text detector and the PP-OCRv5
English recogniser. Its boxes are rebuilt into table rows (services/ocr_layout.py), so a test's
value stays on the same line as its name, and each cell keeps its OCR score.

The two models are downloaded once from the RapidOCR model hub, checked against the SHA-256 that
RapidOCR 3.10 publishes for them, and cached in OCR_MODEL_DIR. Pre-fetch them with:

    python -m services.local_ocr --download
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import httpx

from config import BACKEND_DIR, settings
from services import ocr_layout

logger = logging.getLogger("nora.local_ocr")

_HUB = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5"
MODELS = {
    "det": (
        "ch_PP-OCRv5_det_mobile.onnx",  # the multilingual detector (RapidOCR names it "ch")
        f"{_HUB}/det/ch_PP-OCRv5_det_mobile.onnx",
        "4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae",
    ),
    "rec": (
        "en_PP-OCRv5_rec_mobile.onnx",
        f"{_HUB}/rec/en_PP-OCRv5_rec_mobile.onnx",
        "c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8",
    ),
}

MAX_PAGES = 10
RENDER_SCALE = 3.0  # about 216 dpi; lower scales dropped lines in testing
MIN_TEXT_LAYER_CHARS = 30  # fewer usable characters than this: treat the page as a scan


class LocalOcrError(Exception):
    """OCR could not run (model unavailable) or the file could not be opened."""


@dataclass
class OcrText:
    text: str
    confidence: float | None  # mean OCR score; None when no page needed OCR
    rows: list[dict] = field(default_factory=list)  # OCR'd rows with each cell's score


def model_dir() -> Path:
    directory = Path(settings.ocr_model_dir)
    return directory if directory.is_absolute() else BACKEND_DIR / directory


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure(name: str, url: str, sha256: str) -> Path:
    path = model_dir() / name
    if path.exists() and _sha256(path) == sha256:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    logger.info("Downloading the OCR model %s to %s", name, path.parent)
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=180) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
    except httpx.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise LocalOcrError("The OCR model could not be downloaded. Check the internet connection once.") from exc
    if _sha256(partial) != sha256:
        partial.unlink(missing_ok=True)
        raise LocalOcrError("The downloaded OCR model did not match its checksum; it was discarded.")
    partial.replace(path)
    return path


def ensure_models() -> dict[str, Path]:
    """Both models, downloaded and verified on first use."""
    return {kind: _ensure(*spec) for kind, spec in MODELS.items()}


@lru_cache(maxsize=1)
def _engine():
    from rapidocr import LangDet, LangRec, ModelType, OCRVersion, RapidOCR  # loading it takes a moment

    paths = ensure_models()
    return RapidOCR(
        params={
            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Det.lang_type": LangDet.MULTI,
            "Det.model_type": ModelType.MOBILE,
            "Det.model_path": str(paths["det"]),
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.lang_type": LangRec.EN,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.model_path": str(paths["rec"]),
            "Global.use_cls": False,  # reports are upright; the angle classifier is not loaded
            "Global.log_level": "error",
            "EngineConfig.onnxruntime.intra_op_num_threads": -1,
        }
    )


def _ocr_image(image, page: int) -> list[dict]:
    out = _engine()(image.convert("RGB"))
    if out.boxes is None:
        return []
    result = [(box.tolist(), text, score) for box, text, score in zip(out.boxes, out.txts, out.scores, strict=True)]
    return ocr_layout.rebuild(result, page)


def _mean_score(rows: list[dict]) -> float | None:
    scores = [cell["score"] for row in rows for cell in row["cells"]]
    return sum(scores) / len(scores) if scores else None


def read_text(path: Path) -> OcrText:
    """The file's text, its mean OCR confidence and the OCR'd rows.

    PDF: each page's own text layer when it has one, OCR for scanned pages. Word (.docx): its text and
    tables exactly, plus OCR of any pictures (a scan pasted into Word). Images and TIFF (every page):
    OCR, after turning a phone photo upright from its EXIF orientation."""
    try:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return _read_pdf(path)
        if suffix == ".docx":
            return _read_docx(path)
        from PIL import Image

        with Image.open(path) as image:
            rows = _ocr_frames(image)
    except LocalOcrError:
        raise
    except Exception as exc:  # unreadable or corrupt file
        raise LocalOcrError("The file could not be opened for reading.") from exc
    return OcrText("\n".join(row["text"] for row in rows), _mean_score(rows), rows)


def _upright(image):
    from PIL import ImageOps

    return ImageOps.exif_transpose(image)  # phone photos carry their rotation in EXIF


def _ocr_frames(image, first_page: int = 1) -> list[dict]:
    """OCR rows of every frame (a TIFF can hold many pages), up to MAX_PAGES."""
    from PIL import ImageSequence

    rows: list[dict] = []
    for index, frame in enumerate(ImageSequence.Iterator(image)):
        if index >= MAX_PAGES:
            break
        rows.extend(_ocr_image(_upright(frame), first_page + index))
    return rows


def _read_docx(path: Path) -> OcrText:
    import io

    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from PIL import Image

    document = docx.Document(str(path))
    lines: list[str] = []
    for element in document.element.body.iterchildren():
        if element.tag.endswith("}p"):
            text = Paragraph(element, document).text.strip()
            if text:
                lines.append(text)
        elif element.tag.endswith("}tbl"):
            for row in Table(element, document).rows:
                cells = [" ".join(cell.text.split()) for cell in row.cells]
                # merged cells repeat; keep each distinct neighbour once
                kept = [cell for i, cell in enumerate(cells) if cell and (i == 0 or cell != cells[i - 1])]
                if kept:
                    lines.append(" ".join(kept))
    rows: list[dict] = []
    pictures = [part for part in document.part.related_parts.values() if part.content_type.startswith("image/")]
    for number, part in enumerate(pictures[:MAX_PAGES], start=1):
        try:
            with Image.open(io.BytesIO(part.blob)) as picture:
                found = _ocr_frames(picture, number)
        except Exception:  # a picture Pillow cannot read (a vector logo, say) is skipped, not fatal
            continue
        rows.extend(found)
        lines.extend(row["text"] for row in found)
    return OcrText("\n".join(lines), _mean_score(rows), rows)


def _read_pdf(path: Path) -> OcrText:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    pages: list[str] = []
    rows: list[dict] = []
    try:
        for index in range(min(len(pdf), MAX_PAGES)):
            page = pdf[index]
            layer = page.get_textpage().get_text_bounded().strip()
            if len(re.sub(r"\s", "", layer)) >= MIN_TEXT_LAYER_CHARS:
                pages.append(layer)  # a digital page: its own text, exactly
                continue
            page_rows = _ocr_image(page.render(scale=RENDER_SCALE).to_pil(), index + 1)
            pages.append("\n".join(row["text"] for row in page_rows))
            rows.extend(page_rows)
    finally:
        pdf.close()
    text = "\n\n".join(page for page in pages if page.strip())
    return OcrText(text, _mean_score(rows), rows)


if __name__ == "__main__":
    if "--download" in sys.argv:
        for kind, path in ensure_models().items():
            print(f"OCR {kind} model ready: {path}")
    else:
        print(__doc__)
