# Nora MedLink

Nora MedLink is a final-year project prototype (BS Data Science, COMSATS Islamabad): an
AI-assisted healthcare platform with patient health records, report OCR, AI summaries, advisory
medicine-safety checks, doctor search and booking, and time-limited doctor access to a patient's
dashboard.

It is an academic prototype, **not** a certified medical device. Every medical feature is
advisory only.

Contributors and AI coding agents: read [AGENTS.md](AGENTS.md) first. It has the architecture,
safety, security and UI rules. The phase plan and current state are in
[docs/claude-code-brief.md](docs/claude-code-brief.md).

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS, Poppins, lucide-react; Three.js on the landing page |
| Backend | FastAPI, SQLAlchemy 2, Alembic, slowapi (rate limiting) |
| Database | PostgreSQL (a local SQLite file is used only when no database URL is set) |
| OCR | OCR.space (optional; see [Reports and OCR](#reports-and-ocr)) |
| AI | OpenAI or Groq when a key is set, rule-based fallback otherwise; BioBERT for entity extraction |

The browser never calls FastAPI directly. It calls `/api/backend/...` on the Next.js server,
which forwards to FastAPI.

## Prerequisites

- Node.js 20 or later
- Python 3.11
- PostgreSQL (any recent version)

## Setup

### 1. Database

Create the database once:

```sql
CREATE DATABASE noramedlink;
```

The schema is created and kept up to date by Alembic when the backend starts.

### 2. Environment files

Copy the examples and fill in your own values. Never commit the real files.

| Copy | To | Used by |
|---|---|---|
| `backend/.env.example` | `backend/.env` | FastAPI (database, JWT secret, AI and OCR keys, rate limits) |
| `.env.example` | `.env` | Next.js (`SERVER_API_URL`, the FastAPI address for the proxy) |
| `.env.local.example` | `.env.local` | Nothing required; the browser needs no API URL |

FastAPI reads the root `.env` first and then `backend/.env`, which wins when both set a value.
The important backend variables:

| Variable | Needed for |
|---|---|
| `FASTAPI_DATABASE_URL` (or `DATABASE_URL`) | PostgreSQL, e.g. `postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/noramedlink` |
| `JWT_SECRET_KEY` | Signing sign-in tokens. Without it, a random secret is used and everyone is signed out on restart |
| `ADMIN_INVITE_CODE` | Creating an admin account |
| `OCR_SPACE_API_KEY` | Reading text from uploaded reports |
| `OPENAI_API_KEY` or `GROQ_API_KEY` | AI summaries and explanations (rule-based text otherwise) |
| `RATE_LIMIT_*`, `LOG_LEVEL`, `MAX_UPLOAD_MB` | Optional; defaults are in `backend/.env.example` |

### 3. Install

```powershell
npm install

cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-dev.txt   # the app plus dev tools (ruff)
```

## Run

The app needs two terminals running at the same time.

```powershell
# Terminal 1: backend (http://127.0.0.1:8000, health check at /health)
cd backend
.\venv\Scripts\activate
uvicorn main:app --port 8000

# Terminal 2: frontend
npm run dev
```

Open **http://localhost:3000**.

## Reports and OCR

1. The patient uploads a PDF, JPG, PNG or WebP report (up to 10 MB; large photos are shrunk in
   the browser first) and picks a department.
2. FastAPI checks the token, the file type and the file's contents, and stores it privately under
   `backend/uploads/<patient id>/<department>/`. Files are served only to the owner, or to a
   doctor with an active access grant, through short-lived signed links.
3. OCR.space reads the text. Rule-based checks set the report's validation status
   (`SAFE`, `CAUTION`, `HIGH_RISK` or `NOT_VALIDATED`); the AI only writes the explanation.
4. The patient reviews the text on the report page, corrects it and saves, or re-runs OCR.

Without `OCR_SPACE_API_KEY`, the upload is still saved with OCR marked as failed, and the patient
can type the text on the report page.

OCR works best on clear, straight, well-lit printed text. Handwriting, blur, folds, stamps and
complex tables reduce accuracy, so always check the text before relying on a summary.

## API conventions

- **Pagination:** list endpoints take `?limit=` (1–100, default 20) and `&offset=` and return
  `{ "items": [...], "total": n, "limit": n, "offset": n }`.
- **Rate limits:** per user when signed in, per IP otherwise. Login also has a per-email limit.
  Over the limit, the API returns 429 with a `Retry-After` header and a readable `detail`.
  Defaults: 200/min overall, login 20/min per IP and 5/min per email, signup 5/min, uploads
  10/min, AI and OCR 10/min, doctor access codes 10/min. Each is configurable in `backend/.env`.
- **Errors** are always `{ "detail": "..." }`.

## Development

| Task | Command (from the repo root unless stated) |
|---|---|
| Frontend lint | `npm run lint` |
| Type-check | `npx tsc --noEmit -p .` |
| Production build | `npm run build` |
| Backend lint and format | `cd backend; .\venv\Scripts\python.exe -m ruff check .; .\venv\Scripts\python.exe -m ruff format .` |
| Backend unit tests | `cd backend; .\venv\Scripts\python.exe -m pytest` (no database or network needed) |
| Acceptance tests | `backend\venv\Scripts\python.exe tests\acceptance_test.py` (both servers running) |
| Screenshots for review | `npm run screenshots` (dev server running; uses the installed Microsoft Edge) |
| Regenerate app icons | `backend\venv\Scripts\python.exe scripts\generate-icons.py` |

### Acceptance tests

`tests/acceptance_test.py` checks the running app over HTTP: 401 without a token, 403 for the
wrong role or an inactive account, patients isolated from each other, doctors limited to patients
who granted access, pagination and search, rate limits, and the medicine-safety rules.

It refuses to run unless every database URL points to localhost. It creates temporary users whose
email starts with `phase0-test-` and deletes only those users and their rows when it finishes, even
if a check fails. Set `PHASE0_BASE_URL` to test a dev server on another port (default
`http://localhost:3000`).

## Database migrations

On startup the backend runs `alembic upgrade head`. Migrations only add tables, columns and
indexes; they never drop anything or delete data.

Before upgrading a database that already has data, back it up:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -U postgres -F c -f noramedlink-backup.dump noramedlink
```

(Change `18` to your PostgreSQL version. Restore with
`pg_restore -U postgres -d noramedlink --clean noramedlink-backup.dump`.)

From `backend/`, `alembic current` shows the applied revision and `alembic check` reports any
difference between the models and the database.

`patient_reports` is the single report table. The older `medical_documents` table is kept
read-only: migration 0008 copied its rows into `patient_reports`, and the backend refuses to write
to it.
