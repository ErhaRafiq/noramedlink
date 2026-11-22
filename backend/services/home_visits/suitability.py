"""Which kinds of doctor can see a patient at home (home_visit_suitability.csv, demo knowledge base)."""

from __future__ import annotations

from functools import cache

from services.knowledge.tables import records

FALLBACK = "General Physician"


@cache
def _rows() -> dict[str, dict]:
    return {row["specialty"]: row for row in records("home_visit_suitability")}


def is_suitable(specialty: str | None) -> bool:
    row = _rows().get(specialty or "")
    return bool(row) and row["home_visit"] == "yes"


def suitability(specialty: str | None) -> float:
    """0 to 1; 0 for a specialty that is not for home visits or not in the table."""
    row = _rows().get(specialty or "")
    return float(row["suitability"]) if row and row["home_visit"] == "yes" else 0.0


def note(specialty: str | None) -> str:
    row = _rows().get(specialty or "")
    return row["note"] if row else ""


@cache
def _aliases() -> list[tuple[str, str]]:
    """(alias, specialty name), longest alias first so 'dent' wins over 'ent' for a dentist."""
    pairs = [(row["name"].lower(), row["name"]) for row in records("specialties")]
    pairs += [(alias.lower(), row["name"]) for row in records("specialties") for alias in row["doctor_aliases"]]
    return sorted(pairs, key=lambda p: -len(p[0]))


def specialty_of(listed: str | None) -> str | None:
    """The specialty-table name for what a doctor lists as their specialty, or None if it matches none."""
    text = (listed or "").lower().strip()
    if not text:
        return None
    for alias, name in _aliases():
        if alias == text:
            return name
    for alias, name in _aliases():
        if alias in text:
            return name
    return None
