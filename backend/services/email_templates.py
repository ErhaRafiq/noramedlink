"""The emails, in the look of Nora MedLink: calm clinical blue and teal, one clear action, plain wording.

Built the way email clients need: table layout with inline styles (Outlook ignores most CSS), a 600px card that
shrinks on a phone, a hidden preheader line, a "bulletproof" button, a dark-mode block for the clients that
support it, a plain-text twin of every email, and the logo as a hosted image with alt text (the brand name is
also written, so nothing is lost when images are off). Every value that comes from a person or from the record
goes through html.escape. No email carries the reason for a visit, a diagnosis or any record content.

`render(kind, context)` returns the subject, the HTML and the text. Contexts hold only names, times and links.
"""

from dataclasses import dataclass
from html import escape

from config import settings

BLUE, TEAL, NAVY = "#2563EB", "#00BFA6", "#06182F"
INK, MUTED, LINE, SOFT, PAGE = "#0B1220", "#64748B", "#DCE8F5", "#F8FBFF", "#F4FAFF"
FONT = "Poppins, 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif"

MODE_LABEL = {"online": "Online consultation", "in_clinic": "In clinic", "home": "Home visit"}
SAFETY = "Nora MedLink is an academic prototype and not an emergency service. In an emergency call 1122."


@dataclass(frozen=True)
class Rendered:
    subject: str
    html: str
    text: str


def app_url(path: str = "") -> str:
    return settings.frontend_origin.rstrip("/") + path


def _dr(name: str) -> str:
    name = (name or "").strip()
    return name if name.lower().startswith(("dr ", "dr.")) else f"Dr. {name}"


# --- the shared frame ----------------------------------------------------------------------------------


def _rows(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<tr><td style="padding:10px 16px;border-top:1px solid {LINE};font:13px/1.4 {FONT};color:{MUTED};width:38%;" class="muted bd">{escape(label)}</td>'
        f'<td style="padding:10px 16px;border-top:1px solid {LINE};font:14px/1.4 {FONT};color:{INK};font-weight:600;" class="txt bd">{escape(value)}</td></tr>'
        for label, value in rows
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="soft bd" '
        f'style="background:{SOFT};border:1px solid {LINE};border-radius:12px;border-collapse:separate;margin:20px 0 4px;">{cells}</table>'
    )


def _button(label: str, url: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 8px;"><tr>'
        f'<td align="center" bgcolor="{BLUE}" style="border-radius:12px;background:{BLUE};background-image:linear-gradient(90deg,{BLUE},{TEAL});">'
        f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener" '
        f'style="display:inline-block;padding:14px 28px;font:600 15px/1 {FONT};color:#FFFFFF;text-decoration:none;border-radius:12px;">{escape(label)}</a>'
        f"</td></tr></table>"
    )


def _code_box(code: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="soft bd" '
        f'style="background:{SOFT};border:1px solid {LINE};border-radius:12px;margin:20px 0 8px;"><tr>'
        f"<td align=\"center\" style=\"padding:18px 12px;font:700 34px/1 'SFMono-Regular', Consolas, 'Courier New', monospace;"
        f'letter-spacing:10px;color:{NAVY};" class="txt">{escape(code)}</td></tr></table>'
    )


def _p(text: str, *, muted: bool = False) -> str:
    color, cls = (MUTED, "muted") if muted else (INK, "txt")
    size = "13px" if muted else "15px"
    return f'<p class="{cls}" style="margin:0 0 14px;font:{size}/1.6 {FONT};color:{color};">{text}</p>'


def _layout(*, title: str, preheader: str, body: str, footer_note: str) -> str:
    logo = app_url("/icons/icon-192.png")
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<title>{escape(title)}</title>
<style>
@media only screen and (max-width:620px) {{ .container {{ width:100% !important; }} .px {{ padding-left:20px !important; padding-right:20px !important; }} }}
@media (prefers-color-scheme: dark) {{
  .page {{ background:#0B1220 !important; }} .card {{ background:#111C30 !important; border-color:#243349 !important; }}
  .soft {{ background:#16243B !important; border-color:#243349 !important; }} .bd {{ border-color:#243349 !important; }}
  .txt {{ color:#E6EEF8 !important; }} .muted {{ color:#9FB0C5 !important; }}
}}
</style></head>
<body class="page" style="margin:0;padding:0;background:{PAGE};-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">{escape(preheader)}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="page" bgcolor="{PAGE}" style="background:{PAGE};"><tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" class="container" style="width:600px;max-width:600px;">
<tr><td style="padding:0 4px 16px;">
  <table role="presentation" cellpadding="0" cellspacing="0"><tr>
    <td style="padding-right:10px;"><img src="{escape(logo, quote=True)}" width="36" height="36" alt="" style="display:block;border:0;border-radius:10px;"></td>
    <td style="font:700 18px/1 {FONT};color:{NAVY};" class="txt">Nora MedLink</td>
  </tr></table>
</td></tr>
<tr><td class="card" style="background:#FFFFFF;border:1px solid {LINE};border-radius:16px;overflow:hidden;">
  <div style="height:4px;line-height:4px;font-size:0;background:{BLUE};background-image:linear-gradient(90deg,{BLUE},{TEAL});">&nbsp;</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td class="px" style="padding:28px 32px 26px;">
{body}
  </td></tr></table>
</td></tr>
<tr><td class="px" style="padding:18px 8px 0;">
  <p class="muted" style="margin:0 0 6px;font:12px/1.6 {FONT};color:{MUTED};">{escape(footer_note)}</p>
  <p class="muted" style="margin:0;font:12px/1.6 {FONT};color:{MUTED};">{escape(SAFETY)}</p>
</td></tr>
</table></td></tr></table></body></html>"""


def _h1(text: str) -> str:
    return f'<h1 class="txt" style="margin:0 0 14px;font:700 22px/1.3 {FONT};color:{INK};">{escape(text)}</h1>'


def _text(title: str, lines: list[str], footer: str) -> str:
    return "\n\n".join([f"Nora MedLink\n\n{title}", *lines, footer, SAFETY]) + "\n"


# --- the emails ----------------------------------------------------------------------------------------


def _verify_email(c: dict) -> Rendered:
    name, link, hours = c["name"], c["link"], c.get("hours", 24)
    body = (
        _h1("Confirm your email address")
        + _p(
            f"Hi {escape(name)}, welcome to Nora MedLink. Please confirm that this is your email address so we can send you appointment confirmations and reminders."
        )
        + _button("Confirm my email", link)
        + _p(
            f"This link works for {hours} hours and only once. If the button does not open, copy this address into your browser:",
            muted=True,
        )
        + _p(escape(link), muted=True)
        + _p("If you did not create an account, you can ignore this email.", muted=True)
    )
    return Rendered(
        "Confirm your email for Nora MedLink",
        _layout(
            title="Confirm your email",
            preheader="One tap to confirm your email address.",
            body=body,
            footer_note="You received this because someone signed up to Nora MedLink with this address.",
        ),
        _text(
            "Confirm your email address",
            [
                f"Hi {name}, welcome to Nora MedLink. Please confirm your email address:",
                link,
                f"The link works for {hours} hours and only once.",
                "If you did not create an account, ignore this email.",
            ],
            "You received this because someone signed up to Nora MedLink with this address.",
        ),
    )


def _reset_code(c: dict) -> Rendered:
    name, code, minutes = c["name"], c["code"], c.get("minutes", 10)
    body = (
        _h1("Your password reset code")
        + _p(f"Hi {escape(name)}, enter this code on the reset page to choose a new password:")
        + _code_box(code)
        + _p(
            f"The code works for {minutes} minutes and allows 5 tries. Nora MedLink staff will never ask you for it.",
            muted=True,
        )
        + _p(
            "If you did not ask to reset your password, you can ignore this email: your password has not changed.",
            muted=True,
        )
    )
    return Rendered(
        "Your Nora MedLink password reset code",
        _layout(
            title="Password reset code",
            preheader=f"Your code works for {minutes} minutes.",
            body=body,
            footer_note="You received this because a password reset was requested for this address.",
        ),
        _text(
            "Your password reset code",
            [
                f"Hi {name}, enter this code on the reset page:",
                code,
                f"It works for {minutes} minutes and allows 5 tries. Nora MedLink staff never ask for it.",
                "If you did not ask to reset your password, ignore this email: nothing has changed.",
            ],
            "You received this because a password reset was requested for this address.",
        ),
    )


def _password_changed(c: dict) -> Rendered:
    name = c["name"]
    url = app_url("/forgot-password")
    body = (
        _h1("Your password was changed")
        + _p(
            f"Hi {escape(name)}, the password for your Nora MedLink account was just changed, and you were signed out everywhere."
        )
        + _p("If this was you, there is nothing more to do. If it was not, reset your password now:")
        + _button("Reset my password", url)
    )
    return Rendered(
        "Your Nora MedLink password was changed",
        _layout(
            title="Password changed",
            preheader="If this was not you, reset it now.",
            body=body,
            footer_note="This is a security notice about your Nora MedLink account.",
        ),
        _text(
            "Your password was changed",
            [
                f"Hi {name}, your password was just changed and you were signed out everywhere.",
                f"If this was not you, reset it now: {url}",
            ],
            "This is a security notice about your Nora MedLink account.",
        ),
    )


def _appointment_rows(c: dict) -> list[tuple[str, str]]:
    patient = c["audience"] == "patient"
    rows = [("When", c["when_text"] + " (Pakistan time)")]
    if c.get("old_when_text"):
        rows.insert(0, ("Was", c["old_when_text"]))
    rows.append(("Doctor" if patient else "Patient", _dr(c["doctor_name"]) if patient else c["patient_name"]))
    rows.append(("Type", MODE_LABEL.get(c.get("mode", ""), "Appointment")))
    return rows


def _appointment(kind: str, c: dict) -> Rendered:
    patient = c["audience"] == "patient"
    other = _dr(c["doctor_name"]) if patient else c["patient_name"]
    when = c["when_text"]
    path = "/dashboard/patient#appointments" if patient else "/dashboard/doctor#appointments"
    url = app_url(path)
    greeting = f"Hi {escape(c['recipient_name'])},"
    if kind == "appointment_booked":
        subject = f"Appointment confirmed: {when}" if patient else f"New appointment: {c['patient_name']}, {when}"
        title = "Your appointment is confirmed" if patient else "A new appointment was booked"
        intro = (
            "Your appointment is booked." if patient else f"{escape(c['patient_name'])} booked an appointment with you."
        )
        pre = f"{when} with {other}"
    elif kind == "appointment_moved":
        subject = f"Appointment moved to {when}"
        title = "An appointment was moved"
        intro = (
            "Your appointment was moved to a new time."
            if patient
            else f"{escape(c['patient_name'])} moved their appointment with you."
        )
        pre = f"Now {when}"
    elif kind == "appointment_cancelled":
        who = c.get("cancelled_by", "")
        subject = f"Appointment cancelled: {when}"
        title = "An appointment was cancelled"
        if patient:
            intro = (
                f"{escape(_dr(c['doctor_name']))} cancelled your appointment."
                if who == "doctor"
                else "You cancelled your appointment."
            )
        else:
            intro = (
                f"{escape(c['patient_name'])} cancelled their appointment."
                if who == "patient"
                else "You cancelled this appointment."
            )
        pre = f"Was {when}"
    else:  # appointment_reminder
        minutes = c.get("minutes", 5)
        subject = (
            f"Your appointment starts in {minutes} minutes"
            if patient
            else f"Appointment with {c['patient_name']} starts in {minutes} minutes"
        )
        title = f"Starting in {minutes} minutes"
        intro = f"Your appointment with {escape(other)} is about to start."
        pre = f"{when} with {other}"
    paid = ""
    if kind == "appointment_booked" and patient and c.get("pay_note"):
        paid = _p(escape(c["pay_note"]), muted=True)
    reminder_note = (
        "You can turn reminder emails off in your profile."
        if kind == "appointment_reminder"
        else "You can manage reminder emails in your profile."
    )
    body = (
        _h1(title)
        + _p(f"{greeting} {intro}")
        + _rows(_appointment_rows(c))
        + paid
        + _button("Open Nora MedLink", url)
        + _p(reminder_note, muted=True)
    )
    text = _text(
        title,
        [
            f"{c['recipient_name']},",
            *(f"{label}: {value}" for label, value in _appointment_rows(c)),
            f"Open Nora MedLink: {url}",
        ],
        reminder_note,
    )
    return Rendered(
        subject,
        _layout(
            title=title,
            preheader=pre,
            body=body,
            footer_note="You received this because of an appointment on your Nora MedLink account.",
        ),
        text,
    )


KINDS = {
    "verify_email": _verify_email,
    "reset_code": _reset_code,
    "password_changed": _password_changed,
}
APPOINTMENT_KINDS = ("appointment_booked", "appointment_moved", "appointment_cancelled", "appointment_reminder")


def render(kind: str, context: dict) -> Rendered:
    if kind in KINDS:
        return KINDS[kind](context)
    if kind in APPOINTMENT_KINDS:
        return _appointment(kind, context)
    raise ValueError(f"Unknown email kind: {kind}")
