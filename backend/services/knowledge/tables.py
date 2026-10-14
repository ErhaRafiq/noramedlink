"""The knowledge-base tables: CSV files in services/knowledge/data, read with pandas.

One row per item; list columns hold ";"-separated values ("aliases", "classes"); every row names
its source (sources.csv). DEMO KNOWLEDGE BASE, not a clinical reference: see data/README.md for
each table's data card. The schemas are checked in tests/test_knowledge_data.py (pandera).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent / "data"
LIST_COLUMNS = {
    "medicines": ["aliases", "classes"],
    "brands": ["generics"],
    "allergy_classes": ["classes"],
    "conditions": ["synonyms", "abbreviations"],
    "lab_tests": ["aliases", "row_abbreviations"],
    "plain_terms": ["aliases", "abbreviations"],
}


def split_list(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


@cache
def table(name: str) -> pd.DataFrame:
    """A knowledge-base table, with its list columns as Python lists. Cached: read once."""
    frame = pd.read_csv(DATA / f"{name}.csv", dtype=str, keep_default_na=False)
    for column in LIST_COLUMNS.get(name, []):
        frame[column] = frame[column].map(split_list)
    for column in ("high_alert", "chronic"):
        if column in frame:
            frame[column] = frame[column].str.lower().eq("true")
    return frame


def records(name: str) -> list[dict]:
    return table(name).to_dict("records")
