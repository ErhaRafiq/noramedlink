"""PMDC registration numbers: the format check at signup and the check against the PMDC public register.

What was verified (read from pmdc.pk, not assumed): the register's search is a free, open POST to
`hospitals-inspections.pmdc.pk/api/DRC/GetData` with `RegistrationNo`; it answers `{status, data: [{RegistrationNo,
Name, FatherName, Status}], message}`. It matches the number exactly in the form `12345-P` (digits, a hyphen, one
letter): "12345P", "12345/P" and "12345" find nothing. Numbers seen use the letters P, N, S and D with four or five
digits; PMDC publishes no format document, so any single letter is accepted and the digits run from 3 to 7.
Status values seen: `ACTIVE` and `In Active`.

Rules (the register is public data, but we are a guest on it):
- Only the registration number is sent. Nothing about the doctor or any patient.
- Only an administrator triggers a check (and approval does one best-effort), never signup, never a patient.
- A check never blocks anything. A doctor can be approved and active without being PMDC verified; a verified
  one gets a badge. `pmdc_verified` is true only for: found, ACTIVE, and the register's name matches the
  doctor's name, or an administrator's written decision.
- If the register cannot be reached nothing is changed and nobody is told "not verified".
- No medical text, no number in the logs.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from config import settings
from models import DoctorProfile, User
from schemas import PmdcStatusOut
from services import audit, notifications

log = logging.getLogger("nora.pmdc")

EXAMPLE = "12345-P"
FORMAT_HELP = (
    "Enter the registration number as it is printed on your PMDC certificate: digits, a dash and a letter, "
    f"for example {EXAMPLE}."
)
REGISTER_URL = "https://pmdc.pk/"  # the human page: "Search for Any Doctor ... by Registration Number"

# Words people put in front of the number.
_PREFIX = re.compile(r"^(?:(?:PM\s*&\s*DC|PM\s*AND\s*DC|PMDC|PMC|REGISTRATION|REGD?|NUMBER|NO|NUM|ID)\b[\s.:#/\-]*)+")
_NUMBER = re.compile(r"^([0-9]{3,7})\s*[-/\s]?\s*([A-Z])$")  # ASCII digits only
_DASHES = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-"})


def normalize_registration(raw: str | None) -> str | None:
    """The number in the form the register searches on ("12345-P"), or None when it does not fit.

    Accepts the usual ways of writing it: any case, spaces, "12345P", "12345/P", "12345 - p", a leading
    "PMDC", "PM&DC", "PMC", "Reg No." and the like. Leading zeros are dropped, as the register has none.
    """
    text = " ".join((raw or "").translate(_DASHES).upper().split())
    text = _PREFIX.sub("", text).strip(" .:#")
    match = _NUMBER.match(text)
    if not match:
        return None
    digits = str(int(match.group(1)))  # the register has no leading zeros
    if not 3 <= len(digits) <= 7:  # counted after the zeros go, so the result always normalises to itself
        return None
    return f"{digits}-{match.group(2)}"


class PmdcError(Exception):
    """Base for the two ways a lookup can not give an answer."""


class PmdcDisabled(PmdcError):
    """The lookup is switched off on this server (PMDC_LOOKUP_ENABLED, or a test run)."""


class PmdcUnavailable(PmdcError):
    """The register did not answer properly (down, slow, or an unexpected reply)."""


@dataclass(frozen=True)
class PmdcRecord:
    registration_no: str
    name: str
    status: str  # as the register words it: "ACTIVE", "In Active"


def lookup(registration_no: str, post: Callable[..., httpx.Response] = httpx.post) -> PmdcRecord | None:
    """The register's entry for this exact number, or None when it lists nobody under it."""
    if not settings.pmdc_lookup_enabled:
        raise PmdcDisabled
    try:
        response = post(
            settings.pmdc_lookup_url,
            data={"RegistrationNo": registration_no, "Name": "", "FatherName": ""},
            headers={"User-Agent": "NoraMedLink academic prototype (doctor verification)"},
            timeout=settings.pmdc_lookup_timeout,
            follow_redirects=False,
        )
        if response.status_code != 200:
            raise PmdcUnavailable
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PmdcUnavailable from exc
    if not isinstance(body, dict) or body.get("status") is not True or not isinstance(body.get("data") or [], list):
        raise PmdcUnavailable
    for row in body.get("data") or []:
        if isinstance(row, dict) and normalize_registration(str(row.get("RegistrationNo", ""))) == registration_no:
            return PmdcRecord(
                registration_no=registration_no,
                name=" ".join(str(row.get("Name") or "").split())[:160],
                status=" ".join(str(row.get("Status") or "").split())[:40],
            )
    return None


_TITLES = {"dr", "doctor", "prof", "professor", "mr", "mrs", "ms", "miss", "syed", "sayyed"}


# Spellings of the commonest names that differ between a certificate and a sign-up form.
_ALIASES = {
    "mohammad": "muhammad", "mohammed": "muhammad", "muhammed": "muhammad", "mohd": "muhammad", "md": "muhammad",
    "mohamed": "muhammad", "ahmed": "ahmad",
}  # fmt: skip


def _name_tokens(name: str) -> list[str]:
    cleaned = re.sub(r"[^a-z\s]", " ", (name or "").lower())
    return [_ALIASES.get(t, t) for t in cleaned.split() if t not in _TITLES]


def names_match(register_name: str, doctor_name: str) -> bool:
    """Whether the register's name is the doctor's name, allowing spelling differences and a missing middle name.

    Every word of the shorter name must have a counterpart (about 88% alike) in the longer one, and at least two
    words must match unless a name has only one. The registration number is already unique, so this only guards
    against a typo or a borrowed number; it is not an identity check, and an administrator can decide by hand."""
    a, b = _name_tokens(register_name), _name_tokens(doctor_name)
    if not a or not b:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    matched = 0
    for token in short:
        if any(fuzz.ratio(token, other) >= 88 for other in long_):
            matched += 1
    return matched == len(short) and (matched >= 2 or (len(short) == 1 and len(long_) == 1))


OUTCOMES = {
    "verified": "The register lists this number as ACTIVE under the doctor's name.",
    "inactive": "The register lists this number, but not as ACTIVE.",
    "name_mismatch": "The register lists this number under a different name.",
    "not_found": "The register does not list this number.",
    "format_invalid": "The number is not in a form the register can search (digits, a dash and a letter, like 12345-P).",
    "manual": "An administrator decided by hand.",
}


def check_doctor(
    profile: DoctorProfile,
    doctor_name: str,
    checked_by_id: int | None,
    lookup_fn: Callable[[str], PmdcRecord | None] = lookup,
) -> str:
    """Ask the register about the doctor's number and record the answer. Returns the outcome.

    Raises PmdcDisabled or PmdcUnavailable without touching the profile. The caller commits."""
    number = normalize_registration(profile.pmdc_number)
    if number is None:
        record, outcome = None, "format_invalid"
    else:
        record = lookup_fn(number)  # may raise: then nothing below runs
        if record is None:
            outcome = "not_found"
        elif record.status.strip().lower() != "active":
            outcome = "inactive"
        elif not names_match(record.name, doctor_name):
            outcome = "name_mismatch"
        else:
            outcome = "verified"
    profile.pmdc_outcome = outcome
    profile.pmdc_verified = outcome == "verified"
    profile.pmdc_checked_at = datetime.now(UTC)
    profile.pmdc_checked_by_id = checked_by_id
    profile.pmdc_register_name = record.name if record else None
    profile.pmdc_register_status = record.status if record else None
    profile.pmdc_note = None
    log.info("PMDC check finished: %s", outcome)
    return outcome


def set_by_hand(profile: DoctorProfile, verified: bool, note: str, admin_id: int) -> None:
    """An administrator's own decision (for example after checking pmdc.pk themselves), with the reason."""
    profile.pmdc_verified = verified
    profile.pmdc_outcome = "manual"
    profile.pmdc_checked_at = datetime.now(UTC)
    profile.pmdc_checked_by_id = admin_id
    profile.pmdc_note = note.strip()[:300]


def status_out(profile: DoctorProfile, names: dict[int, str] | None = None) -> PmdcStatusOut:
    """What an administrator sees: the number, whether it can be searched, and the last result."""
    searchable = normalize_registration(profile.pmdc_number)
    if profile.pmdc_checked_at is None:
        message = "Not checked yet."
    elif profile.pmdc_outcome == "manual":
        message = f"An administrator decided by hand: {profile.pmdc_note or 'no note'}"
    else:
        message = OUTCOMES.get(profile.pmdc_outcome or "", "Checked.")
    return PmdcStatusOut(
        number=profile.pmdc_number,
        searchable=searchable,
        format_ok=searchable is not None,
        verified=profile.pmdc_verified,
        outcome=profile.pmdc_outcome,
        message=message,
        register_name=profile.pmdc_register_name,
        register_status=profile.pmdc_register_status,
        checked_at=profile.pmdc_checked_at,
        checked_by_name=(names or {}).get(profile.pmdc_checked_by_id) if profile.pmdc_checked_by_id else None,
        note=profile.pmdc_note,
    )


def run_check(db: Session, profile: DoctorProfile, admin: User) -> str:
    """check_doctor for the doctor's account, written to the audit log and committed. Raises as check_doctor does."""
    doctor = db.get(User, profile.user_id)
    was_verified = profile.pmdc_verified
    outcome = check_doctor(profile, doctor.full_name if doctor else "", admin.id)
    if profile.pmdc_verified != was_verified:
        notifications.doctor_pmdc_changed(db, profile.user_id, profile.pmdc_verified)
    audit.record(
        db, admin, "admin.pmdc_check", target_type="doctor_profile", target_id=profile.id, detail=outcome, commit=False
    )
    db.commit()
    db.refresh(profile)
    return outcome
