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
| OCR | Local OCR (RapidOCR) by default; OCR.space when a key is set (see [Reports and OCR](#reports-and-ocr)) |
| AI | One `AI_API_KEY` (Gemini, OpenAI or Claude, recognised from the key), rule-based fallback otherwise; BioBERT for entity extraction |
| Payments | Stripe Checkout (hosted page) with signed webhooks |
| Hosting | Render, one monorepo: `render.yaml` (see [Deploy to Render](#deploy-to-render)) |

The browser never calls FastAPI directly. It calls `/api/backend/...` on the Next.js server,
which forwards to FastAPI.

**Sign-in and roles.** Signing in sets two HttpOnly cookies (JavaScript cannot read them, so a script injected into
a page cannot steal them): a 15-minute access token and a 7-day refresh token. The Next.js server adds the access
token to each call it forwards and, when it has expired, swaps the refresh token for a new pair (the used one stops
working; presenting it again ends the whole session). Cross-site posts are refused. Every FastAPI route names its
role (`patient`, `doctor` or `admin`) or is on a reviewed list, enforced by `backend/tests/test_api_routes.py`;
the role is read from the database on each request, so changes apply at once.

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

### 2. Environment file

One file for the whole project: copy `.env.example` (repo root) to `.env` and fill it in. Both
Next.js and FastAPI read it; never commit it. Variables already set in the environment win over it
(on Render they are set in the dashboard; there is no `.env` there).

| Variable | Needed for |
|---|---|
| `DATABASE_URL` | PostgreSQL, e.g. `postgresql://postgres:YOUR_PASSWORD@localhost:5432/noramedlink` |
| `JWT_SECRET_KEY` | Signing sign-in tokens. Without it, a random secret is used and everyone is signed out on restart |
| `ADMIN_INVITE_CODE` | Creating an admin account |
| `FRONTEND_ORIGIN`, `SERVER_API_URL` | Where the website runs, and where Next.js reaches FastAPI (defaults suit local development) |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Online payment of consultation fees (see [Payments](#payments)) |
| `AI_API_KEY` (Gemini, OpenAI or Claude) | AI summaries and explanations in plain language (rule-based text otherwise). Patient identifiers are removed before text is sent; on Google's free Gemini tier, content may be used to improve Google's products |
| `BIOBERT_ENABLED` | `0` skips BioBERT (needs about 1 GB of memory); entity extraction then uses the fixed rules |

Everything else (rate limits, upload size, model names) is a default in `backend/config.py`.

### 3. Install

```powershell
npm install

cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-dev.txt   # the app, BioBERT (requirements-ml.txt) and dev tools
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

1. The patient uploads a PDF, Word (.docx), JPG, PNG, WebP or TIFF report (up to 10 MB; large photos are shrunk in
   the browser first) and picks a department.
2. FastAPI checks the token, the file type and the file's contents, and stores it privately under
   `backend/uploads/<patient id>/<department>/`. Files are served only to the owner, or to a
   doctor with an active access grant, through short-lived signed links.
3. The text is read on the server. A PDF's own text layer is used when it has one; scanned pages and
   photos are read with local OCR (RapidOCR 3 with the PP-OCRv5 models), and the text boxes are put
   back into table rows so each value stays next to its test. Nothing is sent to an outside service
   The first upload
   downloads the two OCR models once (about 13 MB, checksum-verified) into `backend/models/`; to fetch
   them ahead of time, run `.\venv\Scripts\python.exe -m services.local_ocr --download` from
   `backend/`. A scanned page takes about 5-6 seconds on a laptop CPU. Numbers OCR was unsure of
   (score under 0.90) are left exactly as read and listed on the report page as "check against the
   original report"; the report is then at least CAUTION.
4. Rule-based checks set the report's validation status (`SAFE`, `CAUTION`, `HIGH_RISK` or
   `NOT_VALIDATED`). With an AI key the AI writes the patient's summary; without
   one, it is built by fixed rules from the values the app read. The page says which. Either way the
   summary and the alerts use everyday words: each medical term gets everyday wording, with the term
   once in brackets ("kidney waste level (Creatinine)"), and a "Words you might see" list explains
   the terms on the report. Urgent alerts are shown in red, points to discuss in amber, and
   conditions the report mentions (for example diabetes) are highlighted as "mentioned in your
   report", never as a diagnosis.
5. The patient reviews the text on the report page, corrects it and saves, or re-reads the file.

If no text can be read, the report is saved as not validated, with no summary, and the report page says
why; the patient can type the text and save to get the summary.

OCR works best on clear, straight, well-lit printed text. Handwriting, blur, folds, stamps and
complex tables reduce accuracy, so always check the text before relying on a summary.

## Clinical summaries and medication safety

- **Clinical summary (doctor).** Fixed rules pull medicines, conditions, allergies and lab values out
  of the patient's reports (with negation and family history), and flag readings outside the same
  ranges the report checks use, each flag with its source report and date. The summary is stored in
  versions and rebuilt when the reports change. With an AI key, only the key findings are reworded,
  and a rewording that adds a number is rejected. Patients see the same flags in everyday words.
- **Prescribing (doctor).** While a patient's access grant is active, the doctor searches medicines
  (brand or generic, typos allowed) and each one is checked live against the patient's record:
  allergies and cross-reactions, interactions, duplicate classes, conditions and lab values (eGFR,
  potassium), dose limits and earlier reactions. Every alert says what, why (the rule and the
  record), what to do and the source. Safer alternatives are ranked by a weighted score shown in
  full, and each one is re-checked for the patient. Confirming despite a high-risk alert needs a
  written reason, stored with the prescription. The patient sees confirmed prescriptions read-only.
- **Rules decide, AI never does.** Alerts come only from the CSV tables in
  `backend/services/knowledge/data/` (data card and sources in its `README.md`). Without a rule the
  app says "no data", never "safe". FDA label text from openFDA is shown as supporting evidence and
  never changes an alert. Behind the curated interaction rules sit 160,235 rated drug pairs from
  DDInter 2.0 (CC BY-NC-SA 4.0, academic use): they fill gaps and are shown whenever they rate a pair
  higher than the curated rule. The tables are a demo knowledge base, not clinically reviewed.

## Data and evaluation

The knowledge bases are CSV files loaded with pandas and validated with pandera in the unit tests.
`notebooks/` holds evaluation notebooks on synthetic data (entity extraction, everyday wording,
medication safety), committed with their outputs; see [notebooks/README.md](notebooks/README.md).

## Payments

Patients pay a doctor's consultation fee by card on **Stripe Checkout** (Stripe's hosted page; the
app never sees card details).

1. The doctor sets a fee (PKR) on the doctor dashboard ("Consultation fee"). Patients see it on the
   doctor's card and on their appointments.
2. The patient presses **Pay PKR ...** (My appointments, or the Payments page). FastAPI creates a
   Checkout session for that appointment at the doctor's fee; the amount never comes from the browser.
3. Stripe sends the patient back to `/payments/result`. The payment is marked **paid only when Stripe's
   signed webhook** (`POST /payments/stripe/webhook`) confirms it, for the right amount and currency.
   Each Stripe event is applied once; nobody, not even an admin, can mark a payment paid by hand.

Locally (test mode, no real money):

```powershell
# Install the Stripe CLI (https://docs.stripe.com/stripe-cli), then forward webhooks to FastAPI:
stripe login
stripe listen --forward-to localhost:8000/payments/stripe/webhook
# It prints a webhook secret (whsec_...): put it in .env as STRIPE_WEBHOOK_SECRET and restart the backend.
```

Pay with the test card **4242 4242 4242 4242**, any future expiry date and any CVC. Without
`STRIPE_SECRET_KEY` the Pay button explains that online payment is not set up.

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
| Acceptance tests | Start the backend with `$env:DISABLE_PAID_SERVICES="1"`, then `$env:DISABLE_PAID_SERVICES="1"; backend\venv\Scripts\python.exe tests\acceptance_test.py` (both servers running; no AI, OCR.space or openFDA call is made) |
| Browser (e2e) tests | Same backend as above, then `$env:DISABLE_PAID_SERVICES="1"; npm run test:e2e` (uses the installed Microsoft Edge) |
| Screenshots for review | `npm run screenshots` (dev server running; uses the installed Microsoft Edge) |
| Regenerate app icons | `backend\venv\Scripts\python.exe scripts\generate-icons.py` |

### Acceptance tests

`tests/acceptance_test.py` checks the running app over HTTP: 401 without a token, 403 for the
wrong role or an inactive account, patients isolated from each other, doctors limited to patients
who granted access, pagination and search, rate limits, the medicine-safety rules, and
prescribing (high-risk alerts need a written reason; only the prescribing doctor can cancel).

It refuses to run unless every database URL points to localhost. It creates temporary users whose
email starts with `phase0-test-` and deletes only those users and their rows when it finishes, even
if a check fails. Set `PHASE0_BASE_URL` to test a dev server on another port (default
`http://localhost:3000`).

### Browser tests

`tests/e2e/` drives the real pages in Microsoft Edge, on a desktop window and at phone width
(390px): the landing page, sign in and sign up, the patient dashboard (search, vitals, upload,
doctor access code), the report page, the doctor unlocking a patient file with that code and
prescribing (with the live safety check), the doctor directory and booking, and the admin
approving or rejecting a doctor. Every page checked at phone width must not scroll sideways.

`tests/e2e/fixtures.py` creates the test users before the run and deletes them afterwards, with
the same localhost guard and `phase0-test-` cleanup as the acceptance tests. Run one suite at a
time. Set `E2E_BASE_URL` to test another port. Failures leave a screenshot and trace under
`test-results/e2e/`.

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

## Deploy to Render

The repo deploys as one monorepo with the blueprint in `render.yaml`: **nora-web** (Next.js, repo
root), **nora-api** (FastAPI, `backend/`) and **nora-db** (PostgreSQL), all on the free plan.

1. Push the branch to GitHub. In Render: **New > Blueprint**, pick the repo; Render reads `render.yaml`.
2. When asked, fill in the values marked `sync: false`:
   - `nora-shared` group: `ADMIN_INVITE_CODE`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (see step 4),
     `AI_API_KEY` (optional). `JWT_SECRET_KEY` is generated by Render.
   - nora-api: `FRONTEND_ORIGIN` = nora-web's address, e.g. `https://nora-web.onrender.com`.
   - nora-web: `SERVER_API_URL` = nora-api's address, e.g. `https://nora-api.onrender.com`.
   `DATABASE_URL` is filled in from nora-db automatically; migrations run when nora-api starts.
3. Build and start commands are in the blueprint: `pip install -r requirements.txt` and
   `uvicorn main:app --host 0.0.0.0 --port $PORT` (nora-api); `npm ci && npm run build` and
   `npm start` (nora-web). Python 3.11.9 (`backend/.python-version`) and Node 22 (`.node-version`).
4. Stripe webhook: in the Stripe Dashboard (test mode), **Developers > Webhooks > Add endpoint**,
   URL `https://<nora-api address>/payments/stripe/webhook`, events `checkout.session.completed`,
   `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed` and
   `checkout.session.expired`. Copy its signing secret into `STRIPE_WEBHOOK_SECRET`.

Free plan limits, all accepted for this demo:

- Services sleep after 15 idle minutes; the first request then takes about a minute.
- **Uploaded reports are lost** on every restart or deploy (no persistent disk on the free plan).
  A paid instance with a disk mounted at `backend/uploads` keeps them.
- BioBERT is off (`BIOBERT_ENABLED=0`; it needs about 1 GB). Entity extraction uses the fixed rules.
- The free database expires after a time limit set by Render; back it up or upgrade before then.
- Rate limits keyed by IP address (login, signup) see the Next.js server's address, not each user's,
  because requests reach FastAPI through the proxy. Per-account limits are unaffected.
