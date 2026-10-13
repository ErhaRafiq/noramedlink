# OCR benchmark results (synthetic samples)

12 synthetic lab reports (`generate_samples.py`): digital PDF, scanned-style PDF and, for 4 reports,
a harsher scan (150 DPI, 1.5-3 degree tilt, more noise). 111 key values (45 on the harsh scans).
CPU: this laptop (8 threads). "Wrong" = test found with a different number (the dangerous outcome).
Phone photos to be added.

| Engine | Kind | CER | WER | Values correct | **Wrong** | Flagged | Rules wrong | s/page |
|---|---|---|---|---|---|---|---|---|
| current | digital | 0.000 | 0.000 | 111/111 | 0 | 0 | 0 | 0.01 |
| current | scan | 0.103 | 0.295 | 63/111 | **41** | 0 | 16 | 6.7 |
| current | harsh | 0.368 | 0.642 | 0/45 | **38** | 0 | 13 | 7.1 |
| rows | scan | 0.026 | 0.236 | 111/111 | 0 | 0 | 0 | 5.4 |
| rows | harsh | 0.060 | 0.441 | 37/45 | 0 | 0 | 0 | 5.5 |
| rows_flag90 | harsh | 0.073 | 0.451 | 36/45 | 0 | 1 | 0 | 5.4 |
| rows_flag95 | harsh | 0.120 | 0.470 | 35/45 | 0 | 3 | 0 | 5.4 |
| **rows_v5** | scan | 0.010 | 0.063 | 108/111 | 0 | 0 | 0 | 4.6 |
| **rows_v5** | harsh | 0.089 | 0.249 | 42/45 | 0 | 0 | 0 | 5.0 |
| doctr (own layout) | scan | 0.428 | 0.521 | 21/111 | 18 | 0 | 0 | 7.2 |
| rows_doctr | scan | 0.031 | 0.111 | 86/111 | 13 | 0 | 6 | 5.5 |
| rows_doctr | harsh | 0.327 | 0.490 | 5/45 | 32 | 0 | 9 | 6.7 |

All engines read digital PDFs from the text layer (identical rows omitted).

- `current`: the app (RapidOCR 1.4, PP-OCRv4 det + PP-OCRv3 English rec), one OCR box per line.
- `rows`: same OCR; boxes deskewed and regrouped into table rows (`layout.py`).
- `rows_flagNN`: rows; numbers in boxes scoring below 0.NN become `[?]`.
- `rows_v5`: rows with RapidOCR 3.10 and PP-OCRv5 (det mobile, English rec mobile).
- `doctr` / `rows_doctr`: docTR 1.1 (fast_base + crnn_vgg16_bn), its own layout / our rows.

The 6 values `rows_v5` misses are all "number right, unit misread or missing".
