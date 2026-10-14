# Knowledge base: data cards

**Status: DEMO KNOWLEDGE BASE.** These tables support an academic prototype. They are not a
clinical reference and have not been reviewed by a clinician. Every row names its source
(`sources.csv`); verify against that source before any real use.

Format: one CSV per table, UTF-8, one row per item. List columns hold `;`-separated values.
Loaded with pandas by `services/knowledge/tables.py` (cached, read once). Schemas (columns,
types, uniqueness, formats, cross-references) are enforced by `tests/test_knowledge_data.py`
with pandera.

| Table | Rows | One row is | Used by |
|---|---|---|---|
| `medicines.csv` | 59 | a generic medicine (WHO INN) | entity extraction, ICSE flags, MSCIE |
| `brands.csv` | 22 | a brand sold in Pakistan → its generic(s) | entity extraction, MSCIE |
| `allergy_classes.csv` | 10 | an allergy word → drug classes | entity extraction, MSCIE |
| `conditions.csv` | 31 | a condition with its ICD-10 code | entity extraction, ICSE flags |
| `lab_tests.csv` | 48 | a lab test and the names labs print | entity extraction, lab rules |
| `plain_terms.csv` | 152 | a medical term → everyday wording | patient summaries and alerts |
| `sources.csv` | 8 | a source cited by the rows above | all tables |

## medicines.csv

- **Columns:** `generic` (lowercase INN, unique), `aliases` (other spellings), `atc` (WHO ATC code,
  may be empty for a combination), `classes` (pharmacological classes used by the rules),
  `high_alert` (on the ISMP high-alert list), `source`.
- **Coverage:** common medicines in Pakistani primary care (diabetes, blood pressure, lipids,
  pain, antibiotics, anticoagulants, thyroid, epilepsy, asthma, stomach). 7 are high-alert.
- **Limitations:** about 60 medicines; no strengths, forms or routes; classes are a simplified
  grouping for the rules, not a full ATC hierarchy.

## brands.csv

- **Columns:** `brand` (unique), `generics` (every one must exist in `medicines.csv`), `source`.
- **Limitations:** 22 well-known brands only. Brand names come from product packs (source
  `PK-PACK`); verify against DRAP registrations.

## allergy_classes.csv

- **Columns:** `allergy_word` (as written in reports: "penicillin", "sulfa drugs"), `classes`.
- **Limitations:** class-level words only; cross-reactivity between classes is not modelled here.

## conditions.csv

- **Columns:** `name` (unique), `synonyms`, `abbreviations` (matched case-sensitively: "DM",
  "HTN"), `icd10` (ICD-10 category or range), `chronic`, `source` (`ICD-10`).
- **Coverage:** 31 conditions, 25 long-term.
- **Limitations:** ICD-10 categories as commonly used; check them in the WHO ICD-10 browser.

## lab_tests.csv

- **Columns:** `name` (unique; the name the lab rules use), `aliases`, `row_abbreviations`
  (two letters or more match anywhere case-sensitively; one letter only at the start of a row),
  `panel`.
- **Panels:** CBC 13, Liver 8, Glucose 5, Kidney 5, Lipid 5, Other 4, Electrolytes 3, Thyroid 3,
  Vitals 1, Cardiac 1.
- **Limitations:** names only. Reference ranges and thresholds are in `services/lab_rules.py`,
  and each lab prints its own.

## plain_terms.csv

- **Columns:** `aliases` (case-insensitive), `abbreviations` (case-sensitive), `plain` (everyday
  wording placed in a sentence), `explain` (one sentence, ends with a full stop), `source`.
- **Coverage:** every lab test and condition above, common report words and prescription
  shorthand.
- **Limitations:** English only; the app's own wording of standard patient-information meanings,
  awaiting clinician review.
