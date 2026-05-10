# Nora MedLink SDS Diagram Section

This section contains SDS-ready diagram content for Nora MedLink. The diagram sources use formal black, white, and grayscale styling to match a professional university software design specification.

PlantUML source files are stored in [docs/sds/diagrams/plantuml](./diagrams/plantuml). Mermaid source files are stored in [docs/sds/diagrams/mermaid](./diagrams/mermaid).

## Figure 3.1 — Nora MedLink Use Case Diagram

Purpose: This diagram shows the main actors that interact with Nora MedLink and the functional services available to each actor.

Contribution: It defines the system boundary and clarifies which patient, doctor, administrator, OCR, AI, and notification responsibilities must be supported by the design.

Diagram source: [use-case-diagram.puml](./diagrams/plantuml/use-case-diagram.puml)

| Diagram element | Explanation |
| --- | --- |
| Patient | Uses report upload, OCR review, appointments, payments, reminders, medicine history, and health insight features. |
| Doctor | Uses authenticated dashboard functions and reviews patient data only when access is granted. |
| Administrator | Manages administrative records such as emergency and payment status information. |
| External services | OCR.Space extracts text, OpenAI supports clinical summaries, and the notification channel delivers reminder alerts. |
| Included and extended use cases | OCR upload includes AI summary generation, while payment and dashboard access extend appointment booking where applicable. |

## Figure 3.2 — Nora MedLink Class Diagram (i): User and Authentication Classes

Purpose: This diagram shows the authentication, role, profile, OTP, and temporary dashboard access classes.

Contribution: It explains how identity, authorization, and consent-based doctor access are structured before clinical data can be accessed.

Diagram source: [class-diagram-i-user-authentication.puml](./diagrams/plantuml/class-diagram-i-user-authentication.puml)

| Diagram element | Explanation |
| --- | --- |
| User | Central account entity with private identity attributes and public role/session methods. |
| PatientProfile and DoctorProfile | Profile objects are composed under User, showing one optional patient or doctor profile per account. |
| AuthService, PasswordService, TokenService | Service classes separate signup, login, password hashing, and token generation responsibilities. |
| PatientDashboardOtp | Represents a patient-created access code that can be consumed once before expiry. |
| PatientDashboardAccess | Represents doctor access granted by a patient, including active, expired, or ended access states. |

## Figure 3.3 — Nora MedLink Class Diagram (ii): Medical Report and AI/OCR Classes

Purpose: This diagram shows how report uploads, OCR processing, department classification, AI validation, and clinical summary generation are organized.

Contribution: It identifies the report-processing classes and the service dependencies needed to convert a file upload into structured medical information.

Diagram source: [class-diagram-ii-medical-report-ai-ocr.puml](./diagrams/plantuml/class-diagram-ii-medical-report-ai-ocr.puml)

| Diagram element | Explanation |
| --- | --- |
| PatientReport | Stores uploaded report metadata, OCR text, structured data, summary, validation status, and OCR status. |
| MedicalDepartment | Aggregates reports by department such as Heart, Kidney, Lab, Medicine, Ortho, and General. |
| MedicalAiAnalysis | Stores entity extraction, confidence, warnings, validation results, and doctor-facing summary data. |
| OCR services | FileStorageService and OcrSpaceService handle secure storage and OCR extraction. |
| AI pipeline services | BioBERT, rule validation, and OpenAI summary services produce clinical-support outputs. |

## Figure 3.4 — Nora MedLink Class Diagram (iii): Appointment, Payment and Notification Classes

Purpose: This diagram shows appointment booking, payment handling, emergency booking, medicine history, reminder, and notification classes.

Contribution: It links operational healthcare workflows to their database-backed classes and service responsibilities.

Diagram source: [class-diagram-iii-appointment-payment-notification.puml](./diagrams/plantuml/class-diagram-iii-appointment-payment-notification.puml)

| Diagram element | Explanation |
| --- | --- |
| Appointment | Connects a patient to an assigned or demo doctor and tracks booking and payment status. |
| Payment | Stores payment method, reference, invoice, transaction, and status data for appointment-related or general payments. |
| Reminder and Notification | Reminder composition creates one or more notification records for scheduled alerts. |
| MedicineHistory | Stores patient medicine, dosage, frequency, reason, and side-effect history. |
| Service classes | AppointmentService, PaymentService, and ReminderService represent business operations around the entities. |

## Figure 3.5 — Nora MedLink Sequence Diagram: OCR Report Upload

Purpose: This diagram shows the runtime message flow when a patient uploads a medical report for OCR processing.

Contribution: It validates the design order for authentication, file storage, OCR extraction, AI analysis, persistence, and user feedback.

Diagram source: [sequence-ocr-report-upload.puml](./diagrams/plantuml/sequence-ocr-report-upload.puml)

| Diagram element | Explanation |
| --- | --- |
| Patient dashboard | Collects file, title, and department input and submits multipart form data. |
| FastAPI Report API | Coordinates authentication, file storage, OCR, AI analysis, and persistence. |
| OCR.Space | Extracts text from the uploaded report image or document. |
| Report AI Pipeline | Produces structured clinical-support analysis after OCR succeeds. |
| Failure branch | Preserves the uploaded report with failed OCR status so the patient can still review the issue. |

## Figure 3.6 — Nora MedLink Sequence Diagram: AI Summary Generation

Purpose: This diagram shows how Nora MedLink generates a clinical-support summary from OCR or corrected report text.

Contribution: It separates entity extraction, rule validation, OpenAI summarization, fallback logic, self-checking, and database persistence.

Diagram source: [sequence-ai-summary-generation.puml](./diagrams/plantuml/sequence-ai-summary-generation.puml)

| Diagram element | Explanation |
| --- | --- |
| Report API | Starts summary generation after upload or OCR text correction. |
| BioBERT Entity Service | Extracts medical entities from report text and structured fields. |
| Rule Validation Service | Checks extracted data and text against safety and validation rules. |
| OpenAI Summary Service | Generates JSON-based clinical-support summaries when available. |
| Self-check and fallback | Verifies generated summaries and uses rule-based fallback when OpenAI is unavailable. |

## Figure 3.7 — Nora MedLink Sequence Diagram: Appointment Booking

Purpose: This diagram shows the interaction flow for searching doctors and booking an appointment.

Contribution: It clarifies appointment creation, doctor resolution, future-date validation, and optional patient dashboard access by OTP.

Diagram source: [sequence-appointment-booking.puml](./diagrams/plantuml/sequence-appointment-booking.puml)

| Diagram element | Explanation |
| --- | --- |
| Doctor directory query | Combines registered doctors and demo doctors for patient selection. |
| Appointment API | Authenticates the patient and creates the appointment record. |
| Dashboard access service | Uses OTP only when the patient supplies it and the doctor is registered. |
| Appointment status | New appointments are stored as BOOKED with payment status PENDING. |
| Confirmation response | Returns booking status and whether dashboard access was granted. |

## Figure 3.8 — Nora MedLink Sequence Diagram: Medicine Reminder

Purpose: This diagram shows how a patient schedules a medicine reminder and how notification records are created.

Contribution: It explains the reminder data flow from patient input through token storage, reminder persistence, scheduled notification creation, and eventual alert delivery.

Diagram source: [sequence-medicine-reminder.puml](./diagrams/plantuml/sequence-medicine-reminder.puml)

| Diagram element | Explanation |
| --- | --- |
| Reminder view | Captures reminder title, due time, and optional browser push token. |
| Reminder API | Authenticates the user and creates reminder records. |
| NotificationToken | Stores or updates the browser/device token for future alerts. |
| Notification record | Represents the scheduled message connected to the reminder. |
| Notification channel | Delivers the alert when the scheduled reminder becomes due. |

## Figure 3.9 — Nora MedLink Sequence Diagram: Payment

Purpose: This diagram shows the payment creation process for wallet, cash, card, or Raast methods.

Contribution: It explains payment validation, appointment ownership checks, reference generation, invoice generation, status assignment, and appointment payment status updates.

Diagram source: [sequence-payment.puml](./diagrams/plantuml/sequence-payment.puml)

| Diagram element | Explanation |
| --- | --- |
| Payment page | Collects method, amount, purpose, phone, and appointment selection. |
| Payment API | Authenticates the user and validates payment rules. |
| Payment service | Generates Nora MedLink references and invoice numbers. |
| Payment status branches | Wallet methods become SUCCESS, cash becomes PAY_ON_VISIT, and card or Raast remains PENDING. |
| Appointment update | Successful appointment payment updates the linked appointment payment status. |

## Figure 3.10 — Nora MedLink Activity Diagram: Report Upload and OCR

Purpose: This diagram shows the step-by-step workflow for report upload, validation, OCR, AI processing, and result review.

Contribution: It helps designers and testers verify all success and failure paths in the report processing workflow.

Diagram source: [activity-report-upload-ocr.puml](./diagrams/plantuml/activity-report-upload-ocr.puml)

| Diagram element | Explanation |
| --- | --- |
| Upload validation | Confirms file type and size before processing. |
| File storage | Saves the uploaded report under a patient-specific path. |
| OCR processing | Extracts, cleans, classifies, and structures report text. |
| AI processing | Generates entities, warnings, validation results, and summaries. |
| Failure handling | Saves failed OCR results so the report state remains visible to the patient. |

## Figure 3.11 — Nora MedLink Activity Diagram: Appointment Booking

Purpose: This diagram shows the workflow from doctor search to appointment confirmation.

Contribution: It supports design validation for doctor filtering, date validation, booking creation, optional OTP access, and confirmation output.

Diagram source: [activity-appointment-booking.puml](./diagrams/plantuml/activity-appointment-booking.puml)

| Diagram element | Explanation |
| --- | --- |
| Doctor selection | Patient filters doctors and selects a preferred appointment option. |
| Date validation | Prevents booking appointments in the past. |
| Appointment creation | Stores the appointment with BOOKED status and PENDING payment status. |
| OTP branch | Grants temporary dashboard access only when a valid OTP is supplied. |
| Confirmation | Returns booking results to the patient. |

## Figure 3.12 — Nora MedLink Activity Diagram: Medicine Reminder

Purpose: This diagram shows how reminder data is validated, saved, connected to a notification, and delivered later.

Contribution: It identifies the reminder lifecycle activities needed for scheduling and patient alerting.

Diagram source: [activity-medicine-reminder.puml](./diagrams/plantuml/activity-medicine-reminder.puml)

| Diagram element | Explanation |
| --- | --- |
| Token step | Stores an optional push token when available. |
| Reminder validation | Confirms title and due time before persistence. |
| Reminder creation | Saves the reminder as UPCOMING. |
| Notification creation | Creates a SCHEDULED notification linked to the reminder. |
| Due-time action | Sends an alert when the scheduled time is reached. |

## Figure 3.13 — Nora MedLink State Transition Diagram: Appointment

Purpose: This diagram shows the major state changes of an appointment from draft booking to completion, cancellation, or deletion.

Contribution: It defines valid appointment transitions and shows how payment status operates inside the booked appointment state.

Diagram source: [state-appointment.puml](./diagrams/plantuml/state-appointment.puml)

| Diagram element | Explanation |
| --- | --- |
| Draft | Represents appointment data before patient confirmation. |
| BOOKED | Active appointment state after successful creation. |
| RESCHEDULED | Intermediate state when appointment time changes. |
| Payment substate | Tracks pending, successful, pay-on-visit, and failed payment states. |
| Final states | COMPLETED, CANCELLED, and DELETED end the appointment lifecycle. |

## Figure 3.14 — Nora MedLink State Transition Diagram: Medical Report

Purpose: This diagram shows report status changes from upload acceptance through OCR, review, regeneration, or deletion.

Contribution: It clarifies report lifecycle control and helps prevent undefined report-processing states.

Diagram source: [state-medical-report.puml](./diagrams/plantuml/state-medical-report.puml)

| Diagram element | Explanation |
| --- | --- |
| PENDING | Initial state after report upload is accepted. |
| OCR_PROCESSING | File has been stored and sent for OCR processing. |
| COMPLETED | OCR and AI analysis completed successfully. |
| NEEDS_REVIEW and REVIEWED | Patient can correct OCR text and regenerate summary results. |
| FAILED and DELETED | Failed OCR can be retried or removed from the patient record. |

## Figure 3.15 — Nora MedLink State Transition Diagram: Medicine Reminder

Purpose: This diagram shows the lifecycle of a scheduled medicine reminder.

Contribution: It defines how reminders progress through scheduled, due, sent, completed, skipped, rescheduled, or cancelled states.

Diagram source: [state-medicine-reminder.puml](./diagrams/plantuml/state-medicine-reminder.puml)

| Diagram element | Explanation |
| --- | --- |
| UPCOMING | Reminder is scheduled for a future date and time. |
| RESCHEDULED | Due time has been modified and saved. |
| DUE | Scheduled reminder time has arrived. |
| SENT | Notification has been dispatched to the patient. |
| COMPLETED, SKIPPED, CANCELLED | End or loop states based on patient action and schedule changes. |

## Figure 3.16 — Nora MedLink State Transition Diagram: Payment

Purpose: This diagram shows payment states across wallet, cash, card, Raast, retry, refund, and cancellation paths.

Contribution: It ensures payment behavior remains consistent with appointment payment status and invoice handling.

Diagram source: [state-payment.puml](./diagrams/plantuml/state-payment.puml)

| Diagram element | Explanation |
| --- | --- |
| Initiated | Payment request has been submitted but not yet classified. |
| PENDING | Card or Raast payment is awaiting confirmation. |
| SUCCESS | Payment is accepted or cash is later received at visit. |
| PAY_ON_VISIT | Cash payment is deferred until the appointment visit. |
| FAILED, REFUNDED, CANCELLED | Exception and terminal states for unsuccessful or reversed payments. |

## Figure 3.17 — Nora MedLink ERD Diagram

Purpose: This diagram shows the relational data model for Nora MedLink, including users, profiles, reports, AI analyses, appointments, payments, reminders, notifications, and patient health records.

Contribution: It supports database design by showing primary entities, foreign-key relationships, cardinality, and major stored attributes.

Diagram source: [erd-diagram.mmd](./diagrams/mermaid/erd-diagram.mmd)

| Diagram element | Explanation |
| --- | --- |
| USERS | Central parent table for patients, doctors, administrators, and system-owned records. |
| Patient and doctor profiles | One-to-one profile tables extend user identity based on role. |
| Patient reports and AI analyses | Reports belong to patients and can generate multiple analysis records. |
| Appointments and payments | Appointments connect patients to doctors and can be linked to one or more payment records. |
| Reminders and notifications | Reminders belong to users and create scheduled notification records. |

## Figure 3.18 — Nora MedLink Layered Architecture Diagram

Purpose: This diagram shows the layered software architecture from frontend pages through API routes, backend routers, domain services, database storage, and external integrations.

Contribution: It explains separation of concerns and the flow of dependency from presentation logic to domain services and infrastructure.

Diagram source: [layered-architecture-diagram.mmd](./diagrams/mermaid/layered-architecture-diagram.mmd)

| Diagram element | Explanation |
| --- | --- |
| Presentation layer | Contains patient, doctor, admin, appointment, payment, and reminder views. |
| Application gateway layer | Routes frontend requests through Next.js pages and API/proxy handlers. |
| Backend API layer | FastAPI routers expose authentication, patient, report, appointment, payment, reminder, and doctor endpoints. |
| Domain service layer | Encapsulates authentication, storage, OCR, AI analysis, validation, and notification scheduling logic. |
| Data and integration layer | Stores persistent data and integrates with OCR.Space, OpenAI, uploaded file storage, and notification channels. |

## Figure 3.19 — Nora MedLink DFD Level 0

Purpose: This diagram shows Nora MedLink as a single system process interacting with external actors, data storage, and third-party services.

Contribution: It provides the high-level data context required before decomposing the system into internal processes.

Diagram source: [dfd-level-0.puml](./diagrams/plantuml/dfd-level-0.puml)

| Diagram element | Explanation |
| --- | --- |
| Nora MedLink System | Main process that receives and returns healthcare workflow data. |
| Patient, doctor, administrator | External entities that provide and consume system data. |
| Nora MedLink Database | Persistent storage for user, report, appointment, payment, reminder, and clinical-support data. |
| OCR.Space and OpenAI | External processing services for text extraction and summary generation. |
| Notification channel | External delivery path for scheduled medicine reminder alerts. |

## Figure 3.20 — Nora MedLink DFD Level 1

Purpose: This diagram decomposes Nora MedLink into major internal data-processing modules and their data stores.

Contribution: It helps system designers understand how authentication, report processing, appointment booking, payment, reminders, doctor access, and administration exchange data.

Diagram source: [dfd-level-1.puml](./diagrams/plantuml/dfd-level-1.puml)

| Diagram element | Explanation |
| --- | --- |
| Authentication and profile management | Handles signup, login, role validation, credentials, and profile records. |
| Report upload, OCR and AI analysis | Processes uploaded files, OCR text, summaries, validations, and medical analysis records. |
| Appointment, payment and reminder processes | Manage booking data, payment status, invoices, reminders, tokens, and scheduled notifications. |
| Doctor access and dashboard | Uses patient consent or OTP access to provide doctors with authorized patient context. |
| Data stores | Separate logical stores represent users, medical records, appointments/access, payments, reminders, and emergency bookings. |
