# Proposal: Module 6, the home-visit engine

Status: **waiting for approval**. Nothing in this document has been built. AGENTS.md section 9 requires
a column-by-column mapping and approval before a migration that moves data is written; this proposal
avoids moving data, and still asks for a yes on the points in section 7.

## 1. What exists today

- `emergency_bookings` (model `EmergencyBooking`): `user_id`, `doctor_id` (always empty), `patient_name`,
  `phone`, `address`, `symptoms`, `doctor_name` (always "Not assigned"), `status` (always `REQUESTED`),
  `estimated_minutes` (always 0, shown as no ETA), `latitude`, `longitude`.
- `POST /emergency/requests` (patient only) records a row and answers "no doctor has been assigned".
  Nothing assigns a doctor, nothing changes the status, the doctor dashboard's emergency list stays empty.
- `/emergency` page: a request form, the 1122 notice, and an honest "what happens next" list.
- **Data to keep:** the development database has 0 rows. Other databases (the Render one) may have some.
- Doctors have no location, radius or home-visit switch. `doctor_profiles.consultation_modes` already
  lists `home` as a type a doctor can offer, and appointments already accept the mode `home`.

## 2. Recommended design (patient picks a nearby doctor)

1. The patient describes the reason, gives a phone number, an address and a location.
2. **The red-flag detector runs first** (`services/symptom_checker.red_flags`). A warning sign blocks the
   request and shows the 1122 notice. No doctor list, no booking, nothing saved as a request.
3. Otherwise the patient sees **verified, active doctors who offer home visits and cover their location**,
   ranked by distance, then rating, then fee, optionally narrowed to a specialty.
4. The patient sends the request to one doctor. The doctor sees the reason and the distance (to the
   nearest 0.5 km), **not the phone number or address**, and accepts or declines.
5. On accept, the doctor sees the phone and address; the visit moves through the states below.
6. The patient can cancel until the doctor arrives. A request nobody answers expires.

This matches the brief's states (including `declined`) with no race between doctors. The alternative
(broadcast to every nearby doctor, first to accept wins) needs an atomic claim and a way to withdraw the
request from the others; see question 1.

### States and who may move them

| From | To | Who |
|---|---|---|
| requested | accepted, declined | the chosen doctor |
| requested | cancelled | the patient |
| requested | expired | the system, 30 minutes after sending, applied when the request is read |
| accepted | en_route, cancelled | the doctor / the patient or the doctor |
| en_route | arrived, cancelled | the doctor / the patient or the doctor |
| arrived | completed | the doctor |

Anything else is refused with 409, enforced in one function (`services/home_visits.py`) and unit tested
for every pair. Final states: completed, cancelled, declined, expired.

### What is never shown (AGENTS.md sections 6 and 7)

No ETA unless the doctor types one when marking en route, labelled "estimated by your doctor". No map
pin that moves. No doctor name before a doctor accepts. The 1122 notice is on every screen of the flow.

## 3. Schema (migration 0020, additive and idempotent; 0018 is the PMDC verification and 0019 the email tables)

**New table `home_visit_requests`**

| Column | Type | Notes |
|---|---|---|
| id | integer, primary key | |
| patient_id | FK users, CASCADE | was `emergency_bookings.user_id` |
| doctor_id | FK users, SET NULL, not null at creation | the chosen doctor (the old column was never set) |
| reason | text | was `symptoms` |
| phone, address | string / text | was `phone`, `address`; shown to the doctor only after accept |
| patient_name | string | was `patient_name` |
| latitude, longitude | float, not null | was nullable; a request needs a location to be matched |
| requested_specialty | string, nullable | a name from `specialties.csv`, when narrowed |
| status | string, indexed | the states above, lower case |
| eta_minutes | integer, nullable | typed by the doctor at `en_route`; never computed |
| decline_reason / cancel_reason | string, nullable | short, optional |
| created_at, updated_at | timestamptz | |
| accepted_at, en_route_at, arrived_at, completed_at, closed_at | timestamptz, nullable | one per step |
| expires_at | timestamptz | created_at + 30 minutes |

Constraints: a doctor can have **one open visit** (accepted, en_route or arrived) at a time (partial
unique index), and a patient one open request (requested to arrived) at a time.

**New columns on `doctor_profiles`**: `home_visits_enabled` (boolean, default false),
`service_radius_km` (integer, nullable, 1 to 50), `base_latitude`, `base_longitude` (float, nullable).
A doctor appears for matching only when enabled, verified, active, `home` is in `consultation_modes`,
and the radius and base location are set.

## 4. Mapping from `emergency_bookings` (nothing is moved or dropped)

| Old column | New column | Handling |
|---|---|---|
| id | none | the old table stays as it is |
| user_id | patient_id | not copied |
| doctor_id, doctor_name | doctor_id | not copied (every old row has no doctor) |
| patient_name, phone, address | same names | not copied |
| symptoms | reason | not copied |
| status (always REQUESTED; SEARCHING and DOCTOR_ASSIGNED belonged to the invented dispatch) | status | not copied |
| estimated_minutes | none | dropped by design: it was always a placeholder |
| latitude, longitude | latitude, longitude | not copied |

**Recommended:** copy nothing. `emergency_bookings` stays in the database and becomes read-only in the
ORM (the same treatment as `medical_documents`). Any old row is shown to its patient on the home-visit
page under "Earlier requests", worded "Recorded before the home-visit service; no doctor was assigned".
No row is deleted or rewritten. Option B (copy old rows in as `requested` and let them expire) is
possible but would turn a stale, unanswered request into a live-looking one; I advise against it.

## 5. Code, tests and UI

- **Backend:** `services/home_visits.py` (transitions, Haversine, matching, expiry), `routers/home_visits.py`
  (`GET /home-visits/doctors`, `POST /home-visits`, `GET /home-visits` for the caller, state changes),
  doctor settings on `PUT /doctor/profile`. The old `POST /emergency/requests` is replaced. In-app
  notifications for each change (existing `notifications` service). Audit log rows for send, accept, each
  state change, and a doctor opening the patient's phone and address.
- **Frontend:** `/emergency` becomes the home-visit page (same URL, so existing links keep working):
  request form with the red-flag notice, nearby doctors, the patient's requests with a plain status
  timeline. Doctor dashboard: a "Home visits" card replaces "Emergency visits". Profile: home-visit switch,
  radius, base location (browser location or typed coordinates; no geocoding service and no new external API).
- **Tests:** unit tests for Haversine, every pair in the state table, expiry and the one-open-visit rules;
  acceptance tests for 401/403, ownership, verified-and-opted-in doctors only, phone and address hidden
  until accept, red flag blocks, double accept; Playwright for the patient and doctor flows at desktop and 390px.
- **Not in the first cut:** paying for a home visit (see question 5).

## 6. Risks I want you to know about

- A home visit is the riskiest feature in the project. The wording stays "request", never "dispatch". Nothing
  promises a doctor will come; a request nobody answers expires and says so.
- Location is personal data: stored only on the request, shown to the doctor only after accept.
- Distance is straight-line (Haversine), not road distance, and says so on screen.
- The base location of a doctor is what they enter; it is not verified.

## 7. Decisions needed

1. **Matching model:** patient picks a nearby doctor (recommended), or broadcast to every nearby doctor?
2. **Old rows:** leave `emergency_bookings` untouched and read-only, with no copy (recommended), or copy them?
3. **A sixth final state `expired`** (the brief lists only cancelled and declined). Needed so an unanswered
   request does not stay open forever. OK to add?
4. **Doctor-typed ETA** at en route (optional, labelled as the doctor's estimate): allowed, or no ETA at all?
5. **Payment for home visits:** in this phase (adds a nullable `home_visit_id` on `payments`, Checkout after
   completion at the doctor's fee, refund on cancel before arrival), or a later phase (recommended: ship the
   state machine first)?
6. **Location input:** browser location or typed coordinates only (recommended), or may I add a geocoding
   service (an external API, which AGENTS.md section 14 says needs your approval)?
