"""OCR benchmark: measures OCR engines on ocr_samples/ against exact ground truth.

Run with the benchmark virtualenv (see requirements.txt next to this file):

    .venv-ocr-bench\\Scripts\\python.exe scripts\\ocr_bench\\benchmark.py
    .venv-ocr-bench\\Scripts\\python.exe scripts\\ocr_bench\\benchmark.py --engines current --variants digital,scan

For every sample variant (<base>__digital.pdf, __scan.pdf, __scan_hard.pdf, __photo_*.jpg) and
engine it records:

- CER and WER: edit distance against <base>.txt, after removing page markers and table pipes
  and collapsing whitespace. Case-sensitive (units such as mg/dL matter).
- Word F1: order-independent word overlap (tables read in another order are not punished twice).
- Key values (<base>.values.csv), at three levels:
    text      the test name, number and unit can be read correctly from the OCR text
    extractor the app's structured-field extractor (extract_structured_data) gives that number
    rules     the safety rules' value reader (lab_ranges.read_value) gives that number
  Each value is "correct", "missing" or "WRONG" (test found, different number). Wrong numbers
  are the dangerous outcome and are counted separately.
- Seconds per page on this CPU, with model loading done before timing.

Writes ocr_samples/_results/<engine>/<sample>.txt (the OCR text), results.csv and summary.md.
The "current" engine is the app's own pipeline (backend/services/local_ocr.py), so the baseline
measures exactly what an upload goes through.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from rapidfuzz.distance import Levenshtein

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "ocr_samples"
RESULTS = SAMPLES / "_results"
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

VARIANT_PATTERN = re.compile(
    r"^(?P<base>.+?)__(?P<variant>digital|scan_hard|scan|photo[^.]*)\.(?:pdf|jpe?g|png)$", re.I
)


# --- engines ------------------------------------------------------------------------------------


class Engine:
    name = "engine"

    def available(self) -> tuple[bool, str]:
        return True, ""

    def warm_up(self) -> None:
        """Load models before timing."""

    def read(self, path: Path) -> tuple[str, float | None]:
        raise NotImplementedError


class CurrentPipeline(Engine):
    """The app as it is: PDF text layer first, else RapidOCR (services/local_ocr.py)."""

    name = "current"

    def warm_up(self) -> None:
        from services import local_ocr

        local_ocr._engine()

    def read(self, path: Path) -> tuple[str, float | None]:
        from services import local_ocr

        return local_ocr.read_text(path)


ENGINES: dict[str, type[Engine]] = {"current": CurrentPipeline}


# --- samples -------------------------------------------------------------------------------------


@dataclass
class Sample:
    base: str
    variant: str
    path: Path
    truth: str
    values: list[dict[str, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.base}__{self.variant}"

    @property
    def kind(self) -> str:  # digital, scan, scan_hard, photo
        return "photo" if self.variant.lower().startswith("photo") else self.variant


def load_samples() -> list[Sample]:
    samples = []
    for path in sorted(SAMPLES.iterdir()):
        match = VARIANT_PATTERN.match(path.name)
        if not match:
            continue
        base = match.group("base")
        truth_file, values_file = SAMPLES / f"{base}.txt", SAMPLES / f"{base}.values.csv"
        if not truth_file.exists():
            print(f"skipped {path.name}: no {truth_file.name}")
            continue
        values = list(csv.DictReader(values_file.open(encoding="utf-8"))) if values_file.exists() else []
        samples.append(Sample(base, match.group("variant"), path, truth_file.read_text(encoding="utf-8"), values))
    return samples


def page_count(path: Path) -> int:
    if path.suffix.lower() != ".pdf":
        return 1
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        return len(pdf)
    finally:
        pdf.close()


# --- text metrics --------------------------------------------------------------------------------


def normalise(text: str) -> str:
    text = re.sub(r"^=== page \d+ ===$", " ", text, flags=re.M)
    text = text.replace(" | ", " ").replace("|", " ")
    return " ".join(text.split())


def text_scores(truth: str, ocr: str) -> dict[str, float]:
    t, o = normalise(truth), normalise(ocr)
    t_words, o_words = t.split(), o.split()
    common = sum((Counter(t_words) & Counter(o_words)).values())
    precision = common / len(o_words) if o_words else 0.0
    recall = common / len(t_words) if t_words else 0.0
    return {
        "cer": Levenshtein.distance(t, o) / max(len(t), 1),
        "wer": Levenshtein.distance(t_words, o_words) / max(len(t_words), 1),
        "word_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


# --- key values ----------------------------------------------------------------------------------

NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:,\d+)*(?:\.\d+)?")


def number(value: str) -> float | None:
    match = NUMBER.search(value or "")
    return float(match.group(0).replace(",", "")) if match else None


def same(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) < 1e-9


def unit_key(unit: str) -> str:
    return unit.lower().replace("µ", "u").replace("μ", "u").replace(" ", "")


def name_variants(test: str) -> list[str]:
    plain = re.sub(r"\s*\([^)]*\)", "", test).strip()
    first = plain.split()[0] if plain.split() else plain
    variants = [test, plain] + ([first] if len(first) >= 4 else [])
    return list(dict.fromkeys(v for v in variants if v))


def value_in_text(row: dict[str, str], ocr: str) -> str:
    """'correct' / 'number_only' (unit missing) / 'WRONG' / 'missing' for one ground-truth value."""
    expected = number(row["value"])
    lines = [" ".join(line.split()) for line in ocr.splitlines() if line.strip()]
    for name in name_variants(row["test"]):
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.I)
        for index, line in enumerate(lines):
            hit = pattern.search(line)
            if not hit:
                continue
            # OCR often puts each table cell on its own line, so read on through the next few lines,
            # the way a line-by-line reader (or the rules) would: the first number after the name.
            rest = " ".join([line[hit.end() :], *lines[index + 1 : index + 4]])
            found = NUMBER.search(rest)
            if not found:
                return "missing"
            if not same(float(found.group(0).replace(",", "")), expected):
                return "WRONG"
            after = unit_key(rest[found.end() : found.end() + 24])
            return "correct" if unit_key(row["unit"]) in after else "number_only"
    return "missing"


def extractor_value(row: dict[str, str], cleaned_text: str, fields: dict[str, str]) -> str:
    """What the app's extract_structured_data gives for this test (only tests it has a field for)."""
    from services.ocr_space_service import STRUCTURED_FIELDS

    test = row["test"].lower()
    if "vldl" in test:  # the app has no VLDL field; "cholesterol" would wrongly map it to total cholesterol
        return "n/a"
    # The alias that starts earliest wins ("LDL Cholesterol" -> ldl, not cholesterol); ties go to the longest.
    candidates = [
        (match.start(), -len(alias), key)
        for key, aliases in STRUCTURED_FIELDS.items()
        if key not in {"test", "patient_name", "doctor_notes", "medicine", "dosage"}
        for alias in aliases
        for match in [re.search(rf"\b{re.escape(alias)}\b", test)]
        if match
    ]
    if not candidates:
        return "n/a"
    key = min(candidates)[2]
    if key not in fields:
        return "missing"
    return "correct" if same(number(fields[key]), number(row["value"])) else "WRONG"


def rules_value(row: dict[str, str], text: str) -> str:
    """What the safety rules' reader (lab_ranges.read_value) takes as this test's number."""
    from services.lab_ranges import LAB_RANGES, read_value

    test = row["test"].lower()
    lab = next((lab for lab in LAB_RANGES if any(re.search(rf"\b{re.escape(a)}\b", test) for a in lab.aliases)), None)
    if lab is None:
        return "n/a"
    reading = read_value(text, lab.aliases)  # no unit conversion: compare the number as printed
    if reading is None:
        return "missing"
    return "correct" if same(reading.value, number(row["value"])) else "WRONG"


# --- run -----------------------------------------------------------------------------------------


def previous_runs(engine_name: str) -> dict[str, dict]:
    """Timing and confidence from the last results.csv, for --reuse."""
    path = RESULTS / "results.csv"
    if not path.exists():
        return {}
    return {r["sample"]: r for r in csv.DictReader(path.open(encoding="utf-8")) if r["engine"] == engine_name}


def run(engine: Engine, samples: list[Sample], reuse: bool = False) -> list[dict]:
    from services.ocr_space_service import build_ocr_result

    out_dir = RESULTS / engine.name
    out_dir.mkdir(parents=True, exist_ok=True)
    earlier = previous_runs(engine.name) if reuse else {}
    rows = []
    for sample in samples:
        pages = page_count(sample.path)
        saved = out_dir / f"{sample.name}.txt"
        if reuse and saved.exists() and sample.name in earlier:
            # Re-score the saved OCR text (after changing a metric) without running OCR again.
            text, error = saved.read_text(encoding="utf-8"), earlier[sample.name]["error"]
            seconds = float(earlier[sample.name]["seconds"])
            confidence = float(earlier[sample.name]["confidence"]) if earlier[sample.name]["confidence"] else None
        else:
            started = time.perf_counter()
            try:
                text, confidence = engine.read(sample.path)
                error = ""
            except Exception as exc:  # recorded, not fatal: one bad file must not stop the run
                text, confidence, error = "", None, f"{type(exc).__name__}: {exc}"
            seconds = time.perf_counter() - started
            saved.write_text(text, encoding="utf-8")

        scores = text_scores(sample.truth, text)
        result = build_ocr_result(text, sample.path.name) if text.strip() else None
        fields = result["structured_data_json"]["fields"] if result else {}
        cleaned = result["cleaned_text"] if result else ""
        levels = {
            "text": [value_in_text(v, text) for v in sample.values],
            "extractor": [extractor_value(v, cleaned, fields) for v in sample.values],
            "rules": [rules_value(v, cleaned) for v in sample.values],
        }
        row = {
            "engine": engine.name,
            "sample": sample.name,
            "kind": sample.kind,
            "pages": pages,
            "seconds": round(seconds, 2),
            "sec_per_page": round(seconds / pages, 2),
            "confidence": "" if confidence is None else round(confidence, 3),
            "cer": round(scores["cer"], 4),
            "wer": round(scores["wer"], 4),
            "word_f1": round(scores["word_f1"], 4),
            "error": error,
        }
        for level, outcomes in levels.items():
            counted = Counter(outcomes)
            row[f"{level}_total"] = len(outcomes) - counted["n/a"]
            row[f"{level}_correct"] = counted["correct"]
            row[f"{level}_wrong"] = counted["WRONG"]
            if level == "text":
                row["text_number_only"] = counted["number_only"]
        rows.append(row)
        print(
            f"  {sample.name:34} {row['sec_per_page']:>6.2f} s/page  CER {row['cer']:.3f}  WER {row['wer']:.3f}  "
            f"values {row['text_correct']}/{row['text_total']}  wrong {row['text_wrong']}/{row['rules_wrong']}(rules)"
            + (f"  ERROR {error}" if error else "")
        )
    return rows


def summarise(rows: list[dict]) -> str:
    lines = [
        "| Engine | Samples | Kind | CER | WER | Word F1 | Values in text | Wrong numbers (text) | Extractor correct | Extractor wrong | Rules correct | Rules wrong | s/page |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["engine"], row["kind"]), []).append(row)

    def pct(a: int, b: int) -> str:
        return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"

    for (engine, kind), group in sorted(groups.items()):

        def total(key: str, group: list[dict] = group) -> int:
            return sum(r[key] for r in group)

        lines.append(
            f"| {engine} | {len(group)} | {kind} | {mean(r['cer'] for r in group):.3f} | {mean(r['wer'] for r in group):.3f} "
            f"| {mean(r['word_f1'] for r in group):.3f} | {pct(total('text_correct'), total('text_total'))} "
            f"| {total('text_wrong')} | {pct(total('extractor_correct'), total('extractor_total'))} | {total('extractor_wrong')} "
            f"| {pct(total('rules_correct'), total('rules_total'))} | {total('rules_wrong')} "
            f"| {mean(r['sec_per_page'] for r in group):.2f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engines", default=",".join(ENGINES), help=f"comma-separated: {', '.join(ENGINES)}")
    parser.add_argument("--variants", default="", help="comma-separated kinds: digital,scan,scan_hard,photo")
    parser.add_argument("--samples", default="", help="comma-separated base-name prefixes, e.g. lab01,lab06")
    parser.add_argument("--reuse", action="store_true", help="re-score saved OCR text instead of running OCR again")
    args = parser.parse_args()

    samples = load_samples()
    if args.variants:
        kinds = set(args.variants.split(","))
        samples = [s for s in samples if s.kind in kinds]
    if args.samples:
        samples = [s for s in samples if any(s.base.startswith(prefix) for prefix in args.samples.split(","))]
    if not samples:
        sys.exit(f"No samples found in {SAMPLES}. Run generate_samples.py first.")

    all_rows = []
    for name in args.engines.split(","):
        engine = ENGINES[name]()
        ok, reason = engine.available()
        if not ok:
            print(f"\n[{name}] skipped: {reason}")
            continue
        if not args.reuse:
            print(f"\n[{name}] warming up...")
            engine.warm_up()
        all_rows += run(engine, samples, reuse=args.reuse)

    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    summary = summarise(all_rows)
    (RESULTS / "summary.md").write_text(summary, encoding="utf-8")
    print("\n" + summary)


if __name__ == "__main__":
    main()
