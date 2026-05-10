import logging
import os
import smtplib
from email.message import EmailMessage


logger = logging.getLogger("nora.otp")


class OtpDeliveryError(Exception):
    pass


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def send_email_otp(email: str, otp: str) -> None:
    if _bool_env("OTP_DEV_MODE", False):
        logger.warning("Development signup OTP for %s: %s", email, otp)
        return

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM_EMAIL", "").strip()
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "Nora MedLink").strip()
    use_tls = _bool_env("SMTP_USE_TLS", True)
    allow_console = _bool_env("SIGNUP_OTP_ALLOW_CONSOLE_FALLBACK", True)

    if not smtp_host or not smtp_from:
        if allow_console:
            logger.warning("Development signup OTP for %s: %s", email, otp)
            return
        raise OtpDeliveryError("Email OTP provider is not configured.")

    message = EmailMessage()
    message["Subject"] = "Your Nora MedLink signup OTP"
    message["From"] = f"{smtp_from_name} <{smtp_from}>"
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                "Your Nora MedLink signup verification code is:",
                "",
                otp,
                "",
                "This code expires in 5 minutes.",
                "If you did not request this account, ignore this message.",
            ]
        )
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if bool(smtp_user) != bool(smtp_password):
                raise OtpDeliveryError("SMTP username and password must be configured together.")
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise OtpDeliveryError("Email OTP could not be sent.") from exc


def send_sms_otp(phone: str, otp: str) -> bool:
    sms_provider = os.getenv("SMS_PROVIDER", "").strip()
    sms_api_key = os.getenv("SMS_API_KEY", "").strip()
    if not sms_provider or not sms_api_key:
        logger.info("SMS OTP provider is not configured; skipping SMS OTP for %s.", phone)
        return False

    logger.info("SMS OTP provider %s is configured, but no SMS adapter is enabled.", sms_provider)
    return False
