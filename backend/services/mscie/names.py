"""Medicine search for prescribing: generic names, aliases and Pakistani brands, then the drugs known
only to DDInter, with fuzzy matching (rapidfuzz) so a misspelling ("glucophag", "amoxicilin") still
finds the medicine."""

from __future__ import annotations

from functools import cache

from rapidfuzz import fuzz, process

from services.knowledge.tables import records
from services.mscie import ddinter

MIN_SCORE = 75


@cache
def _choices() -> list[dict]:
    """Every searchable name, with what it is."""
    medicines = {row["generic"]: row for row in records("medicines")}
    out = []
    for generic, row in medicines.items():
        for name in [generic, *row["aliases"]]:
            out.append({"name": name, "generic": generic, "brand": None, "classes": row["classes"]})
    for brand in records("brands"):
        classes = sorted({c for g in brand["generics"] for c in medicines[g]["classes"]})
        out.append(
            {
                "name": brand["brand"],
                "generic": " + ".join(brand["generics"]),
                "brand": brand["brand"],
                "classes": classes,
            }
        )
    covered = {c["name"].lower() for c in out} | set(ddinter.names_for(tuple(medicines)))
    for name in sorted(ddinter.drug_names() - covered):  # known only to DDInter: interaction checks only
        out.append({"name": name, "generic": name, "brand": None, "classes": []})
    return out


def search(query: str, limit: int = 10) -> list[dict]:
    """Best matches, exact and prefix matches first, then fuzzy ones (each with its score)."""
    text = " ".join((query or "").lower().split())
    if len(text) < 2:
        return []
    choices = _choices()
    names = [c["name"].lower() for c in choices]
    scored = process.extract(text, names, scorer=fuzz.WRatio, limit=limit * 3)
    results, seen = [], set()
    for _name, score, index in sorted(scored, key=lambda s: (not names[s[2]].startswith(text), -s[1], names[s[2]])):
        if score < MIN_SCORE:
            continue
        choice = choices[index]
        key = (choice["generic"], choice["brand"])
        if key in seen:
            continue
        seen.add(key)
        results.append({**choice, "match": round(score)})
        if len(results) >= limit:
            break
    return results
