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
| FE-3 | Doctor profiles: specialization, qualifications, availability, consultation fees, verification status | Partial | Done: qualifications, experience, languages, city, consultation modes, fee, bio, verification (specialization and PMDC number locked to the admin). Availability: step 2 |
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
| FE-1 | Search doctors by specialization, location, availability, ratings, fees | | |
| FE-2 | Real-time availability for online or in-person consultations | | |
| FE-3 | Book, reschedule or cancel appointments | | |
| FE-4 | Appointment confirmations and reminders to patients and doctors | | |

## Module 6: On-Demand Doctor Home Visit Engine

Not in this pass. Home-visit requests are recorded honestly (no invented doctor or ETA).

## Module 7: Intelligent Symptom Analysis and Doctor Recommendation

Not in this pass.

## Module 8: Payment and Billing Management

| ID | Feature | Status | Where |
|---|---|---|---|
| FE-1 | Secure online payments for consultations, appointments and home visits | | |
| FE-2 | Third-party payment gateway | | |
| FE-3 | Invoices, receipts and transaction history | | |
| FE-4 | Refunds, cancellations and payment status tracking | | |

## Module 9: Unified Dashboard and Admin Panel

Not in this pass (dashboards exist; see the brief).
