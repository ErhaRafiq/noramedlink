# Evaluation notebooks

Data-science evaluation of Nora MedLink's modules, on **synthetic data only** (no real patient
data). Each notebook regenerates its synthetic data, so it can be re-run from a clean checkout.

| Notebook | Evaluates | Tools |
|---|---|---|
| `01_icse_evaluation.ipynb` | Module 3 (ICSE): entity extraction (precision, recall, F1 per type, with and without BioBERT), negation confusion matrix, hand-written set, flags, OCR value accuracy | pandas, scikit-learn, matplotlib |
| `02_plain_language_evaluation.ipynb` | Everyday wording for patients: unexplained terms, invented numbers, reading grade (Flesch-Kincaid), most frequent terms | pandas, matplotlib |
| `03_mscie_evaluation.ipynb` | Module 4 (MSCIE): alert detection per kind (precision, recall, F1), severity confusion matrix, false alerts on negative controls, alternatives never contraindicated, ranking-weight sensitivity | pandas, scikit-learn, matplotlib |

## Run

```powershell
cd backend; .\venv\Scripts\python.exe -m pip install -r requirements-ds.txt; cd ..
cd notebooks
$env:HF_HUB_OFFLINE="1"; ..\backend\venv\Scripts\python.exe -m nbconvert --to notebook --execute --inplace 01_icse_evaluation.ipynb
```

Notebook 03 reads the hand-written scenarios in `scripts/mscie_bench/scenarios.csv`. Their expected
alerts come from the knowledge base's own rules, so it checks the engine against its specification,
not clinical validity.

Notebook 01's OCR section reads `ocr_samples/_results/results.csv`; run
`scripts/ocr_bench/benchmark.py` first to include it.

The notebooks are committed with their outputs so the results can be read on GitHub.
