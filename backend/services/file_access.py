"""Access to uploaded report files.

Files are no longer served publicly. GET /files/{path} serves a file only if a report
refers to it and the viewer is the owning patient or a doctor with an active grant.

Browsers cannot send a Bearer token for <img> or CSS backgrounds, so authorized API
responses include a short-lived signed link: files/<path>?exp=..&uid=..&sig=..
The signature binds the path, expiry and viewer; the viewer's right to the file is
checked again on every request, so ending a doctor's grant stops their links at once.
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode

from auth import get_jwt_secret

LINK_LIFETIME_SECONDS = 10 * 60
UPLOADS_PREFIX = "uploads/"


def _key() -> bytes:
    # Derived from the JWT secret, but distinct from it.
    return hashlib.sha256(b"nora-file-links:" + get_jwt_secret().encode()).digest()


def _signature(relative_path: str, expires: int, viewer_id: int) -> str:
    message = f"{relative_path}\n{expires}\n{viewer_id}".encode()
    return hmac.new(_key(), message, hashlib.sha256).hexdigest()


def relative_upload_path(file_url: str | None) -> str | None:
    """'uploads/12/heart/x.png' -> '12/heart/x.png'; None for empty or data: URLs."""
    value = (file_url or "").replace("\\", "/").lstrip("/")
    if not value.startswith(UPLOADS_PREFIX):
        return None
    return value[len(UPLOADS_PREFIX):]


def file_access_url(file_url: str | None, viewer_id: int) -> str | None:
    """Link the viewer can use directly (relative to the API base). Legacy embedded data:
    images are returned unchanged; reports without a file give None."""
    if file_url and file_url.startswith("data:"):
        return file_url
    relative = relative_upload_path(file_url)
    if relative is None:
        return None
    expires = int(time.time()) + LINK_LIFETIME_SECONDS
    query = urlencode({"exp": expires, "uid": viewer_id, "sig": _signature(relative, expires, viewer_id)})
    return f"files/{relative}?{query}"


def verify_signed_link(relative_path: str, expires: int, viewer_id: int, signature: str) -> bool:
    if expires < int(time.time()):
        return False
    return hmac.compare_digest(_signature(relative_path, expires, viewer_id), signature)
