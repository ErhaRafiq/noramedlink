import logging
import smtplib
from email.message import EmailMessage

from config import settings

logger = logging.getLogger("nora.otp")


class OtpDeliveryError(Exception):
    pass


def send_email_otp(email: str, otp: str) -> None:
    if settings.otp_dev_mode:
        logger.warning("Development signup OTP for %s: %s", email, otp)
        return

    smtp_host = settings.smtp_host
    smtp_port = settings.smtp_port
    smtp_user = settings.smtp_username
    smtp_password = settings.smtp_password
    smtp_from = settings.smtp_from_email
    smtp_from_name = settings.smtp_from_name
    use_tls = settings.smtp_use_tls
    allow_console = settings.otp_console_fallback

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
    sms_provider = settings.sms_provider
    if not sms_provider or not settings.sms_api_key:
        logger.info("SMS OTP provider is not configured; skipping the SMS code.")
        return False

    logger.info("SMS OTP provider %s is configured, but no SMS adapter is enabled.", sms_provider)
    return False
