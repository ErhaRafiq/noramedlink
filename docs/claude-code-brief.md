# Nora MedLink: Implementation Brief for Claude Code

You are continuing development of **Nora MedLink**, a final-year project (BS Data Science, COMSATS Islamabad) by Erha Rafiq and Momna Javed. It is an academic prototype of an AI-assisted healthcare platform: unified patient health records, AI clinical summaries, advisory medication-safety alerts, doctor search and booking, home visits, and symptom-to-specialist guidance.

The project is roughly 30% implemented. Your job is to take it further in **phases**, one phase at a time, stopping for review after each.

---

## 1. How to work

- **Start every phase with a plan.** Read the relevant code, list the files you'll change and the approach, then **stop and wait for approval** before editing.
- **One phase per branch** (`phase-0-security`, `phase-1-consolidate`, ...). Small, focused commits with clear messages.
- **Read `AGENTS.md` first.** This repo uses **Next.js 16**, which has breaking changes. Check `node_modules/next/dist/docs/` before writing Next-specific code (route handlers, params, caching).
- **Dev environment is Windows.** Give commands in PowerShell-compatible form.
- **Never commit secrets.** Never print, read aloud, or copy values from `.env` / `backend/.env`. Only edit `*.env.example` files, and only with placeholder values.
- **Never destroy data.** Migrations must be additive. Do not drop tables or columns without asking. Do not run `prisma migrate reset` or anything equivalent.
- **Don't break what works.** OCR upload, AI report summaries, department tiles, reminders, vitals, and the doctor-unlocks-patient-dashboard-via-OTP flow all work today. Keep them working.
- **Verify before claiming done.** Run `npm run lint`, `npm run build`, and the backend tests. Show the output. If something can't be tested locally, say so plainly.
- **When unsure, ask.** Especially about anything listed under "Open decisions" below.

---

## 2. Current state (after Phase 0 and Phase 1)

### Real stack
| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind |
| Backend | **FastAPI** in `backend/` using **SQLAlchemy**: the only backend. Next.js keeps a same-origin proxy (`app/api/backend/[...path]`), thin auth proxies (`app/api/auth/login`, `signup`) and `app/api/drug-check` (OpenFDA, not used by any page yet) |
| Database | PostgreSQL. Schema = SQLAlchemy models + **Alembic** migrations (`backend/migrations/`, head `0009`: `clinical_summaries`), applied by `alembic upgrade head` at startup. Migrations are additive. **No Prisma** (removed in Phase 1) |
| OCR | Local OCR in FastAPI by default: PDF text layers, then RapidOCR 3 with PP-OCRv5 (ONNX, CPU, models cached in `backend/models/`) for scans and photos, rebuilt into table rows; numbers scored under 0.90 are listed to check against the original. OCR.space only when `OCR_SPACE_API_KEY` is set. No Tesseract anywhere |
| AI | Gemini, OpenAI and Groq via env keys (Gemini first), rule-based fallback when no key, BioBERT NER (`d4data/biomedical-ner-all`). Identifiers removed before prompts leave the server; AI summaries with numbers not in the report are rejected |
| Auth | JWT (HS256) issued by FastAPI, stored in `localStorage` on the client; FastAPI role dependencies (`require_patient`, `require_doctor`, admin) on every protected endpoint |
| Tests | `tests/acceptance_test.py`: route authentication, ownership and access-grant checks against the local stack (see README) |

There is **no** Flutter app and **no** Node gateway, despite what the design documents say. Don't create them.

### Module status
| # | Module | Status | Notes |
|---|---|---|---|
| 1 | Auth & profiles | Mostly done | JWT, patient/doctor/admin roles, admin invite code, doctor approve/reject in `backend/routers/admin.py`, inactive accounts get 403. Signup is direct: the OTP signup routes (`request-otp`, `verify-otp-signup`) return 410 |
| 2 | Unified health records | Partial | Reports in `patient_reports` (upload, OCR, department categorisation, file access only for the owner or a granted doctor), BP/sugar log, detailed vitals, medicine schedules with reminders. **Missing:** audit log, versioning, structured allergies / diagnoses / chronic conditions |
| 3 | Clinical summary (ICSE) | Partial | Report summaries with rule fallback, doctor summaries, BioBERT service; `/nlp/summarize` requires sign-in |
| 4 | Medication safety (MSCIE) | Early | Patient-side check in `backend/routers/patient.py` (`/medicine-safety/check`); the LLM can still raise its status (to fix in 3b). `app/api/drug-check` (OpenFDA) is unused. **Missing:** doctor-side prescription flow, interaction rules, alternatives, override log |
| 5 | Doctor search & booking | Partial | `app/doctors/page.tsx` and booking on the patient dashboard; only verified doctors are bookable. **Missing:** filters, availability slots, double-booking prevention |
| 6 | Home visit | Not started | `EmergencyBooking` requests are recorded honestly (status `REQUESTED`, no doctor, no ETA), but nothing assigns a doctor (conflicts with scope limitation LI-5; replaced in 2d) |
| 7 | Symptom → specialist | Not started | The generic AI chat was removed in Phase 1 |
| 8 | Payments | Partial | Manual/wallet payments are recorded as `PENDING` until an admin confirms; only admins can update payments. JazzCash/Easypaisa are env placeholders only |
| 9 | Admin panel | Partial | Overview stats, doctor verification, payment confirmation, all admin-only in FastAPI. **Missing:** audit log view |

### Dashboards
- **Patient:** `/dashboard/patient` (`components/patient/PatientWorkspace.tsx`): reports and upload, BP/sugar log, today's detailed vitals, medicines and reminders with browser pop-ups, appointments, risk flags, AI summary, and the one-time doctor access code. `/dashboard` redirects here.
- **Doctor:** `/dashboard/doctor` (`components/dashboard/DoctorDashboard.tsx`): code unlock, appointments, patient file (vitals, reports, medicines) while a grant is active, end consultation, emergency visits. `/doctor-dashboard` redirects here.
- Both show only real data, with empty states when there is none.

### Known problems

**Resolved in Phase 0 and Phase 1**
1. ~~Insecure routes taking identity from `?userId=` or the body~~: identity comes only from the verified token; the affected Next routes were ported to FastAPI or removed, and the acceptance tests cover them. Doctor access needs an active grant; OTP unlock is limited to 5 failures per 15 minutes.
2. ~~Two backends, one database~~: FastAPI is the only backend, Alembic owns the schema, Prisma is gone. `MedicalRecord`/`MedicalDocument` were reconciled into `patient_reports` (migration 0008). The tables missing from `create_all` databases (`medicine_reminders`, `patient_vitals`, `reminder_logs`) now have models and migrations.
3. ~~Committed runtime files~~: `*.log` is ignored and untracked; `eng.traineddata` was removed with `tesseract.js`.
4. ~~Duplicate UIs~~: `app/dashboard/page.tsx` and `app/doctor-dashboard/page.tsx` were merged into `/dashboard/patient` and `/dashboard/doctor` and replaced by redirects.
5. ~~OCR documented as Tesseract; uploads failed silently~~ *(found and fixed on `ui-refresh`)*. The README said reports were read with Tesseract (pytesseract + OpenCV, `TESSERACT_CMD`), but no code ever used Tesseract: the backend's only OCR was OCR.space, and no key was configured. Every upload therefore failed while looking successful: `201 Created`, `ocr_status = FAILED`, the error message ("OCR_SPACE_API_KEY is missing...") stored as the report's **summary**, `validation_status` left at the column default **SAFE** (shown as safe / "No rule alerts"), and a dashboard toast saying "OCR and AI summary were saved". Fixed: local OCR (PDF text layers, then RapidOCR) with OCR.space only when a key is set; an unreadable file is saved as `NOT_VALIDATED` with no summary, and the toast and report page say why; older failed reports are shown the same way; the README describes the real pipeline. OCR quality is being benchmarked on `ocr-quality`.

**Still open**
1. **Two vitals tables.** `vitals` (free-text BP + sugar, written by the patient dashboard's vitals form, read by the doctor's patient file) and `patient_vitals` (detailed readings, shown as "Today's Vitals"; no form writes it). Merge them in a later phase.
2. **`medical_documents` is a dead, read-only table.** Its rows were copied into `patient_reports`; SQLAlchemy rejects any write to it. It is kept, not dropped, and `medical_ai_analyses.medical_record_id` still references it.
3. **`reminders` table has no UI.** The free-text reminder form was dropped in Phase 1; the rows and the FastAPI `/reminders` endpoints remain.
4. **Emergency requests are never assigned to a doctor**, so the doctor dashboard's emergency list stays empty for new requests. Addressed by the home-visit flow (2d).
5. **Patient sub-routes are not separate views.** `/dashboard/patient/records`, `/upload`, `/summary`, `/profile` and `/ocr-results` all render the full workspace (`initialView` is ignored), though the landing page links to them.
6. **Doctor overview lists are capped** (30 appointments, 12 emergency visits, 40 reports), and the stat cards count those lists.
7. **Leftover client code:** `app/emergency`, `app/payments` and `app/summarize` still gate on `localStorage.userId` (not sent to the server); a few `lib/api.ts` methods (`patientOverview`, `addReminder`) have no caller; `npm run lint` shows 9 unused-variable warnings.
8. **JWT in `localStorage`** is readable by any script on the page; acceptable for the prototype, worth noting in the report.

---

## 3. Architecture decision (already made)

**FastAPI is the single backend.** It issues the JWTs, has proper role dependencies (`require_patient` etc.), and all AI code is Python.

- New business logic goes into FastAPI routers.
- Next.js API routes become **thin authenticated proxies** (see `app/api/backend/[...path]/route.ts` and `lib/backend-auth-proxy.ts`), or are removed once the frontend calls FastAPI through the proxy.
- **SQLAlchemy models are the source of truth for the schema.** Prisma is retired once no route depends on it.
- Migrations: introduce **Alembic** with a baseline matching the current live database, then stop relying on `create_all` / `ensure_schema_compatibility` for schema changes.

---

## 4. Safety rules for all medical features

These are project requirements (scope limitations LI-1 and LI-5), not suggestions:

- The system is **advisory only**. No output may diagnose, prescribe, or state that a medicine is definitely safe. Use wording like "potential interaction", "for physician review".
- **Deterministic rules decide risk; the LLM only explains.** An LLM response must never raise or lower a safety status on its own. If the knowledge base has no data, say "no data", not "safe".
- **Red-flag symptoms get a hard emergency redirect.** Show "Call 1122 or go to the nearest emergency department" and **do not** offer booking or home visits for that request.
- Every AI output shown to a user carries a short "AI-generated, advisory, verify with a clinician" note.
- Log physician overrides of safety alerts with a required justification.
- Only verified doctors are discoverable by patients.

---

## 5. Phases

### Phase 0: Security hygiene *(do this first)*

1. Create `lib/server-auth.ts` exporting `requireUser(request, allowedRoles?)`, which verifies the Bearer JWT (reuse the verification logic in `lib/patient-session.ts`), loads the user, and returns `401` (no/invalid token) or `403` (wrong role).
2. Patch every route listed under "Known problems → 1" to use it. The user ID must come **only** from the verified token. Remove `?userId=` handling.
3. Update frontend callers (`app/dashboard/page.tsx`, `app/doctor-dashboard/page.tsx`, `app/admin/page.tsx`, `app/emergency/page.tsx`, `app/payments/*`, etc.) to send `Authorization: Bearer <token>` using `getSession()` from `lib/auth.ts`, and stop sending `userId`.
4. Ownership checks: a patient can only touch their own records; a doctor can only see a patient's data while an active `PatientDashboardAccess` grant exists; admin routes require role `admin`.
5. Add `*.log` to `.gitignore` and `git rm --cached` the tracked log files. Check whether `eng.traineddata` is actually loaded by `tesseract.js` before touching it; if it's needed, leave it and tell me.
6. **Acceptance tests** in `tests/acceptance_test.py` (a small HTTP test script, extended as routes move to FastAPI):
   - No token → 401 on every patched route.
   - Patient token on an admin route → 403.
   - Patient A cannot read or delete Patient B's records.
   - Doctor without an access grant cannot read a patient's dashboard.

#### Phase 0: approved decisions (already agreed with the team)

- Also patch these routes, with these roles:
  - `ocr/extract`, `ai/analyze-report`: any signed-in user
  - `dashboard/access-otp`: patient only
  - `doctor/access/unlock`, `doctor/access/end`: doctor only
- Signup/login OTP routes (`request-otp`, `verify-otp-signup`) stay public: users have no token before signing up.
- `eng.traineddata` stays where it is. *(Phase 1: removed once `tesseract.js` was dropped. Correction: OCR runs in FastAPI through OCR.space only; the backend has no Tesseract code.)*
- Tests may create temporary `phase0-test-` users in the dev database, on these conditions:
  - Before creating anything, confirm `DATABASE_URL` points to localhost (parse and check the hostname only; never print the value).
  - Cleanup runs in a teardown/finally block, so it happens even when tests fail.
  - Delete only `phase0-test-` users and their related rows, nothing else.
- Work on a `phase-0-security` branch in the real git clone, never in a ZIP download.
- Roles: the system has exactly three roles (patient, doctor, admin), as defined in the SDS. There is no pharmacist role; do not add one.

### Phase 1: Consolidate onto FastAPI

1. Produce an inventory table: every `app/api/**` route → does an equivalent FastAPI endpoint exist? → action (proxy / port / delete). Show it to me before changing anything.
2. Port missing logic to FastAPI **one feature area per commit** (vitals, reminders, payments, admin, doctor access, emergency, medical records).
3. Reconcile duplicate models (e.g. `MedicalRecord` vs `MedicalDocument`) with a data-preserving migration. Propose the mapping first.
4. Add Alembic with a baseline of the current schema.
5. Once no route imports `@/lib/prisma`, remove Prisma (dependency, `prisma/`, `prisma.config.ts`, `lib/prisma.ts`) in a separate, clearly-labelled commit.
6. Everything that worked before must still work. List what you manually verified.

#### Phase 1 notes (found during Phase 0)

- **Missing tables.** A database created by FastAPI's `create_all` lacks three tables that the Prisma schema defines: `medicine_reminders`, `patient_vitals`, `reminder_logs`. The Next routes `patient/vitals`, `patient/vitals/today`, `patient/vitals/trends`, `reminders/create`, `reminders/today`, `reminders/[id]/mark-taken`, `reminders/[id]/skip` and `ai/chat` use them and fail on such a database. Resolve this in the inventory (step 1) and the Alembic baseline (step 4): either add SQLAlchemy models for them or port/remove those routes.
- **Schema drift between Prisma and SQLAlchemy.** Phase 0 found that SQLAlchemy lacked the `(doctor_id, patient_id)` unique constraint on `patient_dashboard_access` (now added to the model). Databases created before that fix need it applied once. When building the Alembic baseline, compare all Prisma `@@unique` / `@@index` declarations with the live schema.

### Phase 2: Patient-facing modules *(Momna's modules)*

**2a. Symptom → specialist mapper (Module 7, FR-13.x)**
- FastAPI router `backend/routers/symptoms.py` + page `app/symptoms/page.tsx`.
- Step 1, **red-flag detector** (pure Python, no LLM): keyword/phrase rules for chest pain, difficulty breathing / shortness of breath, stroke signs (face drooping, slurred speech, one-sided weakness), severe bleeding, loss of consciousness, seizures, suicidal thoughts, severe allergic reaction, high fever in infants. Any hit → emergency redirect response, no specialist list.
- Step 2, **specialty mapping**: a rule table mapping symptom keywords to a fixed list of specialties. Optionally use the LLM as a classifier constrained to that fixed list; if the LLM returns anything outside the list, fall back to General Physician.
- Step 3, **ranked doctors**: query verified doctors by specialty; rank by specialty match, availability, rating, fee. Link directly to booking (FR-13.4).
- Save each session (input, red-flag result, specialty, timestamp) for the admin stats.
- Unit tests, including: `"Chest pain, dizziness, shortness of breath"` → **emergency redirect** (not "Cardiologist, Medium"), `"itchy rash on arm for a week"` → Dermatology, `"fever and sore throat for 2 days"` → General Physician.

**2b. Doctor search (FR-3.x, FR-11.x)**
- Filters: specialty, city, fee range, minimum rating, available today, consultation mode (video / in-person / home visit). Partial, case-insensitive name/specialty matching. Verified doctors only. Filters combine without resetting each other.

**2c. Appointments (FR-4.x, FR-12.x)**
- Doctor availability model (weekly slots). Only free slots are selectable. Prevent double-booking with a DB unique constraint on (doctor, start time) plus a server-side check.
- Reschedule and cancel in the UI; past appointments move to "Past" automatically.
- In-app notifications on booking, reschedule, and cancel (the `Notification` model exists).

**2d. Home visit engine (Module 6)**
- Replace `EmergencyBooking` with a `HomeVisitRequest` flow. Keep old emergency data readable; propose the migration first.
- States: `requested → accepted → en_route → arrived → completed`, plus `cancelled` / `declined`. Enforce valid transitions server-side.
- Doctors opt in to home visits and set a service radius. Match by distance (Haversine on stored coordinates), specialty, and availability.
- Location uses the existing `NEXT_PUBLIC_MAP_PROVIDER=mock` path by default; Google Maps only when a key is configured.
- Run the red-flag detector on the patient's reason at request time; red flags block the request and show the emergency redirect.

### Phase 3: Clinical safety modules *(Erha's modules)*

**3a. Structured health record fields**
- Add structured `allergies`, `diagnoses`, and `chronic_conditions` for patients (tables, not free text), editable by the patient and by doctors with an active access grant.

**3b. MSCIE: doctor-side prescription safety (Module 4, FR-10.x)**
- `Prescription` + `PrescriptionItem` models; doctors draft a prescription for a patient during an active access grant.
- Before confirmation, run checks:
  - **Drug normalisation** with RxNorm (RxNav `rxcui` lookup) so brand/generic names match.
  - **Drug–drug interactions** from a curated local rules table (`backend/data/interactions.csv`: drug A, drug B, severity, mechanism, advice), seeded with common, well-documented pairs (e.g. warfarin + NSAIDs, metformin + iodinated contrast, ACE inhibitors + potassium-sparing diuretics, SSRIs + MAOIs). Mark it clearly as a demo knowledge base. Do **not** use the NLM RxNav drug-interaction API; it was discontinued in 2024.
  - **Label cross-check** via OpenFDA drug labels (`drug_interactions`, `contraindications` sections), reusing `app/api/drug-check` logic moved into FastAPI.
  - **Allergy conflicts** against the structured allergies from 3a.
- Alerts show severity (colour-coded per UI-6: green / yellow / red), reason, source, and curated safer alternatives where the table has them.
- Physician can accept an alternative or **override with a required justification**; overrides go to the audit log.
- Change the existing patient-side check so the LLM only adds explanation text and can no longer change the status.

**3c. Audit log (FR-8.3, FR-14.3)**
- `AuditLog` model (actor, role, action, target type/id, timestamp). Record: record views/edits, access grants, prescription confirmations, overrides, admin actions. Admin page to filter and view.

### Phase 4: Finish and document

- Payments: keep a sandbox/manual provider working end to end (create → pending → paid / refunded, invoice view). No real gateway unless asked.
- Push notifications only if FCM keys are configured; otherwise in-app only.
- Tests: backend pytest suite for auth, ownership, red flags, interaction rules, and state transitions.
- Update `README.md` (setup, env vars, run commands).
- Write `docs/DOCS_VS_CODE.md`: a table of every place the SRS/SDS describes something different from the code (e.g. Flutter, Node gateway, Kubernetes), so the team can update the documents.

---

## 6. Open decisions (ask before implementing)

- **Pharmacist role.** The SRS describes a pharmacist collaborating in consultations; the Scope document and the SDS do not include it. Do not add a pharmacist role until the team confirms.
- **Payment gateway.** JazzCash / Easypaisa integration only if explicitly requested.
- **Removing old UIs.** Don't delete `app/dashboard/page.tsx` or `PatientWorkspace.tsx`; propose a merge plan instead.

---

## 7. First task

Begin with **Phase 0**. Read `AGENTS.md`, `lib/patient-session.ts`, `lib/auth.ts`, and the 15 routes listed above. Then reply with your plan (files to change, the `requireUser` design, how the frontend will send the token, and the test approach) and **wait for my approval** before editing.
