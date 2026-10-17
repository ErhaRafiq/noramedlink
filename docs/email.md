# Email in Nora MedLink

Sent through [Resend](https://resend.com) from `Nora MedLink <noreply@noramedlink.online>`. Everything works
without it: with no key set, no email is sent and the app behaves as before.

## What is sent

| Email | When | Who | Notes |
|---|---|---|---|
| Confirm your email | sign-up, and "resend" | the new account | a link that works 24 hours, once |
| Password reset code | "Forgot password" | the account | 6 digits, 10 minutes, 5 tries, once |
| Password changed | after a reset | the account | a security notice; the account is also signed out everywhere |
| Appointment confirmed / new appointment | a booking | patient and doctor | time in Pakistan time, type, the other person's name |
| Appointment moved | a reschedule | patient and doctor | shows the old time |
| Appointment cancelled | a cancel | patient and doctor | says who cancelled |
| Reminder | 5 minutes before the start | patient and doctor | each person can switch it off in `/profile` |

No email holds the reason for a visit, a diagnosis, a report or any other record content. The doctor's email names
the patient (their own patient) and the patient's names the doctor; nothing else about the visit.

## What stops needless emails (the free plan allows 100 a day)

- Only a **confirmed** address with an **active** account gets an appointment email. Accounts that existed before
  this feature keep their "confirmed" flag; new sign-ups must use the link.
- Every email has a unique key, so the same email is never queued twice, and Resend gets the key as an
  `Idempotency-Key` so a retry cannot send it twice.
- A reminder is **not queued** when the booking is less than 15 minutes ahead (the confirmation just went), is
  **dropped** if it could not be sent within 3 minutes of its time, and is **withdrawn** if the appointment moves
  or is cancelled. Reminders can be switched off per person.
- Forgot password, resend-confirmation and reset are rate limited (below). Nothing else a user can do sends email.
- Counting emails against the daily limit is left to you (Resend's dashboard shows usage); the app has no cap.

## Rate limits on emails a user can cause

| Endpoint | Limit |
|---|---|
| `POST /auth/forgot-password` | 5 a minute per IP, 5 an hour per address (counted for every address, so it reveals nothing), and one code per account at most every 60 seconds and 3 an hour (kept in the database, so it survives restarts) |
| `POST /auth/reset-password` | 10 a minute per IP, 15 an hour per address, 5 wrong tries per code |
| `POST /auth/resend-verification` | 5 a minute per IP, and one link per account every 60 seconds, 3 an hour |
| `POST /auth/verify-email` | 20 a minute per IP |

Forgot password gives the same answer whether or not the address has an account, and the email is sent after the
answer, so neither the wording nor the timing says who is registered.

## How reminders are scheduled (and why not a cron job)

The reminder time is known the moment an appointment is booked. So a row is written to `email_outbox` then, with
the time it is due (`send_after`) and the latest it is still useful (`expires_at`). A small loop inside the
server (`services/email_outbox.py`, started in `main.py`) looks every 20 seconds, and at once after a booking,
for rows that are due and sends them. Appointment emails are queued **in the same database transaction as the
booking**, so a booking that fails sends nothing; a request never waits on Resend; a failed send is retried
after 30 seconds, 2 minutes and 10 minutes (only for errors that may pass, like a rate limit).

A cron job would scan appointments on a timer and needs a paid always-on worker on Render. This needs neither,
but it does need the server **awake** at the reminder time. On Render's free plan the web service sleeps after
15 minutes without traffic, which would miss a reminder. Keep it awake with a free uptime monitor (UptimeRobot,
Better Stack or cron-job.org) that requests `https://<your-api>/health` every 5 minutes. If the server was asleep
and a reminder is more than 3 minutes late, it is dropped rather than sent after the visit started.

Code and verification emails are the exception: they are sent right after the request, in the background, and
only a log row (no content) is kept, so a database copy never holds a working code.

## Setting it up

1. In Resend, **Domains → Add Domain** `noramedlink.online`, and add the DNS records it shows at your domain
   registrar: the SPF (TXT) and DKIM (CNAME or TXT) records. Wait until the domain shows **Verified**. Add a
   DMARC record too, for example `_dmarc` TXT `v=DMARC1; p=none; rua=mailto:you@noramedlink.online`, then tighten
   it later. Until the domain is verified Resend only lets you send to your own address.
2. In Resend, **API Keys → Create API Key** with "Sending access" for that domain only.
3. Put it in your own `.env` (never in `.env.example`, never in git, never in a chat):

   ```
   RESEND_API_KEY=re_...
   EMAIL_FROM=Nora MedLink <noreply@noramedlink.online>
   EMAIL_REPLY_TO=              # optional, for example support@noramedlink.online
   ```

   On Render, set the same names as environment variables on `nora-api` (the key as a secret).
4. Set `FRONTEND_ORIGIN` to the public address of the site (the links in the emails and the logo use it).
5. Restart the API. Sign up with a real address to receive the confirmation email.

**If a key was ever pasted into a chat, an issue or a commit, treat it as exposed: delete it in Resend and make a
new one.**

## Tests never send email

`DISABLE_PAID_SERVICES=1` (backend and tests) blanks the key like every other outside service, and the acceptance
and e2e runs refuse to start if an email key is configured. Test accounts use `example.test` addresses that must
never receive mail. The sender is tested with fake providers (`backend/tests/test_email.py`, section 17d of
`tests/acceptance_test.py`).

## Files

`services/email_client.py` (Resend call), `services/email_templates.py` (the emails), `services/email_outbox.py`
(queue, worker, reminders), `services/auth_tokens.py` (codes and links), `services/account_email.py` (immediate
sends), `routers/account_email.py` (the endpoints), migration 0019.
