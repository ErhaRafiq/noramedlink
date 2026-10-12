"""Local OCR: reads report text on this server, with no external service and no API key.

- PDFs: each page's text layer is used when it has one (digital PDFs, instant); pages
  without one (scans) are rendered and read with OCR.
- Images (JPG, PNG, WebP): read with OCR.

OCR is RapidOCR (ONNX Runtime, CPU) with its English recognition model, which keeps the
spaces between words (the bundled Chinese/English model drops them in English text).
That model is downloaded once from the RapidOCR model hub, checked against a fixed
SHA-256, and cached in OCR_MODEL_DIR. Pre-fetch it with:

    python -m services.local_ocr --download
"""

import hashlib
import logging
import re
import sys
from functools import lru_cache
from pathlib import Path

import httpx

from config import BACKEND_DIR, settings

logger = logging.getLogger("nora.local_ocr")

MODEL_NAME = "en_PP-OCRv3_rec_infer.onnx"
MODEL_URL = f"https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv3/{MODEL_NAME}"
MODEL_SHA256 = "ef7abd8bd3629ae57ea2c28b425c1bd258a871b93fd2fe7c433946ade9b5d9ea"

MAX_PAGES = 10
RENDER_SCALE = 3.0  # about 216 dpi; lower scales dropped lines in testing
MIN_TEXT_LAYER_CHARS = 30  # fewer usable characters than this: treat the page as a scan
MIN_LINE_SCORE = 0.5

# The detector also "reads" logos and stamps; keep only characters a report in English uses.
_UNEXPECTED_CHARS = re.compile(r"[^\x20-\x7E\n°±µ×μ–—‘’“”]")


class LocalOcrError(Exception):
    """OCR could not run (model unavailable) or the file could not be opened."""


def model_path() -> Path:
    directory = Path(settings.ocr_model_dir)
    if not directory.is_absolute():
        directory = BACKEND_DIR / directory
    return directory / MODEL_NAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model() -> Path:
    """The recognition model, downloaded and verified on first use."""
    path = model_path()
    if path.exists() and _sha256(path) == MODEL_SHA256:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    logger.info("Downloading the OCR recognition model (about 9 MB) to %s", path.parent)
    try:
        with httpx.stream("GET", MODEL_URL, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
    except httpx.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise LocalOcrError("The OCR model could not be downloaded. Check the internet connection once.") from exc
    if _sha256(partial) != MODEL_SHA256:
        partial.unlink(missing_ok=True)
        raise LocalOcrError("The downloaded OCR model did not match its checksum; it was discarded.")
    partial.replace(path)
    return path


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR  # imported here: loading it takes a moment

    return RapidOCR(rec_model_path=str(ensure_model()), intra_op_num_threads=-1)


def _ocr_image(image) -> tuple[list[str], list[float]]:
    result, _elapsed = _engine()(image.convert("RGB"), use_cls=False)  # reports are upright
    lines, scores = [], []
    for _box, text, score in result or []:
        cleaned = " ".join(_UNEXPECTED_CHARS.sub("", text).split())
        if cleaned and float(score) >= MIN_LINE_SCORE:
            lines.append(cleaned)
            scores.append(float(score))
    return lines, scores


def read_text(path: Path) -> tuple[str, float | None]:
    """The file's text and the mean OCR confidence (None when no page needed OCR)."""
    try:
        if path.suffix.lower() == ".pdf":
            return _read_pdf(path)
        from PIL import Image

        with Image.open(path) as image:
            lines, scores = _ocr_image(image)
    except LocalOcrError:
        raise
    except Exception as exc:  # unreadable or corrupt file
        raise LocalOcrError("The file could not be opened for reading.") from exc
    return "\n".join(lines), (sum(scores) / len(scores) if scores else None)


def _read_pdf(path: Path) -> tuple[str, float | None]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    pages: list[str] = []
    scores: list[float] = []
    try:
        for index in range(min(len(pdf), MAX_PAGES)):
            page = pdf[index]
            layer = page.get_textpage().get_text_bounded().strip()
            if len(re.sub(r"\s", "", layer)) >= MIN_TEXT_LAYER_CHARS:
                pages.append(layer)
                continue
            lines, page_scores = _ocr_image(page.render(scale=RENDER_SCALE).to_pil())
            pages.append("\n".join(lines))
            scores.extend(page_scores)
    finally:
        pdf.close()
    text = "\n\n".join(page for page in pages if page.strip())
    return text, (sum(scores) / len(scores) if scores else None)


if __name__ == "__main__":
    if "--download" in sys.argv:
        print("OCR model ready:", ensure_model())
    else:
        print(__doc__)
