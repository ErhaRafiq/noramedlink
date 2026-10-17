# Nora MedLink: modules and features

The project scope, kept here for reference, with the status of every feature in the code.
Statuses: **Done** (built and tested), **Partial** (built, with a stated gap), **Not built**.
Update the status column in the same commit that changes a feature.

Not a medical device: every medical feature is advisory (AGENTS.md section 6).

## Module 1: User and Profile Management

| ID | Feature | Status | Where |
|---|---|---|---|
| FE-1 | Secure registration and login for patients, doctors and administrators with encrypted credentials and role-based access control | Done | `routers/auth.py`, `services/sessions.py`, `dependencies.py`; HttpOnly cookie sessions |
| FE-2 | Manage personal profile (age, gender, contact details, medical role) | Done | `routers/profile.py`, `services/profiles.py`, `/profile` page: name and phone for everyone; date of birth (age is computed), gender, blood group, city, address and emergency contact for patients; CNIC shown masked |
| FE-3 | Doctor profiles: specialization, qualifications, availability, consultation fees, verification status | Done | Qualifications, experience, languages, city, consultation types, fee, bio and verification (specialization and PMDC number are locked to the admin) on `/profile`; weekly availability in `components/profile/AvailabilityEditor.tsx` (`GET/PUT /doctor/availability`) |
| FE-3b | Doctor verification: PMDC registration number | Done | Signup checks the number's form and stores it as `12345-P` (`services/pmdc.py`, mirrored in `lib/pmdc.ts`). The admin checks it on the PMDC public register ("Check on PMDC") or decides by hand with a written reason; `doctor_profiles.pmdc_verified` is true only for found + ACTIVE + matching name, or the admin's decision. A doctor can be approved and active without it; a verified doctor shows a "PMDC verified" badge and can be filtered. Details below |
| FE-4 | Confirmations and reminders to patients and doctors | Done (in-app and email) | `services/notifications.py`, `GET /notifications` (+ unread-count, read, read-all, dismiss), `/notifications` page, bell with a dropdown and live toasts: events for patients, doctors and admins (bookings, moves, cancels, visits, payments, refunds, prescriptions, record access, doctor reviews) with links, plus 24-hour, 1-hour and 5-minute reminders. Email via Resend (`docs/email.md`) |

### Email (Resend): confirmation, password reset, appointment emails and reminders

Full detail, limits and setup in `docs/email.md`. In short:

- **Sign-up** creates an unconfirmed account and emails a link (24 hours, once). Nothing is blocked; a banner on the
  dashboards and profile offers a new link (one a minute, 3 an hour). Accounts that existed before keep their flag.
- **Forgot password** (`/forgot-password`): a 6-digit code by email (10 minutes, 5 tries, once). The answer is the same
  for every address. A reset signs the account out everywhere, confirms the address and sends a "password changed" notice.
- **Appointments**: a booking, move or cancellation emails the patient and the doctor (Pakistan time, type, the other
  person's name, never the reason). A reminder goes 5 minutes before the visit unless the person switched it off
  in `/profile`; it is withdrawn if the appointment moves or is cancelled and dropped if it could not go in time.
- **Not a cron job**: the reminder row is written at booking and a loop inside the server sends rows that are due. On a
  free host that sleeps, an uptime monitor pinging `/health` every 5 minutes keeps it awake.
- **Rate limits** on every endpoint that causes an email (per IP, per address, and per account in the database).
- **Not built:** a daily send cap (left to you), email change, an unsubscribe link (transactional email only), calendar
  attachments, SMS.

### Doctor PMDC verification (how it works)

- **The number:** the PMDC register searches an exact number written like `12345-P` (digits, a hyphen, one letter; letters seen: P, N, S, D; four or five digits are usual). `12345P`, `12345/P` and `12345` find nothing there. PMDC publishes no format document, so the rule is deliberately broad: 3 to 7 digits and any one letter, any case, with an optional "PMDC", "PM&DC", "PMC" or "Reg. No." in front. Signup refuses anything else with an example. Existing doctors keep what they entered; a number that does not fit shows "Number not recognised" to the admin.
- **The check:** `POST /api/admin/doctors/{id}/pmdc-check` asks the register's free public search (the same call pmdc.pk makes; only the number is sent). Outcomes: `verified` (found, ACTIVE, name matches), `inactive`, `name_mismatch`, `not_found`, `format_invalid` (no request is made). If the register cannot be reached, nothing is changed and the admin is told so. A later check can take the badge away.
- **Name match:** every word of the shorter name must match a word of the longer one (about 88% alike, with the common spellings of Muhammad and Ahmad folded together), at least two words unless both names have one. The number is already unique, so this only guards against a typo or a borrowed number; it is not an identity check.
- **By hand:** `PUT /api/admin/doctors/{id}/pmdc-verified` with a reason of at least ten characters (for example after looking the doctor up on pmdc.pk). The reason stays on the profile, not on the public card or in the audit log.
- **Approval is separate:** approving never needs PMDC verification. Approval does try a check best-effort so a doctor who checks out gets the badge without another click; any failure is ignored.
- **Who sees what:** patients see the badge, its date and the "PMDC verified only" filter; never the number, the register's name or the note. The doctor sees their own status on `/profile`. The admin sees everything above.
- **Outside service:** `https://hospitals-inspections.pmdc.pk/api/DRC/GetData` (no key, no sign-in). Switch off with `PMDC_LOOKUP_ENABLED=0`; `DISABLE_PAID_SERVICES=1` switches it off too, so tests never call it. Rate limited per admin. The endpoint is PMDC's own website's search, not a documented API: it can change, which is why a failure is never read as "not verified".
- **Not built:** automatic re-checks on a schedule, checking at signup, or a check by CNIC or name.

## Module 2: Unified Patient Health Record Repository (UPHRR)

Reports, vitals, medicines and clinical notes were built earlier (see `docs/claude-code-brief.md`). This pass
added the structured record and the audit trail.

| ID | Feature | Status | Where |
|---|---|---|---|
| Structured allergies, diagnoses and long-term conditions | Tables, not free text, editable by the patient and by a doctor with an active grant | Done | `patient_health_entries` (migration 0017), `services/health_record.py`, `routers/health_record.py`; `HealthRecordPanel` on the patient dashboard ("My health record") and in the doctor's patient file. A doctor can add and change entries but not remove them; the patient sees who added each. Nothing is hard-deleted ("removed" hides, "resolved" keeps history) |
| The medication check uses the record | Active entries the knowledge base recognises reach MSCIE (`services/mscie/context.py`), labelled "health record (added by you / a doctor)". A word the check does not know is kept but marked "Not used by the check", never guessed at | Done | `services/health_record.recognised` |
| Audit log | Who viewed or changed whose record, and when | Done | `audit_logs` (migration 0017), `services/audit.py`. Logged: a doctor's view of a record area or a file (once per 10 minutes), one-time codes, access grants and endings, health entry add/change/remove, prescription confirm and cancel, safety overrides, admin approve/reject of doctors. A row holds no medical text. Not logged yet: the patient's own report uploads and deletes, logins |
| Patient access history | The patient sees who else opened or changed their record | Done | `GET /patient/access-history`, "Who has seen my record" on the patient dashboard |
| Versioning of record entries | Earlier values of an entry | Not built | Changes are in the audit log (that something changed, not the old value); clinical summaries are versioned (Module 3) |

## Module 3: Intelligent Clinical Summary Engine (ICSE)

| ID | Feature | Status | Where |
|---|---|---|---|
| FE-1 | Extract diseases, medications, allergies and test results with NLP | Done | `services/icse/entities.py`, `services/biobert_service.py` |
| FE-2 | Concise, clinically relevant summaries for physician review | Done | `services/icse/summary.py`, `routers/clinical_summary.py` |
| FE-3 | Highlight critical flags: high-risk conditions, chronic illnesses, ongoing treatments | Done | `services/icse/flags.py`, `services/lab_rules.py` |
| FE-4 | Update summaries dynamically as new data is added | Done | `services/icse/versions.py` (fingerprints, regenerate) |

## Module 4: Medication Safety and Clinical Interaction Engine (MSCIE)

| ID | Feature | Status | Where |
|---|---|---|---|
| FE-1 | Detect drug-drug interactions, drug-disease contraindications, allergy conflicts, dosage risks | Done | `services/mscie/engine.py`, CSV rules + DDInter |
| FE-2 | Real-time safety alerts with explanations before a prescription is confirmed | Done | `routers/mscie.py`, `components/dashboard/doctor/prescribe/` |
| FE-3 | Suggest safer alternatives | Done | `services/mscie/alternatives.py` |
| FE-4 | Rank alternatives (health profile, previous response, severity) | Done | `ranking_weights.csv` |
| FE-5 | Transparent reasoning, no automated decisions | Done | alert evidence + sources; score breakdown |
| FE-6 | Physician override and manual choice (human in the loop) | Done | written justification in `safety_overrides` |

## Module 5: Doctor Search and Appointment Booking

| ID | Feature | Status | Where |
|---|---|---|---|
| FE-1 | Search doctors by specialization, location, availability, ratings, fees | Done | `GET /appointments/doctors` (query, specialty, city, consultation type, available today, max fee, min rating, sort); `components/doctors/DoctorFilters.tsx`. Ratings and next-open times are real; a doctor with no fee or rating is never matched by a fee or rating limit |
| FE-2 | Real-time availability for online or in-person consultations | Done | `services/scheduling.py`: weekly windows cut into slots (clinic time, UTC+5), `GET /appointments/doctors/{id}/slots`; taken and too-soon slots are shown closed; consultation types online / in clinic / home |
| FE-3 | Book, reschedule or cancel appointments | Done | `services/appointments.py`; one live booking per doctor and time (database unique index plus a check); a patient cannot hold two overlapping visits; move/cancel only before the visit starts; the doctor completes, marks a no-show or cancels; completed visits can be rated once |
| FE-4 | Confirmations and reminders to patients and doctors | Done (in-app and email) | `services/notifications.py`, `GET /notifications`, `/notifications` page and bell: confirmation, move and cancel notices, plus 24-hour and 1-hour reminders for both people. Email or SMS needs a provider and is not configured |

## Module 6: On-Demand Doctor Home Visit Engine

Not in this pass. Home-visit requests are recorded honestly (no invented doctor or ETA).

## Module 7: Intelligent Symptom Analysis and Doctor Recommendation

Rules only, no AI: deterministic rules decide, which is also what AGENTS.md section 6 requires.

| ID | Feature | Status | Where |
|---|---|---|---|
| FE-1 | Describe symptoms in free text and get the kind of specialist to see | Done | `POST /symptoms/check` (open to visitors, rate limited per IP), `services/symptom_checker.py`, tables `symptom_specialties.csv` and `specialties.csv`; `/symptoms` page. English only. Up to three specialties, each with the words that pointed to it; no match falls back to a general physician and says so |
| FE-2 | Red-flag symptoms get a hard emergency redirect | Done | `red_flags.csv` (chest pain, breathing, stroke signs, severe bleeding, loss of consciousness, seizure, self-harm, severe allergy, fever in a baby, sudden severe headache, overdose). A hit returns "Call 1122 or go to the nearest emergency department." with no specialist and no booking. A sign the patient says they do not have ("no chest pain", "never had a seizure") does not count; anything unclear is treated as a warning sign |
| FE-3 | Recommend verified doctors and link to booking | Done | Verified, active doctors of the suggested specialty, ranked by next opening, rating, then fee (`rank_doctors`); the same booking dialog as the doctor search, with the times that clash with the patient's own visits closed |
| FE-4 | Keep sessions for the admin | Done | `symptom_sessions` (migration 0016: text, red-flag ids, top specialty, user if signed in); `GET /api/admin/symptom-stats` returns counts only, shown on the admin dashboard. The text stays in the database and is never logged or shown to the admin |

Not built: an LLM classifier (not needed; the rules decide), languages other than English, Roman Urdu or Urdu. The tables are a demo knowledge base and have not been clinically reviewed.

## Module 8: Payment and Billing Management

| ID | Feature | Status | Where |
|---|---|---|---|
| FE-1 | Secure online payments for consultations, appointments and home visits | Partial | Consultations and appointments: Stripe Checkout at the doctor's fee (`services/payments.py`, `/payments`); the server sets the amount and only Stripe's signed webhook marks a payment paid. Home visits cannot be paid: the home-visit engine (Module 6) is not built |
| FE-2 | Third-party payment gateway | Done (test mode) | Stripe, hosted payment page, signed webhook, each event applied once. No live keys; no other gateway |
| FE-3 | Invoices, receipts and transaction history | Done | Payment history on `/payments`; printable receipt on `/payments/receipt?id=` (`GET /payments/{id}`, owner only) with invoice number and reference. A prototype receipt, not a tax invoice; no PDF export |
| FE-4 | Refunds, cancellations and payment status tracking | Done | Cancelling a paid appointment (patient or doctor) asks Stripe for a full refund: `REFUND_PENDING`, then `REFUNDED` only on Stripe's `charge.refunded` webhook. If the refund cannot be requested the cancellation stands and the payment shows `REFUND_FAILED` with the reference to quote to support. No partial refunds and no admin refund screen yet |

## Module 9: Unified Dashboard and Admin Panel

Dashboards exist for the patient, doctor and admin (see the brief).

| Item | Status | Where |
|---|---|---|
| Admin: doctor verification, account overview, recent activity | Done | `components/admin/` |
| Admin: audit log view with filters | Done | "Who accessed or changed records" on `/admin`: filter by action, role and patient number, 15 rows at a time (`GET /api/admin/audit-log`). Rows cannot be edited or deleted |
| Admin: symptom checker usage | Done | counts only (Module 7) |
| Admin: PMDC verification | Done | "All doctors and PMDC verification" on `/admin` (filter by approval, PMDC status, name or number) and a PMDC panel on every pending doctor: check on the register, decide by hand, open the PMDC site |
| Admin: payment confirmation | Removed on purpose | Only Stripe's signed webhook marks a payment paid (Module 8) |
| Report explainer | A report in everyday words, and questions about it | Done | `services/report_explainer.py`, `GET /patient/reports/{id}/explanation`, `POST .../ask`, "Your report in simple words" on the report page: where each result sits against the usual range (gauge), what the test is, what higher or lower can be linked to (`lab_meanings.csv`), explain-more per result and an ask box. Fixed rules decide; an AI may only re-word behind number and banned-phrase guards; emergencies get 1122, treatment and diagnosis questions are refused. Questions are not stored. Machine-generated note on every answer |
