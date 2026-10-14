# Evaluation notebooks

Data-science evaluation of Nora MedLink's modules, on **synthetic data only** (no real patient
data). Each notebook regenerates its synthetic data, so it can be re-run from a clean checkout.

| Notebook | Evaluates | Tools |
|---|---|---|
| `01_icse_evaluation.ipynb` | Module 3 (ICSE): entity extraction (precision, recall, F1 per type, with and without BioBERT), negation confusion matrix, hand-written set, flags, OCR value accuracy | pandas, scikit-learn, matplotlib |
| `02_plain_language_evaluation.ipynb` | Everyday wording for patients: unexplained terms, invented numbers, reading grade (Flesch-Kincaid), most frequent terms | pandas, matplotlib |

## Run

```powershell
cd backend; .\venv\Scripts\python.exe -m pip install -r requirements-ds.txt; cd ..
cd notebooks
$env:HF_HUB_OFFLINE="1"; ..\backend\venv\Scripts\python.exe -m nbconvert --to notebook --execute --inplace 01_icse_evaluation.ipynb
```

Notebook 01's OCR section reads `ocr_samples/_results/results.csv`; run
`scripts/ocr_bench/benchmark.py` first to include it.

The notebooks are committed with their outputs so the results can be read on GitHub.
