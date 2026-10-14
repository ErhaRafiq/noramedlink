"""Schema checks for the CSV knowledge bases (pandera): columns, types, uniqueness, formats and
cross-references, so a bad row fails here instead of at runtime."""

import re

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


# --- Module 4 (MSCIE) tables -------------------------------------------------------------------

SEVERITIES = ["contraindicated", "major", "moderate", "minor"]
GENERICS = set(table("medicines")["generic"])
CLASSES = {c for row in table("medicines")["classes"] for c in row}


def known_reference(value: str) -> bool:
    """A generic in medicines.csv, or "class:<a class one of them has>"."""
    if value.startswith("class:"):
        return value.removeprefix("class:") in CLASSES
    return value in GENERICS


def raw(name):
    return pd.read_csv(DATA / f"{name}.csv", dtype=str, keep_default_na=False)


def cites(series):
    """Every ";"-separated source (outside brackets) starts with a key from sources.csv."""
    return series.map(lambda v: all(cites_a_source(part.strip()) for part in re.split(r";(?![^()]*\))", v)))


MSCIE_SCHEMAS = {
    "interactions": pa.DataFrameSchema(
        {
            "id": pa.Column(str, pa.Check.str_matches(r"^DDI-\d{3}$"), unique=True),
            "a": pa.Column(str, pa.Check(lambda s: s.map(known_reference))),
            "b": pa.Column(str, pa.Check(lambda s: s.map(known_reference))),
            "severity": pa.Column(str, pa.Check.isin(SEVERITIES)),
            "effect": pa.Column(str, NON_EMPTY),
            "management": pa.Column(str, NON_EMPTY),
            "source": pa.Column(str, pa.Check(cites)),
        },
        strict=True,
    ),
    "contraindications": pa.DataFrameSchema(
        {
            "id": pa.Column(str, pa.Check.str_matches(r"^CI-\d{3}$"), unique=True),
            "drug": pa.Column(str, pa.Check(lambda s: s.map(known_reference))),
            "exclude": pa.Column(str, pa.Check(lambda s: s.map(lambda v: not v or v in GENERICS))),
            "condition": pa.Column(
                str, pa.Check(lambda s: s.map(lambda v: not v or v in set(table("conditions")["name"])))
            ),
            "lab_test": pa.Column(str),
            "lab_operator": pa.Column(str, pa.Check.isin(["", "<", ">"])),
            "lab_value": pa.Column(str, pa.Check.str_matches(r"^(\d+(\.\d+)?)?$")),
            "severity": pa.Column(str, pa.Check.isin(SEVERITIES)),
            "effect": pa.Column(str, NON_EMPTY),
            "management": pa.Column(str, NON_EMPTY),
            "source": pa.Column(str, pa.Check(cites)),
        },
        strict=True,
    ),
    "allergy_cross_reactivity": pa.DataFrameSchema(
        {
            "id": pa.Column(str, pa.Check.str_matches(r"^AX-\d{3}$"), unique=True),
            "allergy_class": pa.Column(str, pa.Check.isin(sorted(CLASSES | {"sulfonamide"}))),
            "target": pa.Column(str, pa.Check(lambda s: s.map(known_reference))),
            "severity": pa.Column(str, pa.Check.isin(SEVERITIES)),
            "effect": pa.Column(str, NON_EMPTY),
            "management": pa.Column(str, NON_EMPTY),
            "source": pa.Column(str, pa.Check(cites)),
        },
        strict=True,
    ),
    "dose_limits": pa.DataFrameSchema(
        {
            "generic": pa.Column(str, pa.Check.isin(sorted(GENERICS)), unique=True),
            "max_single_mg": pa.Column(str, pa.Check.str_matches(r"^(\d+(\.\d+)?)?$")),
            "max_daily_mg": pa.Column(str, pa.Check.str_matches(r"^\d+(\.\d+)?$")),
            "usual_frequency": pa.Column(str, pa.Check.isin(["OD", "BD", "TDS", "QID"])),
            "source": pa.Column(str, pa.Check(cites)),
        },
        strict=True,
    ),
    "duplicate_classes": pa.DataFrameSchema(
        {
            "class": pa.Column(str, pa.Check.isin(sorted(CLASSES)), unique=True),
            "severity": pa.Column(str, pa.Check.isin(SEVERITIES)),
            "effect": pa.Column(str, NON_EMPTY),
            "source": pa.Column(str, pa.Check(cites)),
        },
        strict=True,
    ),
    "alternatives": pa.DataFrameSchema(
        {
            "for_drug": pa.Column(str, pa.Check(lambda s: s.map(known_reference))),
            "alternative": pa.Column(str, pa.Check.isin(sorted(GENERICS))),
            "use": pa.Column(str, NON_EMPTY),
            "reason": pa.Column(str, NON_EMPTY),
            "source": pa.Column(str, pa.Check(cites)),
        },
        strict=True,
    ),
}


@pytest.mark.parametrize("name", sorted(MSCIE_SCHEMAS))
def test_every_mscie_table_matches_its_schema(name):
    MSCIE_SCHEMAS[name].validate(raw(name), lazy=True)


def test_lab_thresholds_name_tests_the_lab_rules_know():
    from services.lab_rules import RULES

    tests = {t for t in raw("contraindications")["lab_test"] if t}
    assert tests <= set(RULES)


def test_ranking_weights_sum_to_one():
    weights = pd.to_numeric(raw("ranking_weights")["weight"])
    assert abs(weights.sum() - 1.0) < 1e-9 and (weights > 0).all()


def test_dose_limits_single_never_exceeds_daily():
    frame = raw("dose_limits")
    with_single = frame[frame["max_single_mg"] != ""]
    assert (pd.to_numeric(with_single["max_single_mg"]) <= pd.to_numeric(with_single["max_daily_mg"])).all()
