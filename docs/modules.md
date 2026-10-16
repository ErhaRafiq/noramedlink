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
| FE-4 | Link each profile with records, appointments, prescriptions and payment history | Done | `activity` on `GET /profile`; the profile page links each count to its page |

## Module 2: Unified Patient Health Record Repository (UPHRR)

Not in the requested scope of this pass; reports, vitals, medicines and clinical notes exist (see `docs/claude-code-brief.md`).

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
| FE-4 | Confirmations and reminders to patients and doctors | Done (in-app) | `services/notifications.py`, `GET /notifications`, `/notifications` page and bell: confirmation, move and cancel notices, plus 24-hour and 1-hour reminders for both people. Email or SMS needs a provider and is not configured |

## Module 6: On-Demand Doctor Home Visit Engine

Not in this pass. Home-visit requests are recorded honestly (no invented doctor or ETA).

## Module 7: Intelligent Symptom Analysis and Doctor Recommendation

Not in this pass.

## Module 8: Payment and Billing Management

| ID | Feature | Status | Where |
|---|---|---|---|
| FE-1 | Secure online payments for consultations, appointments and home visits | Partial | Consultations and appointments: Stripe Checkout at the doctor's fee (`services/payments.py`, `/payments`); the server sets the amount and only Stripe's signed webhook marks a payment paid. Home visits cannot be paid: the home-visit engine (Module 6) is not built |
| FE-2 | Third-party payment gateway | Done (test mode) | Stripe, hosted payment page, signed webhook, each event applied once. No live keys; no other gateway |
| FE-3 | Invoices, receipts and transaction history | Done | Payment history on `/payments`; printable receipt on `/payments/receipt?id=` (`GET /payments/{id}`, owner only) with invoice number and reference. A prototype receipt, not a tax invoice; no PDF export |
| FE-4 | Refunds, cancellations and payment status tracking | Done | Cancelling a paid appointment (patient or doctor) asks Stripe for a full refund: `REFUND_PENDING`, then `REFUNDED` only on Stripe's `charge.refunded` webhook. If the refund cannot be requested the cancellation stands and the payment shows `REFUND_FAILED` with the reference to quote to support. No partial refunds and no admin refund screen yet |

## Module 9: Unified Dashboard and Admin Panel

Not in this pass (dashboards exist; see the brief).
