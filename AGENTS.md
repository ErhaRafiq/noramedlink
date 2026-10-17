# AGENTS.md: Nora MedLink

Instructions for AI coding agents (Claude Code, Codex, Cursor, etc.) working in this repository.
Human contributors should read it too. The detailed phase plan lives in `docs/claude-code-brief.md`.

<!-- BEGIN:nextjs-agent-rules -->
## This is NOT the Next.js you know

This repo uses **Next.js 16**, which has breaking changes (route handlers, params, caching, config).
APIs, conventions and file structure may differ from your training data. Before writing any
Next-specific code, read the relevant guide in `node_modules/next/dist/docs/` and heed deprecation notices.
<!-- END:nextjs-agent-rules -->

---

## 1. Project

**Nora MedLink** is a final-year project (BS Data Science, COMSATS Islamabad, 2023–2027) by
Erha Rafiq and Momna Javed, supervised by Ms. Sadia Maryam. It is an **academic prototype** of an
AI-assisted healthcare platform: unified patient health records with OCR, AI clinical summaries,
advisory medication-safety alerts, doctor search and booking, home visits, and symptom-to-specialist
guidance.

It is **not** a certified medical device. Every medical feature is advisory only (see section 6).

| Owner | Modules |
|---|---|
| Momna Javed | Phase 2: symptom → specialist mapper, doctor search, appointments, home visits |
| Erha Rafiq | Phase 3: structured health records, prescription safety (MSCIE), audit log |

---

## 2. Stack (verified, not what the design docs say)

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS, lucide-react, Poppins (next/font) |
| 3D | Three.js + @react-three/fiber, on the landing page only |
| Backend | **FastAPI** (the only backend), SQLAlchemy 2 ORM, slowapi rate limiting, ruff |
| Database | PostgreSQL; schema managed by **Alembic** migrations |
| Medication safety | MSCIE (`services/mscie/`): deterministic rules from CSV tables (interactions, contraindications, allergy cross-reactivity, dose limits, duplicate classes, alternatives, ranking weights) decide every alert; Behind the curated interaction rules: 160,235 rated pairs from DDInter 2.0 (`services/mscie/ddinter.py`, CC BY-NC-SA 4.0, academic use only), used for gaps and whenever they rate a pair higher. openFDA label text is shown as supporting evidence only and never changes an alert. High-risk alerts need a written reason to confirm, stored in `safety_overrides` |
| Data | Knowledge bases are CSV files in `services/knowledge/data/` (data card `README.md`, sources in `sources.csv`), loaded with pandas and validated with pandera in the tests; medicine search uses rapidfuzz. Evaluation notebooks in `notebooks/` (scikit-learn, matplotlib; `requirements-ds.txt`). The knowledge bases are demo data, not clinically reviewed |
| Auth | FastAPI issues a 15-minute JWT (HS256) and a rotating refresh token (7 days, stored hashed in `refresh_tokens`). **The browser never holds either**: the Next.js server keeps them in HttpOnly, SameSite cookies (`nora_at`, `nora_rt`; `lib/server-session.ts`, `app/api/auth/*`), adds the access token to calls it forwards, and renews it from the refresh cookie when it expires. A reused refresh token revokes its whole session. Only the user's profile is in `localStorage` |
| Payments | Stripe Checkout (hosted page) at the doctor's consultation fee; only Stripe's signed webhook marks a payment paid (`services/payments.py`). No JazzCash, Easypaisa or manual confirmation |
| Email | Resend (`services/email_client.py`; key in your own `.env` only, never committed or pasted into a chat): sign-up confirmation link, forgot-password 6-digit code, password-changed notice, appointment confirmation / move / cancel emails and a 5-minute reminder for patient and doctor. Appointment emails are queued with the booking (`email_outbox`) and sent by a worker loop in `main.py`, not a cron job; codes are stored as keyed hashes. Only confirmed addresses get appointment email; reminders can be switched off in `/profile`. No email holds a reason for a visit or any record content. Off with no key and in test runs (`DISABLE_PAID_SERVICES=1`); test accounts never receive mail. See `docs/email.md` |
| Doctor verification | The signup form checks a PMDC registration number's form (`services/pmdc.py`, mirrored in `lib/pmdc.ts`); an admin checks it on PMDC's free public register (`hospitals-inspections.pmdc.pk`, only the number is sent) or decides by hand; `doctor_profiles.pmdc_verified` drives a badge. A doctor can be active without it. Off with `PMDC_LOOKUP_ENABLED=0` and in test runs (`DISABLE_PAID_SERVICES=1`) |
| Config | **One `.env` in the repo root** for Next.js and FastAPI (template: root `.env.example`); real environment variables win (Render) |
| Hosting | Render monorepo, `render.yaml`: nora-web (Next.js), nora-api (FastAPI, `backend/`), nora-db (PostgreSQL), free plan |
| OCR | **Local OCR** by default (`services/local_ocr.py`): PDF text layers are read directly; scans and photos go through RapidOCR 3 (ONNX, CPU) with the PP-OCRv5 detector and English recogniser, downloaded once to `backend/models/` (checksum-verified); boxes are rebuilt into table rows (`services/ocr_layout.py`), and numbers read with a score under 0.90 are listed as "check against the original report", never changed. No key, nothing leaves the server. There is no Tesseract |
| AI | One `AI_API_KEY` (Gemini, OpenAI or Claude, picked from the key prefix by `services/ai_client.py`), rule-based fallback otherwise; BioBERT NER. Patient identifiers are removed before any prompt leaves the server (`services/privacy.py`), and an AI summary with a number that is not in the report is rejected (`services/ai_guard.py`). Every patient-facing summary and alert is in everyday words: medical terms get everyday wording with the term once in brackets (`services/plain_language.py`, dictionary `services/knowledge/data/plain_terms.csv`, a demo knowledge base); without an AI key the summary is built by fixed rules (`services/patient_summary.py`) |

There is **no** Flutter app, **no** Node gateway and **no** Prisma. Do not create them.
The SRS/SDS documents describe some of these; the code is the source of truth.

---

## 3. Repository map

```
app/                      Next.js pages (App Router)
  api/backend/[...path]/  Same-origin proxy: the browser reaches FastAPI only through this
  api/auth/*              login, signup, logout: set or clear the HttpOnly session cookies (signup logs in at once; the email is confirmed afterwards by a link, and nothing is blocked until then)
  api/drug-check/         Old OpenFDA lookup, used by no page; superseded by services/mscie/openfda.py (ask before deleting)
  dashboard/patient/      Patient dashboard (renders components/patient/PatientWorkspace.tsx)
  dashboard/doctor/       Doctor dashboard (renders components/dashboard/DoctorDashboard.tsx)
  admin/                  Admin dashboard
  icon.svg, favicon.ico, apple-icon.png, manifest.ts   App icons (generated, see section 15)
components/
  ui/                     Shared building blocks: Button, Card, fields, Badge, Alert, Skeleton, ...
  layout/                 SitePage, SiteHeader, PageHeader, DashboardShell
  landing/ auth/ patient/ dashboard/ admin/ doctors/ ...   Feature components
hooks/                    Generic hooks (use-*.ts); feature data hooks in hooks/<area>/
lib/api.ts                The only API client; every call goes to /api/backend/...
lib/auth.ts               Session helpers (getSession, clearSession, dashboardPathForRole)
lib/types.ts              Shared TypeScript types matching FastAPI responses
scripts/                  dev.ps1 (`npm run dev:all`: backend + frontend + Stripe listener), icon generator, screenshot capture, phone-overflow finder; ocr_bench/ and mscie_bench/ (evaluation data);
                          ddinter_import/build.py (rebuilds the DDInter tables)
notebooks/                Evaluation notebooks (ICSE, plain language, MSCIE), committed with outputs
render.yaml               Render blueprint (deploy); .env.example: every environment variable, documented
backend/
  main.py                 FastAPI app; runs `alembic upgrade head` at startup
  config.py               Every environment variable, read once into `settings`
  logging_config.py       Handler for the backend's "nora.*" loggers
  rate_limit.py           Rate limits (slowapi) and the 429 response
  pagination.py           ?limit=&offset= parameters and the Page[T] response
  models.py               SQLAlchemy models: the single source of truth for the schema
  schemas.py              Pydantic request/response models
  dependencies.py         get_current_user, require_patient / require_doctor / require_admin
  routers/                One router per feature area; thin (parse, check access, call a service)
  services/               Business logic (medicine_safety, patient_insights, report_service, OCR, AI, ...)
    icse/                 Module 3: entities, flags, versioned clinical summaries, AI wording of key findings
    mscie/                Module 4: medication-safety engine, alternatives, patient context, prescribing
    knowledge/            CSV knowledge bases and their loader (tables.py)
  migrations/versions/    Alembic migrations (0001 baseline ... 0011 Stripe payments; see `alembic current`)
  pyproject.toml          ruff lint and format settings
tests/acceptance_test.py  End-to-end auth, ownership and safety checks over HTTP
docs/claude-code-brief.md Phase plan, approved decisions, current state, known problems
```

Old URLs `/dashboard` and `/doctor-dashboard` redirect (307) in `next.config.ts`. Do not recreate them.

---

## 4. Commands (Windows, PowerShell)

The app needs **two terminals running at the same time**: backend and frontend.

| Task | Command (run from the repo root unless stated) |
|---|---|
| Install frontend | `npm install` |
| Install backend | `cd backend; python -m venv venv; .\venv\Scripts\activate; pip install -r requirements-dev.txt` (app + dev tools) |
| Run backend | `cd backend; .\venv\Scripts\activate; uvicorn main:app --port 8000` |
| Run frontend | `npm run dev`, then open **http://localhost:3000** (not the 192.168.x.x address) |
| Lint | `npm run lint` |
| Type-check | `npx tsc --noEmit -p .` |
| Backend lint + format | `cd backend; .\venv\Scripts\python.exe -m ruff check .; .\venv\Scripts\python.exe -m ruff format .` |
| Production build | `npm run build` (can run while `npm run dev` is running; Next 16 keeps dev output in `.next/dev`) |
| Backend unit tests | `cd backend; .\venv\Scripts\python.exe -m pytest` (no database, no network; `backend/tests/`) |
| Acceptance tests | Start the backend with `$env:DISABLE_PAID_SERVICES="1"`, then `$env:DISABLE_PAID_SERVICES="1"; backend\venv\Scripts\python.exe tests\acceptance_test.py` (both servers running; no AI, OCR.space, openFDA or Stripe call is made; with the same `STRIPE_WEBHOOK_SECRET` in both it signs test webhook events itself) |
| Browser (e2e) tests | Same backend as above, then `$env:DISABLE_PAID_SERVICES="1"; npm run test:e2e` (report in `test-results/e2e-report`) |
| Screenshots for review | `npm run screenshots` (dev server running; uses the installed Microsoft Edge) |
| Phone overflow check | `node scripts/find-overflow.mjs http://localhost:3000/<page>` (lists elements wider than 390px) |
| Backend smoke tests | `$env:HF_HUB_OFFLINE="1"; backend\venv\Scripts\python.exe backend\test_quick.py` |
| Migration state | `cd backend; .\venv\Scripts\python.exe -m alembic current` |
| Schema drift check | `cd backend; .\venv\Scripts\python.exe -m alembic check` (must report no new operations) |
| Free a stuck port | `Get-NetTCPConnection -LocalPort 8000 -State Listen \| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }` |

---

## 5. Architecture rules

- **FastAPI is the single backend.** All new business logic goes into a FastAPI router + service.
  Do not add Next.js API routes with business logic or database access.
- **The frontend calls the backend only through `lib/api.ts`**, which goes through the
  `/api/backend` proxy. Never call `localhost:8000` from the browser.
- **Identity comes only from the verified token** (the session cookie, added by the Next.js proxy). Never read a user ID from the query string or
  request body. Use the `require_*` dependencies for role checks.
- **Ownership checks are mandatory:** a patient touches only their own data; a doctor sees a
  patient's data only while an active `PatientDashboardAccess` grant exists; admin routes use
  `require_admin`.
- **Exactly three roles:** `patient`, `doctor`, `admin`. There is no pharmacist role. Do not add one.
- **Only admin-verified, active doctors** are visible or bookable by patients.
- **Uploaded files are private.** Serve them only through `routers/files.py` (owner or active grant,
  short-lived signed links). Never mount `uploads/` publicly.
- **One report table:** `patient_reports`. `medical_documents` is a read-only legacy table; the ORM
  blocks writes to it. Do not drop it without explicit team approval.
- Keep `lib/types.ts` in sync with FastAPI response shapes.

---

## 6. Medical safety rules (non-negotiable)

These come from the project scope (limitations LI-1 and LI-5). They override convenience.

1. **Advisory only.** No output may diagnose, prescribe, or state a medicine is definitely safe.
   Use wording such as "potential interaction" and "for physician review".
2. **Deterministic rules decide risk; the LLM only explains.** An LLM must never raise or lower a
   safety status. If the knowledge base has no data, say "no data", never "safe".
3. **Red-flag symptoms → hard emergency redirect.** Show "Call 1122 or go to the nearest emergency
   department." Do **not** offer booking or a home visit for that request.
4. **Every AI output shown to a user carries an "AI-generated, advisory, verify with a clinician" note.**
5. **Physician overrides of safety alerts require a written justification** and are logged.
6. **The emergency page is not an emergency service.** It must never show an assigned doctor or
   ETA unless a real one exists, and it always shows the 1122 notice.

---

## 7. Data honesty rule

**Never show invented data as if it were real.** No sample patients, sample doctors, fake vitals,
fake ratings, fake timestamps ("just now"), fake counts or placeholder statuses ("Stable").
When there is no data, show an honest empty state ("Not recorded", "No reports uploaded yet").
Test data belongs in tests, never in UI fallbacks.

---

## 8. Security and privacy rules

- **Never read aloud, print, log or copy secret values** from `.env` (the project's one env file).
  When checking configuration, report only whether a value is set (true/false).
- Mask database URLs in any output you show (`postgresql://user:****@host`).
- Only edit `*.env.example` files, and only with placeholder values. Never commit real secrets.
- Never commit runtime files: `*.log`, `uploads/`, `.next/`, virtualenvs.
- Never log one-time codes, passwords, tokens or medical text.
- Use realistic **fake** data in examples and tests (e.g. `patient1@test.com`, CNIC `12345-1234567-1`).
- Rate limits on one-time codes (5 failures / 15 min) must stay in place.

---

## 9. Database and migrations

- **Every schema change is an Alembic migration** in `backend/migrations/versions/`, matching a
  change in `models.py`. Never use `create_all` for schema changes.
- **Migrations are additive and idempotent:** check before creating tables, columns or indexes.
  Never drop or rename tables or columns, and never delete data, without explicit approval.
- Data-moving migrations need a proposal (column-by-column mapping) and approval **before** they are written.
- A downgrade that would delete data must refuse to run.
- Verify new migrations on a scratch database (`noramedlink_alembic_check`, localhost only, dropped
  afterwards) and confirm `alembic check` reports no drift.
- Database timestamps are timezone-aware UTC.

---

## 10. Testing

- `tests/acceptance_test.py` must stay green. Extend it whenever you add or change an endpoint:
  401 without a token, 403 for the wrong role or inactive account, and ownership isolation.
- Tests that write to the database must:
  - refuse to run unless every database URL points to localhost (check the hostname only);
  - create users only with the `phase0-test-` email prefix;
  - delete only those users and their rows (and upload folders) in a `finally` block.
- **Never call paid or external services in tests** (Gemini, OpenAI, Claude, openFDA, Stripe). Tests that would
  must skip when a key is configured. `DISABLE_PAID_SERVICES=1` (backend and test process) makes the
  backend ignore every AI and Stripe key, so the whole suite runs with no paid or external call.
- Safety logic (red-flag rules, interaction rules, state transitions) needs unit tests with
  explicit cases, including the cases listed in the brief. Unit tests live in `backend/tests/`
  (pytest): no database, no network, and `conftest.py` blanks every AI and OCR key.
- Browser tests live in `tests/e2e/` (Playwright, installed Edge, desktop and 390px projects).
  `tests/e2e/fixtures.py` creates and removes their `phase0-test-` users with the acceptance
  suite's guard and cleanup. Select elements by role and label, as a user would. Pages and flows
  that change get a test; tests that would reach an LLM skip when a key is set.
  Never run the e2e and acceptance suites at the same time (each cleans up the other's users).

---

## 11. Workflow and git

- **Plan first.** For each phase or batch: read the relevant code, propose files and approach,
  then **stop and wait for approval** before editing.
- **One branch per phase** (`phase-2-patient-modules`, ...). Never commit to `main` directly.
- **Small, focused commits**, one feature area each, using Conventional Commits:
  `feat(scope): ...`, `fix(scope): ...`, `chore: ...`, `docs: ...`, `test: ...`.
- **Do not push** unless the team explicitly asks. Merges to `main` happen through pull requests.
- If you discover a problem outside the current task, **flag it; don't silently fix it.**
  If you judge a fix necessary for safety, make it in its own commit and say so clearly.
- At the end of each phase, update section 2 ("Current state") of `docs/claude-code-brief.md`.

---

## 12. Windows gotchas

- Windows PowerShell 5.1 splits arguments at embedded double quotes. For multi-line commit
  messages, write the message to a file and use `git commit -F <file>`.
- `LF will be replaced by CRLF` warnings from git are expected; ignore them.
- Stopping `npm run dev` can leave orphaned `node` processes holding port 3000. Free the port
  before restarting (see the command table).
- PowerShell pipes may add a UTF-8 BOM to JSON output; write JSON to a file and read it from there.
- Python virtualenv: `backend\venv\Scripts\python.exe`. Activate with `.\venv\Scripts\activate`.

---

## 13. Definition of done

A change is done only when all of these hold:

- [ ] `npm run lint`: 0 errors (existing warnings may remain; add no new ones)
- [ ] `npm run build`: passes
- [ ] `ruff check`, `ruff format --check` and `pytest` in `backend/`: pass (when Python changed)
- [ ] `tests/acceptance_test.py`: all passing, with new checks for new behaviour
- [ ] UI changes: no horizontal scroll at 390px wide; loading, empty and error states all handled
- [ ] `alembic check`: no drift (when models changed)
- [ ] No invented data, no secrets in output, safety rules respected
- [ ] A short manual click-through is written for the human to run (agents cannot drive the browser)
- [ ] Commits are small and clearly described; nothing is pushed

---

## 14. Ask before you

- add a pharmacist role, another payment gateway or live (non-test) Stripe keys, or push notifications;
- delete a page, a table, a column or any data;
- change an approved decision recorded in `docs/claude-code-brief.md`;
- use an external API not already in the project (and never the discontinued RxNav interaction API).
---

## 15. UI and frontend conventions

The look is a clean, calm clinical UI. **Keep the existing colours and theme**; improve layout,
spacing and states, not the palette.

**Type and tokens**
- One font: **Poppins**, loaded with `next/font` in `app/layout.tsx` (`--font-poppins`, Tailwind
  `font-sans`). Do not add other fonts.
- Use the Tailwind tokens in `tailwind.config.js`, never new hex values: `brand.blue` #2563EB,
  `brand.teal` #00BFA6, `brand.navy`, `ink` / `ink-muted` for text, `surface` / `surface-soft` /
  `surface-page` for backgrounds, `line` for borders. Radius `rounded-card` (16px) and
  `rounded-control` (12px); shadows `shadow-card`, `shadow-card-hover`, `shadow-focus`.
- The primary action is the blue→teal gradient (`Button variant="primary"`). One primary
  action per area; everything else is `secondary` or `ghost`. `danger` is for destructive actions.

**Shared components (use these before writing new markup)**
- `components/ui`: `Button` / `ButtonLink` (variants `primary | secondary | ghost | danger`,
  sizes `sm | md | lg`, `loading`, `icon`), `Card` / `CardHeader`, `TextField` / `TextAreaField` /
  `SelectField` (label, hint, error built in), `Badge`, `Alert`, `EmptyState`, `Skeleton` /
  `SkeletonCard`, `Spinner` / `PageLoader` / `ErrorState`, `StatCard` / `StatCardSkeleton`,
  `ConfirmDialog`, `NoraLogo`. `cn()` from `lib/cn.ts` joins class names.
- `components/layout`: `SitePage` + `SiteHeader` for public pages, `PageContainer` / `PageHeader`
  for page titles, `DashboardShell` for the doctor and admin dashboards. The patient dashboard
  uses its own layout in `components/patient/workspace/layout.tsx`.
- Keep files small: a component over ~250 lines gets split into sections (see
  `components/patient/workspace/` and `components/admin/AdminSections.tsx`).

**Every async state is visible**
- Buttons that start a request use `loading` and a verb label ("Saving...", "Approving..."), and
  related buttons are disabled until it finishes.
- Page and section data loads show a **skeleton shaped like the content**, not a bare spinner.
  `PageLoader` is only for the full-page session check.
- Errors show `ErrorState` or `Alert` with a retry. Empty data shows an honest `EmptyState` (section 7).
- Destructive actions (reject, delete) go through `ConfirmDialog`.
- A 429 from the API is an `ApiError` with `retryAfterSeconds`; show its message, do not retry in a loop.

**Hooks**
- Pages render; hooks fetch. Feature data lives in `hooks/<area>/use-*.ts` (for example
  `use-report-list`, `use-doctor-dashboard`, `use-admin-dashboard`) and calls only `lib/api.ts`.
- Protected pages start with `useAuthGuard(role)`: it confirms the session with `/auth/me`,
  signs out on 401/403 and sends the wrong role to its own dashboard.
- Generic hooks in `hooks/`: `useDebouncedValue` (search inputs, 200–300 ms),
  `useThrottledCallback` (scroll and resize handlers, ~100 ms), `usePagination`, `useScrollSpy`,
  `useMediaQuery` / `usePrefersReducedMotion`, `useAsyncAction`, `useToast`, `useStoredSession`,
  `useNotificationPermission`.
- Requests that can be superseded (search, filters) abort the previous one (see `use-report-list`).

**Lists and pagination**
- Paginated endpoints take `?limit=` (1–100, default 20) and `&offset=`, and return
  `{ items, total, limit, offset }` (`Page<T>` in `lib/types.ts`). Show "Load more" or pages from
  `total`; never assume one request returns everything.
- Search and filters run on the server (for example `GET /patient/reports?q=&department=&validation_status=`).
  Department slugs come from `lib/departments.ts`, which mirrors the backend list.

**Motion and 3D**
- Three.js is used **only** in the landing hero (`components/landing/HeroScene.tsx`), loaded with
  `next/dynamic` and `ssr: false` from a client component (`HeroVisual.tsx`). It renders a
  single still frame under `prefers-reduced-motion` and while scrolled out of view; static art
  (`HeroFallbackArt.tsx`) shows while it loads and when WebGL is unavailable. Do not add 3D elsewhere.
- `Reveal` keeps content visible without JavaScript; only elements below the fold animate in.
- Hover and press transitions are 200 ms; the scroll reveal is 500 ms. `prefers-reduced-motion`
  turns all of it off (`app/globals.css`). Motion never hides information.

**Layout, accessibility, icons**
- Design for 390px first. Flex and grid children that hold text get `min-w-0`; long emails and
  names use `break-words` / `truncate`. Check with `scripts/find-overflow.mjs`.
- Inputs always have a visible label (the field components do this). Keep the focus-visible ring.
  Loaders use `role="status"` with an `aria-label`.
- Icons are `lucide-react`. The app icons (`app/favicon.ico`, `app/icon.svg`, `app/apple-icon.png`,
  `public/icons/*`, used by `app/manifest.ts`) are generated by `scripts/generate-icons.py` from
  the `NoraLogo` mark; regenerate them, never hand-edit.
- AI output on screen carries the disclaimer from `buildMedicalDisclaimer()` in
  `lib/patient-dashboard.ts` (section 6.4).

---

## 16. Backend conventions

- **Settings:** read configuration only from `config.settings` (`backend/config.py`). A new
  environment variable gets a field and default in `Settings`, a line in `load_settings()`, and a
  placeholder in the root `.env.example`. Never call `os.getenv` in app code.
- **Routers stay thin:** parse the request, check identity and ownership, call a service, build
  the response. Rules, AI calls and data shaping go in `services/` (for example
  `services/medicine_safety.py`, `services/patient_insights.py`, `services/report_service.py`).
  Aim for files under ~400 lines.
- **Rate limits:** endpoints that cost money or protect accounts (login, signup, uploads, OCR, AI,
  access codes) use `@limiter.limit(...)` from `rate_limit.py` and take `request: Request`.
  Everything else gets the default limit. Limits are defaults in `backend/config.py`.
- **Pagination:** list endpoints that can grow use `page_params` and `paginate()` from
  `pagination.py` and return `Page[T]`. Validate filter values and return 422 for unknown ones.
- **Response models:** use plain `str` for emails in output models; `EmailStr` belongs on inputs only.
- **Logging:** `logging.getLogger("nora.<area>")`. Never log one-time codes, passwords, tokens,
  phone numbers or medical text (section 8).
- **Style:** ruff with the settings in `backend/pyproject.toml` (line length 120, import sorting).
  Format-only changes go in their own commit.
