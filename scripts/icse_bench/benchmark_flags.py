"""Flag benchmark for the clinical summary (ICSE FE-3). Synthetic data only.

The flag rules are tested case by case in backend/tests/test_icse_flags.py. This measures what
reaches the doctor end to end: flags built from what the extractor read, against flags built
from the exact ground truth by the same rules. A difference is a flag gained or lost through
reading, never a question of which rule is right.

1. Synthetic patients (icse_samples/): every flag kind, across several dated reports.
2. OCR lab tables (ocr_samples/): result flags from OCR text against the printed values.

    backend\\venv\\Scripts\\python.exe scripts\\icse_bench\\benchmark_flags.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services import knowledge  # noqa: E402
from services.icse.entities import extract_entities  # noqa: E402
from services.icse.flags import build_flags, printed_date  # noqa: E402


def truth_entity(entity: dict) -> dict:
    """A ground-truth entity in the extractor's shape, with what the knowledge base adds."""
    out = {"method": "rules", "certainty": "mentioned in report", "readable": True, "confidence": None, **entity}
    if entity["type"] == "medication":
        info = knowledge.resolve_medication(entity["name"])
        out |= {"high_alert": bool(info and info.high_alert), "known": info is not None, "negated": False}
    if entity["type"] == "condition":
        mention = knowledge.find_conditions(entity["name"])
        info = mention[0].info if mention else None
        out |= {"chronic": bool(info and info.chronic), "icd10": info.icd10 if info else None}
    return out


def flag_keys(result: dict) -> Counter:
    keys = Counter()
    for flag in result["flags"]:
        values = tuple(sorted(str(s.get("value", s.get("medicine"))) for s in flag["sources"]))
        keys[(flag["code"], flag["subject"].lower(), flag["severity"], values)] += 1
    for check in result["check_original"]:
        keys[("CHECK_ORIGINAL", check["subject"].lower(), "INFO", ())] += 1
    return keys


def compare(expected: Counter, found: Counter, totals: Counter, kinds: Counter, errors: list, label: str) -> None:
    for key in expected | found:
        hit = min(expected[key], found[key])
        totals["right"] += hit
        totals["missed"] += expected[key] - hit
        totals["extra"] += found[key] - hit
        kinds[key[0]] += expected[key]
        if expected[key] != found[key]:
            errors.append(f"- {label}: {key[0]} {key[1]} {key[3]} expected {expected[key]}, got {found[key]}")


def patients() -> list[str]:
    folders = sorted(p for p in (ROOT / "icse_samples").glob("icse-p*") if p.is_dir())
    if not folders:
        raise SystemExit("Run scripts/icse_bench/generate_patients.py first.")
    totals, kinds, errors = Counter(), Counter(), []
    for folder in folders:
        read, truth = [], []
        for index, item in enumerate(json.loads((folder / "entities.json").read_text(encoding="utf-8"))):
            entities = extract_entities((folder / item["file"]).read_text(encoding="utf-8"))
            read.append({"report_id": index, "date": printed_date(entities), "entities": entities})
            truth.append(
                {"report_id": index, "date": item["date"], "entities": [truth_entity(e) for e in item["entities"]]}
            )
        compare(flag_keys(build_flags(truth)), flag_keys(build_flags(read)), totals, kinds, errors, folder.name)
    expected = totals["right"] + totals["missed"]
    return [
        f"## 1. Synthetic patients ({len(folders)} patients, all their reports)",
        "",
        "| Flags expected | Same flag, same values | Missed | Extra |",
        "|---|---|---|---|",
        f"| {expected} | {totals['right']} | {totals['missed']} | {totals['extra']} |",
        "",
        "Expected flags by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()) if v),
        "",
        "Differences:",
        "",
        *(errors or ["- none"]),
    ]


def ocr_tables() -> list[str]:
    samples = ROOT / "ocr_samples"
    results = samples / "_results"
    if not results.exists():
        return ["## 2. OCR lab tables", "", "Skipped: run scripts/ocr_bench/benchmark.py first."]
    lines = [
        "## 2. Result flags from OCR text (ocr_samples, one report each)",
        "",
        "| Engine | Variant | Flags expected | Right | Missed | Wrong (extra) | Shown to check |",
        "|---|---|---|---|---|---|---|",
    ]
    truth = {}
    for path in sorted(samples.glob("*.values.csv")):
        entities = []
        for row in csv.DictReader(path.open(encoding="utf-8")):
            found = knowledge.find_lab_tests(row["test"])
            if found:
                entities.append(
                    truth_entity(
                        {"type": "test_result", "name": found[0].info.name, "value": row["value"], "unit": row["unit"]}
                    )
                )
        truth[path.name.removesuffix(".values.csv")] = build_flags(
            [{"report_id": 1, "date": None, "entities": entities}]
        )
    for engine in ("current", "rows_v5"):
        for variant in ("digital", "scan", "scan_hard"):
            totals, checks, expected_count = Counter(), 0, 0
            for stem, expected in truth.items():
                path = results / engine / f"{stem}__{variant}.txt"
                if not path.exists():
                    continue
                found = build_flags(
                    [{"report_id": 1, "date": None, "entities": extract_entities(path.read_text(encoding="utf-8"))}]
                )
                checks += len(found["check_original"])
                want = Counter(k for k in flag_keys(expected).elements() if k[0] != "CHECK_ORIGINAL")
                got = Counter(k for k in flag_keys(found).elements() if k[0] != "CHECK_ORIGINAL")
                expected_count += sum(want.values())
                compare(want, got, totals, Counter(), [], stem)
            if expected_count:
                lines.append(
                    f"| {engine} | {variant} | {expected_count} | {totals['right']} | {totals['missed']} | {totals['extra']} | {checks} |"
                )
    return lines


def main() -> None:
    report = "\n".join(["# ICSE flag benchmark (synthetic data only)", "", *patients(), "", *ocr_tables()]) + "\n"
    (ROOT / "icse_samples" / "_flag_results.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
