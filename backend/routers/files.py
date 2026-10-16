"""Authorized access to uploaded report files (replaces the public /uploads mount).

GET /files/{path} with either
- a signed link from an API response (?exp=..&uid=..&sig=..), or
- an Authorization: Bearer token.
Either way the viewer must be the patient who owns the report that refers to the file,
or a doctor with an active dashboard grant for that patient. Files no report refers to
are not served.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db, get_upload_root_path
from dependencies import get_current_user
from models import PatientReport, User
from services import audit
from services.dashboard_access import has_active_grant
from services.file_access import UPLOADS_PREFIX, verify_signed_link

router = APIRouter(tags=["files"])


def _can_view(db: Session, viewer: User, patient_id: int) -> bool:
    role = viewer.role.lower()
    if role == "patient":
        return viewer.id == patient_id
    if role == "doctor":
        return has_active_grant(db, viewer.id, patient_id)
    return False


@router.get("/files/{file_path:path}")
def get_file(
    file_path: str,
    exp: int | None = None,
    uid: int | None = None,
    sig: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    relative = file_path.replace("\\", "/").lstrip("/")
    root = get_upload_root_path().resolve()
    disk_path = (root / relative).resolve()
    if not disk_path.is_relative_to(root) or disk_path == root:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    # Identify the viewer: a valid signed link, else a Bearer token.
    if sig is not None or exp is not None or uid is not None:
        if exp is None or uid is None or sig is None or not verify_signed_link(relative, exp, uid, sig):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="This file link is invalid or has expired."
            )
        viewer = db.get(User, uid)
        if viewer is None or not viewer.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="This file link is invalid or has expired."
            )
    else:
        viewer = get_current_user(authorization=authorization, db=db)

    report = db.query(PatientReport).filter(PatientReport.file_url == UPLOADS_PREFIX + relative).first()
    if report is None or not disk_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    if not _can_view(db, viewer, report.patient_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this file.")
    if viewer.role.lower() == "doctor":
        audit.record(
            db, viewer, "file.view", patient_id=report.patient_id, target_type="report", target_id=report.id,
            once_per=audit.VIEW_WINDOW,
        )  # fmt: skip

    return FileResponse(disk_path, headers={"Cache-Control": "private, no-store"})
