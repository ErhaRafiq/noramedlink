# Nora MedLink

Nora MedLink is a Final Year Project prototype with a Next.js frontend, a FastAPI backend, PostgreSQL storage, and Tesseract OCR for patient medical report uploads.

## Stack

- Frontend: Next.js
- Backend: FastAPI
- Database: PostgreSQL through SQLAlchemy and psycopg2
- OCR: Tesseract, pytesseract, Pillow, OpenCV, NumPy

## PostgreSQL Setup

Install PostgreSQL locally and create the project database:

```sql
CREATE DATABASE noramedlink;
```

Create `backend/.env` from `backend/.env.example` and set your local password:

```env
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/noramedlink
SECRET_KEY=change-this-secret
FRONTEND_ORIGIN=http://localhost:3000
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Do not commit `.env` files. They are ignored by git.

## Tesseract Setup on Windows

1. Download Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
2. Install it.
3. Either add Tesseract to your Windows `PATH`, or set this in `backend/.env`:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

The backend reads `TESSERACT_CMD` and assigns it to `pytesseract.pytesseract.tesseract_cmd`.

## Backend Run Commands

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Frontend Run Commands

Create `.env.local` from `.env.local.example`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Run the frontend:

```powershell
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:3000
```

## Patient Upload and OCR Workflow

1. Patient signs up or logs in.
2. Patient opens the dashboard and selects Upload Report.
3. Frontend sends `category`, `title`, `notes`, and the image file as `FormData`.
4. The browser does not manually set `Content-Type`; it lets the multipart boundary be generated automatically.
5. FastAPI verifies the bearer token and confirms the user is a patient.
6. Backend validates JPG, JPEG, or PNG and enforces the 10 MB limit.
7. File is saved under `backend/uploads/{patient_id}/{category}/` with a unique filename.
8. OCR service preprocesses the image using OpenCV grayscale conversion, Gaussian blur, and OTSU thresholding.
9. Tesseract extracts English text from the preprocessed image.
10. Backend cleans the OCR text, detects medical keywords, detects report type, builds structured sections, and generates a safe summary.
11. Medical document data is saved in PostgreSQL.
12. Patient reviews the OCR text, edits it if needed, and saves the corrected text.
13. Backend updates `ocr_cleaned_text`, regenerates keywords, structured sections, and summary, then saves the result.

## Database Workflow

FastAPI loads `DATABASE_URL` from `backend/.env`. Only PostgreSQL URLs are accepted. On startup, SQLAlchemy creates these tables if they do not exist:

- `users`
- `patient_profiles`
- `doctor_profiles`
- `medical_documents`

`medical_documents` stores the uploaded file metadata, OCR status, raw OCR text, cleaned OCR text, detected keywords, structured OCR sections, safe summary, and upload date.

## Test Flow

1. Start PostgreSQL and confirm the `noramedlink` database exists.
2. Start FastAPI on `http://127.0.0.1:8000`.
3. Start Next.js on `http://localhost:3000`.
4. Signup as a patient.
5. Login.
6. Open the patient dashboard.
7. Upload a clear JPG or PNG medical report.
8. Confirm OCR text appears.
9. Edit the OCR text.
10. Save corrected text.
11. Confirm the document remains available in records and data is stored in PostgreSQL.

## OCR Limitations

Tesseract works best with clear printed text, high contrast, straight images, and minimal shadows. Handwriting, blurred photos, folded paper, low light, stamps over text, and complex table layouts can reduce accuracy. Always review and correct OCR text before relying on summaries.
