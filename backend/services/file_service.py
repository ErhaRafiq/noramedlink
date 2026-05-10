import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from database import get_upload_root_path


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf"}
DEFAULT_MAX_UPLOAD_MB = 10


def get_upload_root() -> Path:
    root = get_upload_root_path()
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_path_segment(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum() or ch in {"-", "_"}) or "general"


def validate_upload(file: UploadFile) -> str:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, JPEG, PNG, and PDF medical reports are supported.",
        )
    return suffix


def validate_stored_file(path: Path, suffix: str) -> None:
    try:
        if suffix == ".pdf":
            with path.open("rb") as input_file:
                if input_file.read(5) != b"%PDF-":
                    raise ValueError("Invalid PDF signature.")
            return

        with Image.open(path) as image:
            image.verify()
    except (OSError, UnidentifiedImageError, ValueError):
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded report appears corrupted or is not a readable file.",
        )


async def save_upload_file(file: UploadFile, category: str, patient_id: int | str | None = None) -> tuple[str, str]:
    suffix = validate_upload(file)
    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", str(DEFAULT_MAX_UPLOAD_MB)))
    max_upload_bytes = max_upload_mb * 1024 * 1024
    category_dir = sanitize_path_segment(category)
    patient_dir = sanitize_path_segment(str(patient_id)) if patient_id is not None else "shared"
    upload_dir = get_upload_root() / patient_dir / category_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}{suffix}"
    stored_path = upload_dir / stored_name
    total_size = 0

    with stored_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > max_upload_bytes:
                output.close()
                stored_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds the {max_upload_mb} MB upload limit.",
                )
            output.write(chunk)

    validate_stored_file(stored_path, suffix)
    public_path = Path("uploads") / patient_dir / category_dir / stored_name
    return public_path.as_posix(), suffix.lstrip(".")


def stored_path_to_disk_path(stored_file_path: str) -> Path:
    stored_path = Path(stored_file_path)
    if stored_path.is_absolute():
        return stored_path

    normalized = stored_file_path.replace("\\", "/").lstrip("/")
    if normalized.startswith("uploads/"):
        return get_upload_root() / normalized.removeprefix("uploads/")

    return get_upload_root().parent / normalized
