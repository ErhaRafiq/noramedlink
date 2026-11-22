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
| `lab_meanings.csv` | 24 | a lab test → what a higher or a lower result can be linked to | the report explanation |
| `interactions.csv` | 31 | a drug-drug (or class-class) interaction | MSCIE |
| `contraindications.csv` | 19 | a drug or class vs a condition or a lab threshold | MSCIE |
| `allergy_cross_reactivity.csv` | 10 | an allergy class → a drug or class it affects | MSCIE |
| `dose_limits.csv` | 23 | a medicine's usual maximum single and daily dose | MSCIE |
| `dose_limits_per_kg.csv` | 15 | a label tier (age in months, weight) of a medicine's dose limits: per-kg and absolute | MSCIE |
| `duplicate_classes.csv` | 10 | a class where two medicines together is a duplicate | MSCIE |
| `alternatives.csv` | 24 | a safer candidate for the same use | MSCIE |
| `ranking_weights.csv` | 4 | a ranking factor and its weight (sums to 1) | MSCIE |
| `home_visit_suitability.csv` | 16 | a specialty: can it see a patient at home, and how well | home visits |
| `home_visit_weights.csv` | 4 | a doctor-ranking factor and its weight (sums to 1) | home visits |
| `home_visit_checklist.csv` | 11 | a fixed emergency question the patient answers first | home visits |
| `ddinter_interactions.csv.gz` | 160,235 | a drug pair and DDInter's level (CC BY-NC-SA 4.0) | MSCIE, behind `interactions.csv` |
| `ddinter_names.csv` | 57 | a curated medicine → its DDInter name(s) | MSCIE |
| `sources.csv` | 15 | a source cited by the rows above | all tables |

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

## lab_meanings.csv

- **Columns:** `test` (a test name from `lab_rules.RULES`), `higher` and `lower` (one sentence each, ends with a
  full stop: what a result above or below the usual range can be linked to), `source`.
- **Use:** the "Your report in simple words" explanation. General patient-information wording; it names causes a
  result can be linked to and never says the reader has an illness.
- **Limitations:** English only; awaiting clinician review.

## Module 4 (MSCIE) tables

Medicine references are a generic from `medicines.csv` or `class:<class>` (a class one of those
medicines has); the schema tests reject any reference that does not exist. Severities:
`contraindicated` and `major` are high risk (a doctor must write a justification to override),
`moderate` is a caution, `minor` is information.

- **interactions.csv** (`id`, `a`, `b`, `severity`, `effect`, `management`, `source`): 31 pairs,
  mostly from the ONC high-priority list (Phansalkar 2012) and FDA prescribing information.
  Limitations: a curated subset for about 60 medicines, not a complete interaction database.
- **contraindications.csv** (`id`, `drug`, `exclude`, `condition` or `lab_test`/`lab_operator`/
  `lab_value`, `severity`, ...): drug-disease and drug-lab rules (eGFR, potassium) from FDA labels,
  KDIGO, GINA and the EMA domperidone review. Lab tests are the shared lab rules' names.
- **allergy_cross_reactivity.csv**: same-class and cross-class rules from the 2022 drug-allergy
  practice parameter (penicillin-cephalosporin cross-reactivity is uncommon: a caution).
- **dose_limits.csv**: usual adult maximum single and daily doses (mg) from FDA labels and the EMA;
  no paediatric, weight-based or renal dosing (renal rules are in contraindications.csv).
- **dose_limits_per_kg.csv** (`generic`, `tier`, `kind`, `age_from_months`, `age_to_months`, `weight_from_kg`, `weight_to_kg`, `max_single_mg_per_kg`, `max_daily_mg_per_kg`, `max_single_mg`, `max_daily_mg`, `caution_single_mg`, `caution_single_mg_per_kg`, `caution_daily_mg_per_kg`, `severity`, `caution_note`, `over_note`, `within_note`, `source`): one row per tier of an FDA label, for paracetamol (the acetaminophen injection label), amoxicillin, azithromycin, ibuprofen and cefixime. A tier is chosen by the patient's age in months (both ends inclusive) and, where the label splits by weight, by the recorded weight (from inclusive, to exclusive). The dose is checked against the per-kg limit times the weight, never above the tier's absolute maximum (`services/mscie/weight_doses.py`). `not_covered` tiers (below a label's minimum age) say "verify dose: not covered by demo table". With no weight, or one older than the app rule (demo) in `config.py` (90 days adults, 30 days under 18), the check is skipped and "weight needed for dose check" is shown; a weight is never assumed. Amoxicillin above 45 mg/kg/day is a yellow note (moderate), not a red alert. Sources are FDA labels only, listed with set id, URL and date in `sources.csv`. Figures were checked by two team members against the labels. Not yet covered: amoxicillin-clavulanate (strengths such as "500/125" are not parsed yet), indication-specific limits (the prescription form has no indication field) and paracetamol from other products taken at the same time. Demo knowledge base, not clinically reviewed.
- **duplicate_classes.csv**: classes where two medicines together duplicate the effect.
- **alternatives.csv**: candidates for the same use, each re-checked against the patient before it
  is shown; a contraindicated candidate is never suggested. Choosing among them is clinical.
- **ranking_weights.csv**: the transparent scoring weights (safety 0.5, kidney fit 0.2, previous
  response 0.2, simplicity 0.1); the evaluation notebook shows how the ranking changes with them.

## DDInter tables (Module 4, second interaction source)

- **What:** `ddinter_interactions.csv.gz` holds 160,235 drug pairs among 1,939 drugs from DDInter 2.0
  (ddinter.scbdd.com; Xiong G. et al., *Nucleic Acids Research* 2022 and 2025), each with DDInter's level:
  major 26,914, moderate 96,675, minor 6,833, unknown 29,813. `ddinter_names.csv` maps a curated
  medicine to DDInter's name for it (aspirin → acetylsalicylic acid, paracetamol → acetaminophen,
  co-amoxiclav → amoxicillin and clavulanic acid, ...).
- **Licence:** CC BY-NC-SA 4.0. Academic, non-commercial use with attribution; these derived tables
  are shared under the same licence. Do not use them in a commercial product.
- **How it is built:** `scripts/ddinter_import/build.py` from DDInter's eight published downloads
  (names lower-cased, each pair once with a < b, no pair with two levels). Re-run it to update.
- **How the engine uses it** (`services/mscie/ddinter.py`): the curated `interactions.csv` comes first
  (it says what happens and what to do). A DDInter alert is added when no curated rule covers the
  pair, or when DDInter rates the pair higher (the more severe rating is never hidden). "Unknown" is
  shown as moderate. A medicine known only to DDInter can be prescribed and checked for interactions,
  with an extra note that its allergy class, dose, duplicates and conditions were not checked.
- **Gaps:** DDInter publishes downloads for eight ATC groups (A, B, D, H, L, P, R, V) only. A pair of
  two cardiovascular (C), nervous-system (N), anti-infective (J) or musculoskeletal (M) drugs appears
  only when it is also listed under one of those groups (lisinopril + spironolactone does not, so the
  curated rule covers it). DDInter's download has no mechanism or management text: its alerts say
  only that the pair interacts and how severely. Carbimazole, domperidone and gliclazide are not in DDInter.
- **Not clinically reviewed** for this project, like the rest of the knowledge base.

## Symptom checker tables (Module 7)

- **red_flags.csv** (`id`, `label`, `patterns`, `also`, `source`): 12 warning signs. `patterns` are
  alternative phrases (any one matches); `also`, when set, needs one of its phrases as well (a fever
  counts only with a baby word; "allergic" only with swelling or breathing words). Source: NHS
  "when to get urgent help" guidance, as the project's own wording of each sign.
- **specialties.csv** (`name`, `plain`, `doctor_aliases`, `source`): the fixed list of 16 specialties,
  what each looks after in everyday words, and the words that match a doctor's listed specialty.
  "General Physician" is the fallback.
- **symptom_specialties.csv** (`terms`, `specialty`, `weight`, `source`): everyday symptom words to a
  specialty, weight 1 to 3. A phrase belongs to one specialty only (tested), the longest phrase wins
  ("high blood pressure" beats "blood pressure") and a word is never counted twice.
- **Limitations:** English only; a word list, not understanding. It can miss a warning written in other
  words, so the page always shows the 1122 notice first. Negation is a simple look-back over the three
  words before a phrase ("no", "never", "without", "denies"...), cut at a comma or full stop.
  The mapping is the authors' demo mapping (`DEMO-MAP`), **not clinically reviewed**.

## Home visits (home_visit_suitability.csv, home_visit_weights.csv, home_visit_checklist.csv)

- **home_visit_suitability.csv** (`specialty`, `home_visit`, `suitability`, `note`, `source`): one row for each of the
  16 specialties. `home_visit` says whether that kind of doctor can sensibly see a patient at home;
  `suitability` (0 to 1, always 0 for a "no") is one of the four ranking factors. A reason that points to a
  "no" specialty is not matched to a home visit: the patient is told to book a clinic appointment.
- **home_visit_weights.csv** (`factor`, `weight`, `description`): proximity 0.4, specialty 0.25, availability
  0.2, suitability 0.15 (sum 1). Proximity falls evenly from 1 at the same place to 0 at 25 km, straight line.
- **home_visit_checklist.csv** (`id`, `question`, `source`): 11 emergency questions every request must answer.
  One "yes" blocks the request with the 1122 notice; nothing is saved and no doctor is shown.
- **Limitations:** the authors' own demo rules (`HOME-DEMO`), **not clinically reviewed**. They only decide
  whom a request is offered to and never diagnose.
