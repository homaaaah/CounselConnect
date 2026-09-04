"""Email notifications via SMTP (Gmail-compatible).

Graceful degradation: when SMTP credentials are unset (dev machines),
emails are skipped with a log line so the application never fails because
of notifications. Configure with COUNSELCONNECT_SMTP_* variables:

Gmail setup:
1. Enable 2-Step Verification on the Google account.
2. Create an App Password (16 characters) at myaccount.google.com/apppasswords.
3. Set COUNSELCONNECT_SMTP_USER=<gmail address> and
   COUNSELCONNECT_SMTP_PASSWORD=<app password> in backend/.env.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("counselconnect.notifications")


def smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_user and settings.smtp_password)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True when actually sent.

    Skips (returns False) when SMTP is not configured; raises on network
    errors so callers can decide how to handle them.
    """
    settings = get_settings()
    if not smtp_configured():
        logger.info("SMTP not configured — skipping email to %s (%s)", to, subject)
        return False

    message = EmailMessage()
    message["From"] = f"CounselConnect <{settings.smtp_user}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
    logger.info("Email sent to %s (%s)", to, subject)
    return True
