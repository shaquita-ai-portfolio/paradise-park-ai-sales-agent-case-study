"""Non-blocking lead and recommendation notifications for the sales team."""

from __future__ import annotations

from email.message import EmailMessage
import logging
import os
import smtplib
import ssl
from typing import Mapping


LOGGER = logging.getLogger(__name__)
DEFAULT_ADMIN_EMAIL = "notifications@example.com"


def send_admin_report(*, subject: str, fields: Mapping[str, object]) -> bool:
    """Email an admin report when SMTP is configured; never expose credentials."""

    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    recipient = os.getenv("ADMIN_NOTIFICATION_EMAIL", DEFAULT_ADMIN_EMAIL).strip()
    if not username or not password:
        LOGGER.warning(
            "Admin notification skipped because SMTP_USERNAME or SMTP_PASSWORD is not configured."
        )
        return False

    message = EmailMessage()
    message["Subject"] = " ".join(subject.splitlines())
    message["From"] = os.getenv("SMTP_FROM_EMAIL", username).strip()
    message["To"] = recipient
    message.set_content(
        "\n".join(f"{label}: {value}" for label, value in fields.items())
    )

    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "465"))
    try:
        with smtplib.SMTP_SSL(
            host,
            port,
            context=ssl.create_default_context(),
            timeout=12,
        ) as client:
            client.login(username, password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        LOGGER.exception("Admin notification could not be sent: %s", error)
        return False
    return True
