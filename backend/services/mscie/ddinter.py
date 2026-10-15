"""DDInter 2.0 drug-drug interactions: the second source behind the curated rules.

160,000 rated pairs among about 1,900 drugs (ddinter.scbdd.com, CC BY-NC-SA 4.0; built by
scripts/ddinter_import/build.py). The curated table (interactions.csv) comes first: it says what
happens and what to do. DDInter only says that a pair interacts and how severely, so its alerts are
used when no curated rule covers the pair. A pair DDInter rates "unknown" is shown as moderate
(caution), never as no interaction. Lookups are a dictionary keyed by the sorted pair, built once.
"""

from __future__ import annotations

from functools import cache
from itertools import product

import pandas as pd

from services.knowledge.tables import DATA, records

SOURCE = "DDINTER"
SEVERITY = {"major": "major", "moderate": "moderate", "minor": "minor", "unknown": "moderate"}
RANK = {"minor": 1, "unknown": 2, "moderate": 2, "major": 3}
MANAGEMENT = {
    "major": "Avoid the combination, or use it only with close monitoring. Check the mechanism in a full drug reference.",
    "moderate": "Use with caution and monitor; check the mechanism in a full drug reference.",
    "minor": "Usually manageable; be aware of it.",
    "unknown": "Check the mechanism in a full drug reference before prescribing.",
}


@cache
def _pairs() -> dict[str, str]:
    frame = pd.read_csv(DATA / "ddinter_interactions.csv.gz", dtype=str, keep_default_na=False)
    return dict(zip(frame["drug_a"] + "|" + frame["drug_b"], frame["level"], strict=True))


@cache
def drug_names() -> frozenset[str]:
    return frozenset(name for key in _pairs() for name in key.split("|"))


@cache
def _mapped() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for row in records("ddinter_names"):
        out.setdefault(row["generic"], []).append(row["ddinter"])
    return {generic: tuple(names) for generic, names in out.items()}


def names_for(generics: tuple[str, ...]) -> list[str]:
    """DDInter's names for a medicine: the mapped name(s) of a curated medicine, or its own name."""
    names: list[str] = []
    for generic in generics:
        names.extend(_mapped().get(generic) or ((generic,) if generic in drug_names() else ()))
    return names


def known_name(name: str) -> str | None:
    """The DDInter name for a medicine typed in full (case and spacing ignored), if DDInter has it."""
    normalized = " ".join((name or "").lower().split())
    return normalized if normalized in drug_names() else None


def interaction(item: tuple[str, ...], other: tuple[str, ...]) -> tuple[str, str, str] | None:
    """The most severe DDInter level between two medicines, with the two names it was found under."""
    found = None
    for a, b in product(names_for(item), names_for(other)):
        level = _pairs().get(f"{a}|{b}" if a < b else f"{b}|{a}")
        if level and (found is None or RANK[level] > RANK[found[0]]):
            found = (level, a, b)
    return found


def effect(level: str, a: str, b: str) -> str:
    graded = "does not grade its severity (shown as moderate)" if level == "unknown" else f"rates it {level}"
    return f"DDInter lists an interaction between {a} and {b} and {graded}. It gives no mechanism here."
