# ICSE: entity extraction and flag results (synthetic data only)

Reproduce:

```powershell
backend\venv\Scripts\python.exe scripts\icse_bench\generate_patients.py
$env:HF_HUB_OFFLINE="1"; backend\venv\Scripts\python.exe scripts\icse_bench\benchmark_entities.py
backend\venv\Scripts\python.exe scripts\icse_bench\benchmark_flags.py
```

Scoring: an entity counts as right only when its type, name and key attribute all match: the value
for a test result, stopped or not for a medicine, negated or not for a condition.

## 1. Generated narrative reports (42 reports, 12 patients)

The generator and the extractor were written by the same author, so these numbers show that the
patterns work as designed. They do not predict performance on real reports. Section 1b is the
fairer measure.

| | Precision | Recall | F1 |
|---|---|---|---|
| Rules + knowledge base | 100% (401/401) | 100% | 100% |
| With BioBERT suggestions | 88.9% (50 extra) | 100% | 94.1% |

- Dose 85/85, frequency 85/85, unit 168/168, the report's own H/L flag 78/78.
- Family history ("Family history: mother has X", "Fam hx of X (father)", "Brother is a known case
  of X"): 18/18 recorded as `family_history`, none as a patient condition.
- Blood pressure readings: 18/18.
- BioBERT added 45 medicine, 5 condition and 19 symptom suggestions. Medicine precision fell from
  100% to 68%.
- The texts contain 36 conditions and free-text medicines that are deliberately outside the
  knowledge base. The rules find none of them, by design. BioBERT found 12, and they are labelled
  "model suggestion" with confidence ≤ 0.5.

(Numbers from the Batch 2 generator, which added family-history lines and scores blood pressure;
Batch 1's run had 372 entities and the same 100%.)

## 1b. Hand-written harder phrasing (5 snippets, 38 entities)

| | Precision | Recall | F1 |
|---|---|---|---|
| First run (held out, before any fix) | 94.4% | 89.5% | 91.9% |
| After two general fixes | 94.7% | 94.7% | 94.7% |
| After fixes, with BioBERT suggestions | 94.7% | 94.7% | 94.7% |
| After family history (Batch 2) | 94.7% | 94.7% | 94.7% |

The two fixes were the allergy phrasing "sensitive to / hypersensitivity to" (with "(rash)" no
longer read as part of the allergen) and the condition names "Hep B / Hep C". Once these fixes
were made, the set is no longer held out.

Remaining errors, left as known limitations:

- "No DM in family" (fixed in Batch 2): now recorded as negated `family_history`, not as a patient
  condition. The ground truth predates that type, so the benchmark still counts it as one extra;
  the ground truth was not edited.
- "Pt denies TB contact" is read as negated tuberculosis.
- "TC 240" and "TG 310" in the middle of a sentence are missed. Short abbreviations count only at
  the start of a table row, to avoid false matches, so the error is a miss rather than a wrong
  value.

## 2. Test results from OCR text (`ocr_samples/`, exact ground truth)

| Engine | Variant | Expected | Right value | Wrong value | Unreadable | Missed |
|---|---|---|---|---|---|---|
| current | digital | 111 | 111 | 0 | 0 | 0 |
| current | scan | 111 | 0 | 0 | 0 | 111 |
| current | scan_hard | 45 | 0 | 0 | 0 | 45 |
| rows_v5 | digital | 111 | 111 | 0 | 0 | 0 |
| rows_v5 | scan | 111 | 111 | 0 | 0 | 0 |
| rows_v5 | scan_hard | 45 | 45 | 0 | 0 | 0 |

The current OCR prints scanned tables column by column, so the row-based extractor finds no value
next to each name. It reports these as missed, never as a wrong value. With the recommended
rows_v5 OCR, every value is right. (The OCR benchmark's own extractor reached 108/111 on the same
text. This extractor reads rows better.)

## Decision on BioBERT

BioBERT stays a secondary signal: its additions are labelled "model suggestion", have confidence
≤ 0.5, are never used for a flag and never change a rule-found entity. On these texts it adds
recall only for names outside the knowledge base, and it costs precision.

## 3. Flags (Batch 2)

The flag rules are tested case by case in `backend/tests/test_icse_flags.py` (32 tests, including
random sugar 230 with a normal fasting value, one high creatinine then normal, and family history
of diabetes). The benchmark below measures what reaches the doctor end to end: flags built from
what the extractor read, against flags built by the same rules from the exact ground truth. It
cannot show that a rule itself is right; it shows whether reading errors add or lose flags.

### 3a. Synthetic patients (12 patients, 42 dated reports)

| Flags expected | Same flag, same values | Missed | Extra |
|---|---|---|---|
| 103 | 103 | 0 | 0 |

By kind: chronic condition 29, high-alert medicine 5, ongoing treatment 12, persistent high 7,
result high 39, result low 8, trend falling 2, trend rising 1. These are clean typed texts written
by the same author as the extractor (see section 1), so 103/103 is expected, not impressive.

### 3b. Result flags from OCR text (`ocr_samples/`, one report each)

| Engine | Variant | Flags expected | Right | Missed | Wrong (extra) | Shown to check |
|---|---|---|---|---|---|---|
| current | digital | 31 | 31 | 0 | 0 | 0 |
| current | scan | 31 | 0 | 31 | 0 | 0 |
| current | scan_hard | 13 | 0 | 13 | 0 | 0 |
| rows_v5 | digital | 31 | 31 | 0 | 0 | 0 |
| rows_v5 | scan | 31 | 31 | 0 | 0 | 0 |
| rows_v5 | scan_hard | 13 | 12 | 1 | 0 | 2 |

No wrong flag with either engine. With rows_v5 on harsh scans the OCR read the unit "U/L" as "Un"
(ALT 62) and "U/" (AST 22). An unknown unit is never guessed, so both values are listed as "check
against the original report", and the ALT flag is missed rather than raised from an untrusted
value. With the current OCR, scanned tables come out column by column, so no value sits next to
its test name: nothing is flagged, rightly or wrongly.

## Held-out set (pending)

The team will write 10 snippets. They will be run once, with no fixes in between, and reported
here separately as the held-out result.
