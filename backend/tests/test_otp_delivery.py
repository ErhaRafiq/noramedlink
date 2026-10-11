"""Signup code delivery (services/otp_delivery_service.py): codes are never logged (AGENTS.md section 8)."""

import logging
from dataclasses import replace
from typing import ClassVar

import pytest

from services import otp_delivery_service
from services.otp_delivery_service import OtpDeliveryError, send_email_otp, send_sms_otp

CODE = "493817"


@pytest.fixture(autouse=True)
def capture_nora_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    # logging_config stops "nora" propagating to the root logger; caplog listens there.
    monkeypatch.setattr(logging.getLogger("nora"), "propagate", True)


class FakeSmtp:
    sent: ClassVar[list] = []

    def __init__(self, host, port, timeout):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        FakeSmtp.sent.append(message)


def configure(monkeypatch: pytest.MonkeyPatch, **smtp) -> None:
    monkeypatch.setattr(otp_delivery_service, "settings", replace(otp_delivery_service.settings, **smtp))


def test_without_smtp_the_code_is_not_sent_and_not_logged(monkeypatch, caplog):
    configure(monkeypatch, smtp_host="", smtp_from_email="")
    with caplog.at_level(logging.DEBUG, logger="nora"), pytest.raises(OtpDeliveryError):
        send_email_otp("patient1@test.com", CODE)
    assert CODE not in caplog.text
    assert "not configured" in caplog.text


def test_with_smtp_the_code_goes_only_into_the_email(monkeypatch, caplog):
    configure(
        monkeypatch, smtp_host="smtp.test", smtp_from_email="noreply@test.com", smtp_username="", smtp_password=""
    )
    monkeypatch.setattr(otp_delivery_service.smtplib, "SMTP", FakeSmtp)
    FakeSmtp.sent = []
    with caplog.at_level(logging.DEBUG, logger="nora"):
        send_email_otp("patient1@test.com", CODE)
    assert CODE in FakeSmtp.sent[0].get_content()
    assert FakeSmtp.sent[0]["To"] == "patient1@test.com"
    assert CODE not in caplog.text


def test_sms_is_skipped_without_logging_the_number_or_code(caplog):
    with caplog.at_level(logging.DEBUG, logger="nora"):
        assert send_sms_otp("0300 1234567", CODE) is False
    assert CODE not in caplog.text and "1234567" not in caplog.text
