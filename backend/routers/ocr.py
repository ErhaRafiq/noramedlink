from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from dependencies import require_patient
from models import User
from schemas import OcrOutput
from services.file_service import save_upload_file, stored_path_to_disk_path
from services.ocr_space_service import OcrSpaceError, extract_report_with_ocr_space


router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/extract", response_model=OcrOutput)
async def extract(file: UploadFile = File(...), current_user: User = Depends(require_patient)):
    stored_path, _ = await save_upload_file(file, "ocr-temp", patient_id=current_user.id)
    try:
        result = await extract_report_with_ocr_space(str(stored_path_to_disk_path(stored_path)), file.filename or "")
    except OcrSpaceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    fields = result.get("structured_data_json", {}).get("fields", {})
    return OcrOutput(
        raw_text=str(result.get("raw_text") or ""),
        cleaned_text=str(result.get("cleaned_text") or ""),
        possible_report_type=f"{result.get('department_name') or 'General'} report",
        detected_keywords=[str(keyword) for keyword in result.get("detected_keywords") or []],
        structured_sections={key: str(value) for key, value in fields.items()},
    )
