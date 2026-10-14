"""Schema checks for the CSV knowledge bases (pandera): columns, types, uniqueness, formats and
cross-references, so a bad row fails here instead of at runtime."""

import pandas as pd
import pandera as pa
import pytest

from services.knowledge.tables import DATA, table

SOURCES = set(pd.read_csv(DATA / "sources.csv", dtype=str)["key"])
NON_EMPTY = pa.Check.str_length(min_value=1)
BOOL_TEXT = pa.Check.isin(["True", "False"])


def cites_a_source(value: str) -> bool:
    return any(value.startswith(key) for key in SOURCES)


RAW_SCHEMAS = {
    "sources": pa.DataFrameSchema(
        {"key": pa.Column(str, NON_EMPTY, unique=True), "description": pa.Column(str, NON_EMPTY)}, strict=True
    ),
    "medicines": pa.DataFrameSchema(
        {
            "generic": pa.Column(str, [NON_EMPTY, pa.Check(lambda s: s == s.str.lower())], unique=True),
            "aliases": pa.Column(str),
            "atc": pa.Column(str, pa.Check.str_matches(r"^([A-Z]\d{2}[A-Z]{0,2}\d{0,2})?$")),
            "classes": pa.Column(str, NON_EMPTY),
            "high_alert": pa.Column(str, BOOL_TEXT),
            "source": pa.Column(str, pa.Check(lambda s: s.map(cites_a_source))),
        },
        strict=True,
    ),
    "brands": pa.DataFrameSchema(
        {
            "brand": pa.Column(str, NON_EMPTY, unique=True),
            "generics": pa.Column(str, NON_EMPTY),
            "source": pa.Column(str, pa.Check(lambda s: s.map(cites_a_source))),
        },
        strict=True,
    ),
    "allergy_classes": pa.DataFrameSchema(
        {"allergy_word": pa.Column(str, NON_EMPTY, unique=True), "classes": pa.Column(str, NON_EMPTY)}, strict=True
    ),
    "conditions": pa.DataFrameSchema(
        {
            "name": pa.Column(str, NON_EMPTY, unique=True),
            "synonyms": pa.Column(str, NON_EMPTY),
            "abbreviations": pa.Column(str),
            "icd10": pa.Column(str, pa.Check.str_matches(r"^[A-Z]\d{2}(\.\d)?(-[A-Z]\d{2}(\.\d)?)?$")),
            "chronic": pa.Column(str, BOOL_TEXT),
            "source": pa.Column(str, pa.Check.isin(sorted(SOURCES))),
        },
        strict=True,
    ),
    "lab_tests": pa.DataFrameSchema(
        {
            "name": pa.Column(str, NON_EMPTY, unique=True),
            "aliases": pa.Column(str),
            "row_abbreviations": pa.Column(str),
            "panel": pa.Column(
                str,
                pa.Check.isin(
                    [
                        "CBC",
                        "Glucose",
                        "Kidney",
                        "Electrolytes",
                        "Liver",
                        "Lipid",
                        "Thyroid",
                        "Cardiac",
                        "Vitals",
                        "Other",
                    ]
                ),
            ),
        },
        strict=True,
    ),
    "plain_terms": pa.DataFrameSchema(
        {
            "aliases": pa.Column(str),
            "abbreviations": pa.Column(str),
            "plain": pa.Column(str, NON_EMPTY),
            "explain": pa.Column(str, pa.Check.str_matches(r".+\.$")),
            "source": pa.Column(str, pa.Check.isin(sorted(SOURCES))),
        },
        strict=True,
    ),
}


@pytest.mark.parametrize("name", sorted(RAW_SCHEMAS))
def test_every_table_matches_its_schema(name):
    RAW_SCHEMAS[name].validate(pd.read_csv(DATA / f"{name}.csv", dtype=str, keep_default_na=False), lazy=True)


def test_every_brand_maps_to_known_generics():
    generics = set(table("medicines")["generic"])
    unknown = {g for row in table("brands")["generics"] for g in row} - generics
    assert unknown == set()


def test_no_name_is_claimed_by_two_medicines():
    names = [n.lower() for _, row in table("medicines").iterrows() for n in [row["generic"], *row["aliases"]]]
    names += [b.lower() for b in table("brands")["brand"]]
    assert len(names) == len(set(names))


def test_each_plain_term_entry_has_a_name_to_match():
    frame = table("plain_terms")
    assert all(row["aliases"] or row["abbreviations"] for _, row in frame.iterrows())
