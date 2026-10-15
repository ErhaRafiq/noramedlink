"""Build the DDInter tables used by the medication-safety engine (MSCIE).

Source: DDInter 2.0, http://ddinter.scbdd.com (Xiong G. et al., Nucleic Acids Res 2022 and 2025),
licensed CC BY-NC-SA 4.0: academic, non-commercial use with attribution; the derived tables keep
that licence (see backend/services/knowledge/data/README.md).

1. Download the published files (eight ATC groups) into scripts/ddinter_import/raw/ (git-ignored):
     http://ddinter.scbdd.com/static/media/download/ddinter_downloads_code_<A|B|D|H|L|P|R|V>.csv
2. Run from the repo root:  backend\\venv\\Scripts\\python.exe scripts\\ddinter_import\\build.py

Writes, in backend/services/knowledge/data/:
- ddinter_interactions.csv.gz: one row per drug pair (names lower-case, a < b), DDInter's level
  (major, moderate, minor or unknown). No interaction text: DDInter's download has none.
- ddinter_names.csv: for each medicine in medicines.csv, the DDInter name(s) it corresponds to
  (same name, an alias, a different international name, or the parts of a combination).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "scripts" / "ddinter_import" / "raw"
DATA = ROOT / "backend" / "services" / "knowledge" / "data"
GROUPS = "ABDHLPRV"

# Our name -> DDInter's name(s), where neither the name nor an alias matches.
OVERRIDES = {
    "aspirin": ["acetylsalicylic acid"],
    "glyceryl trinitrate": ["nitroglycerin"],
    "colecalciferol": ["cholecalciferol"],
    "ferrous sulfate": ["ferrous sulfate anhydrous"],
    "insulin": ["insulin human"],
    "amoxicillin and clavulanic acid": ["amoxicillin", "clavulanic acid"],
}


def load_pairs() -> pd.DataFrame:
    files = [RAW / f"ddinter_downloads_code_{group}.csv" for group in GROUPS]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        sys.exit(f"Missing downloads in {RAW}: {', '.join(missing)}")
    raw = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)
    a = raw["Drug_A"].str.strip().str.lower()
    b = raw["Drug_B"].str.strip().str.lower()
    pairs = pd.DataFrame(
        {"drug_a": a.where(a < b, b), "drug_b": b.where(a < b, a), "level": raw["Level"].str.strip().str.lower()}
    )
    pairs = pairs[pairs["drug_a"] != pairs["drug_b"]].drop_duplicates()
    conflicts = pairs.duplicated(["drug_a", "drug_b"], keep=False)
    if conflicts.any():
        sys.exit(f"{int(conflicts.sum())} pairs have more than one level; check the download.")
    unexpected = set(pairs["level"]) - {"major", "moderate", "minor", "unknown"}
    if unexpected:
        sys.exit(f"Unexpected levels: {sorted(unexpected)}")
    return pairs.sort_values(["drug_a", "drug_b"]).reset_index(drop=True)


def name_map(names: set[str]) -> pd.DataFrame:
    medicines = pd.read_csv(DATA / "medicines.csv", dtype=str, keep_default_na=False)
    rows = []
    for _, medicine in medicines.iterrows():
        generic = medicine["generic"]
        candidates = OVERRIDES.get(generic) or [generic, *[x.strip().lower() for x in medicine["aliases"].split(";") if x.strip()]]
        found = [c for c in candidates if c in names]
        if generic in OVERRIDES and len(found) != len(OVERRIDES[generic]):
            sys.exit(f"Override for {generic} names something DDInter does not have: {OVERRIDES[generic]}")
        for ddinter in found[: len(OVERRIDES.get(generic, [])) or 1]:
            rows.append({"generic": generic, "ddinter": ddinter})
    return pd.DataFrame(rows)


def main() -> None:
    pairs = load_pairs()
    names = set(pairs["drug_a"]) | set(pairs["drug_b"])
    mapping = name_map(names)
    pairs.to_csv(DATA / "ddinter_interactions.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    mapping.to_csv(DATA / "ddinter_names.csv", index=False)
    medicines = pd.read_csv(DATA / "medicines.csv", dtype=str)
    print(f"{len(pairs)} pairs among {len(names)} drugs: {pairs['level'].value_counts().to_dict()}")
    print(f"{mapping['generic'].nunique()} of {len(medicines)} curated medicines matched to DDInter names")
    print("not in DDInter:", ", ".join(sorted(set(medicines["generic"]) - set(mapping["generic"]))))


if __name__ == "__main__":
    main()
