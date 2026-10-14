"""Reading a prescribed dose and frequency ("500 mg", "1 g"; "BD", "1+0+1", "every 8 hours")."""

from __future__ import annotations

import re

_DOSE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(mg|g|gm|mcg|µg|ug)\b", re.IGNORECASE)
_TO_MG = {"mg": 1.0, "g": 1000.0, "gm": 1000.0, "mcg": 0.001, "µg": 0.001, "ug": 0.001}
TIMES_PER_DAY = {
    "OD": 1, "ONCE DAILY": 1, "ONCE A DAY": 1, "HS": 1, "AT NIGHT": 1, "AT BEDTIME": 1, "STAT": 1,
    "BD": 2, "BID": 2, "TWICE DAILY": 2, "TWICE A DAY": 2,
    "TDS": 3, "TID": 3, "THRICE DAILY": 3, "THREE TIMES A DAY": 3,
    "QID": 4, "QDS": 4, "FOUR TIMES A DAY": 4,
}  # fmt: skip
AS_NEEDED = {"PRN", "SOS", "AS NEEDED", "WHEN NEEDED", "WHEN REQUIRED"}


def dose_mg(dose: str | None) -> float | None:
    """A single dose in mg, or None when it is not a plain mass (units, ml, a range)."""
    match = _DOSE.match(dose or "")
    if not match:
        return None
    return float(match.group(1)) * _TO_MG[match.group(2).lower()]


def times_per_day(frequency: str | None) -> int | None:
    """How many doses a day; None when as needed or unknown (only the single dose is checked)."""
    text = " ".join((frequency or "").upper().split())
    if not text or text in AS_NEEDED:
        return None
    if text in TIMES_PER_DAY:
        return TIMES_PER_DAY[text]
    pattern = re.fullmatch(r"(\d)\s*\+\s*(\d)\s*\+\s*(\d)", text)  # "1+0+1": morning, noon, night
    if pattern:
        return sum(int(part) for part in pattern.groups())
    every = re.fullmatch(r"(?:EVERY|Q)\s*(\d{1,2})\s*(?:HOURS?|HRS?|H)", text)
    if every and 0 < int(every.group(1)) <= 24:
        return 24 // int(every.group(1))
    return None
