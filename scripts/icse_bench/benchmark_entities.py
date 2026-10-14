"""Entity extraction benchmark for the clinical summary (ICSE FE-1). Synthetic data only.

1. Narrative reports (icse_samples/, from generate_patients.py): precision, recall and F1 per
   entity type, with the rules and knowledge base alone and with BioBERT suggestions added.
2. Lab tables read by OCR (ocr_samples/_results/<engine>/): test results found with the right
   value, with a wrong value, or missed, against the exact ground truth.

    $env:HF_HUB_OFFLINE="1"; backend\\venv\\Scripts\\python.exe scripts\\icse_bench\\benchmark_entities.py
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services import knowledge  # noqa: E402
from services.biobert_service import extract_medical_entities  # noqa: E402
from services.icse.entities import extract_entities  # noqa: E402

TYPES = ["test_result", "medication", "condition", "allergy", "allergy_status"]


def key(entity: dict) -> tuple:
    kind, name = entity["type"], str(entity["name"]).lower()
    if kind == "test_result":
        return kind, name, entity.get("value")
    if kind == "medication":
        return kind, name, entity.get("status", "mentioned")
    if kind == "condition":
        return kind, name, bool(entity.get("negated"))
    return kind, name


def score(truth: list[dict], predicted: list[dict], totals: dict, attributes: Counter) -> None:
    expected = Counter(key(e) for e in truth if e["type"] in TYPES)
    found = Counter(key(e) for e in predicted if e["type"] in TYPES)
    for item in expected | found:
        hit = min(expected[item], found[item])
        totals[item[0]]["tp"] += hit
        totals[item[0]]["fn"] += expected[item] - hit
        totals[item[0]]["fp"] += found[item] - hit
    # Attributes of matched entities: dose and frequency of medicines, unit and flag of results.
    by_key = defaultdict(list)
    for entity in predicted:
        if entity["type"] in TYPES:
            by_key[key(entity)].append(entity)
    for entity in truth:
        matches = by_key.get(key(entity))
        if not matches:
            continue
        match = matches.pop(0)
        for field in ("dose", "frequency", "unit", "report_flag"):
            if field in entity and entity[field] is not None:
                attributes[f"{field} checked"] += 1
                attributes[f"{field} right"] += match.get(field) == entity[field]


def table(totals: dict) -> list[str]:
    lines = [
        "| Type | Expected | Found right | Wrong (extra) | Missed | Precision | Recall | F1 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    all_counts = Counter()
    for kind in TYPES:
        counts = totals[kind]
        all_counts.update(counts)
        lines.append(row(kind, counts))
    lines.append(row("**all**", all_counts))
    return lines


def row(label: str, c) -> str:
    tp, fp, fn = c["tp"], c["fp"], c["fn"]
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * p * r / (p + r) if p + r else 0
    return f"| {label} | {tp + fn} | {tp} | {fp} | {fn} | {p:.1%} | {r:.1%} | {f1:.1%} |"


async def narrative() -> list[str]:
    folders = sorted(p for p in (ROOT / "icse_samples").glob("icse-p*") if p.is_dir())
    if not folders:
        raise SystemExit("Run scripts/icse_bench/generate_patients.py first.")
    runs = {"rules + knowledge base": defaultdict(Counter), "with BioBERT suggestions": defaultdict(Counter)}
    attributes = Counter()
    out_of_kb = Counter()
    suggestions = Counter()
    biobert_source = Counter()
    reports = 0
    for folder in folders:
        for item in json.loads((folder / "entities.json").read_text(encoding="utf-8")):
            text = (folder / item["file"]).read_text(encoding="utf-8")
            reports += 1
            plain = extract_entities(text)
            biobert, meta = await extract_medical_entities(text)
            biobert_source[meta.get("source")] += 1
            with_model = extract_entities(text, biobert)
            score(item["entities"], plain, runs["rules + knowledge base"], attributes)
            score(item["entities"], with_model, runs["with BioBERT suggestions"], Counter())
            for entity in with_model:
                if entity["method"] == "biobert":
                    suggestions[entity["type"]] += 1
            for missing in item["out_of_knowledge_base"]:
                out_of_kb["present"] += 1
                names = {str(e["name"]).lower() for e in with_model}
                if missing["name"].lower() in names:
                    out_of_kb["found by BioBERT"] += 1

    lines = [f"## 1. Narrative reports ({reports} synthetic reports, {len(folders)} patients)", ""]
    lines.append(f"BioBERT ran as: {dict(biobert_source)}")
    for name, totals in runs.items():
        lines += ["", f"### {name}", "", *table(totals)]
    lines += ["", "Attributes of entities found right (rules + knowledge base):", ""]
    for field in ("dose", "frequency", "unit", "report_flag"):
        checked = attributes[f"{field} checked"]
        if checked:
            lines.append(f"- {field}: {attributes[f'{field} right']}/{checked}")
    lines += [
        "",
        f"BioBERT suggestions added (all labelled 'model suggestion', low confidence): {dict(suggestions)}",
        f"Out-of-knowledge-base conditions and free-text medicines: {out_of_kb['present']} present, "
        f"{out_of_kb['found by BioBERT']} found by BioBERT (the rules cannot find them by design).",
    ]
    return lines


async def handwritten() -> list[str]:
    """Harder phrasing, written by hand: the generator and the extractor share an author, so the
    generated set alone would flatter the rules."""
    data = json.loads((Path(__file__).parent / "handwritten.json").read_text(encoding="utf-8"))
    runs = {"rules + knowledge base": defaultdict(Counter), "with BioBERT suggestions": defaultdict(Counter)}
    errors = []
    for item in data["reports"]:
        plain = extract_entities(item["text"])
        biobert, _ = await extract_medical_entities(item["text"])
        score(item["entities"], plain, runs["rules + knowledge base"], Counter())
        score(item["entities"], extract_entities(item["text"], biobert), runs["with BioBERT suggestions"], Counter())
        expected = Counter(key(e) for e in item["entities"])
        found = Counter(key(e) for e in plain if e["type"] in TYPES)
        errors += [f"- {item['id']} missed: {k}" for k in expected - found]
        errors += [f"- {item['id']} extra: {k}" for k in found - expected]
    lines = [f"## 1b. Hand-written harder phrasing ({len(data['reports'])} snippets)"]
    for name, totals in runs.items():
        lines += ["", f"### {name}", "", *table(totals)]
    return [*lines, "", "Errors (rules + knowledge base):", "", *(errors or ["- none"])]


def ocr_tables() -> list[str]:
    samples = ROOT / "ocr_samples"
    results = samples / "_results"
    if not results.exists():
        return ["## 2. OCR lab tables", "", "Skipped: run scripts/ocr_bench/benchmark.py first."]
    lines = [
        "## 2. Test results from OCR text (ocr_samples, exact ground truth)",
        "",
        "| Engine | Variant | Expected | Right value | Wrong value | Unreadable ([?]) | Missed |",
        "|---|---|---|---|---|---|---|",
    ]
    truth = {}
    for path in sorted(samples.glob("*.values.csv")):
        rows = []
        for item in csv.DictReader(path.open(encoding="utf-8")):
            found = knowledge.find_lab_tests(item["test"])
            if found:
                rows.append((found[0].info.name, item["value"]))
        truth[path.name.removesuffix(".values.csv")] = rows
    for engine in ("current", "rows_v5"):
        for variant in ("digital", "scan", "scan_hard"):
            counts = Counter()
            for stem, rows in truth.items():
                path = results / engine / f"{stem}__{variant}.txt"
                if not path.exists():
                    continue
                readings = defaultdict(list)
                for entity in extract_entities(path.read_text(encoding="utf-8")):
                    if entity["type"] == "test_result":
                        readings[entity["name"]].append(entity)
                for name, value in rows:
                    counts["expected"] += 1
                    got = readings.get(name, [])
                    values = [e["value"] for e in got if e["readable"]]
                    if any(_same(v, value) for v in values):
                        counts["right"] += 1
                    elif values:
                        counts["wrong"] += 1
                    elif got:
                        counts["unreadable"] += 1
                    else:
                        counts["missed"] += 1
            if counts["expected"]:
                lines.append(
                    f"| {engine} | {variant} | {counts['expected']} | {counts['right']} | {counts['wrong']} | {counts['unreadable']} | {counts['missed']} |"
                )
    return lines


def _same(found: str, expected: str) -> bool:
    try:
        return float(found.replace(",", "").lstrip("<>")) == float(expected.replace(",", "").lstrip("<>"))
    except ValueError:
        return found == expected


def main() -> None:
    lines = [
        "# ICSE entity benchmark (synthetic data only)",
        "",
        *asyncio.run(narrative()),
        "",
        *asyncio.run(handwritten()),
        "",
        *ocr_tables(),
    ]
    report = "\n".join(lines) + "\n"
    out = ROOT / "icse_samples" / "_entity_results.md"
    out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
