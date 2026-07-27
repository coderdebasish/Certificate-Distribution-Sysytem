"""
app.services.email.gmail_provider
===================================
Gmail SMTP provider implementation.

Authentication uses Gmail App Passwords — never the user's Google password.
Credentials are stored encrypted via app.utils.crypto.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.services.email.base import EmailProvider, EmailMessage, SendResult

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


class GmailProvider(EmailProvider):
    """
    Sends emails through Gmail using SMTP with TLS.

    Credentials must be set with ``configure()`` before calling ``send()``.
    """

    def __init__(self) -> None:
        self._email_address: str = ""
        self._app_password: str = ""
        self._sender_name: str = ""

    @property
    def name(self) -> str:
        return "Gmail"

    def configure(self, email_address: str, app_password: str, sender_name: str = "") -> None:
        """
        Set Gmail credentials.

        :param email_address: The Gmail address to send from.
        :param app_password:  Google App Password (16-char, no spaces).
        :param sender_name:   Display name shown in recipient's inbox.
        """
        if not email_address or "@" not in email_address:
            raise ValueError("Invalid Gmail address.")
        if not app_password or len(app_password.replace(" ", "")) < 8:
            raise ValueError("Invalid App Password.")
        self._email_address = email_address.strip()
        self._app_password = app_password.replace(" ", "")
        self._sender_name = sender_name or email_address

    def test_connection(self) -> SendResult:
        """Attempt SMTP login without sending an email."""
        self._assert_configured()
        try:
            with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(self._email_address, self._app_password)
            return SendResult(success=True)
        except smtplib.SMTPAuthenticationError:
            return SendResult(
                success=False,
                error_message=(
                    "Authentication failed. Please check your Gmail address "
                    "and App Password. Make sure 2-Factor Authentication is enabled."
                ),
            )
        except smtplib.SMTPConnectError as exc:
            return SendResult(success=False, error_message=f"Cannot connect to Gmail: {exc}")
        except Exception as exc:
            return SendResult(success=False, error_message=str(exc))

    def send(self, message: EmailMessage) -> SendResult:
        """Send one email with an optional PDF attachment."""
        self._assert_configured()
        try:
            mime = self._build_mime(message)
            with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.login(self._email_address, self._app_password)
                server.sendmail(
                    self._email_address,
                    message.to_email,
                    mime.as_string(),
                )
            logger.info("Email sent to %s", message.to_email)
            return SendResult(success=True)
        except smtplib.SMTPRecipientsRefused:
            return SendResult(
                success=False,
                error_message=f"Address refused by server: {message.to_email}",
            )
        except Exception as exc:
            logger.error("Failed to send to %s: %s", message.to_email, exc)
            return SendResult(success=False, error_message=str(exc))

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _build_mime(self, message: EmailMessage) -> MIMEMultipart:
        msg = MIMEMultipart("mixed")
        msg["From"] = f"{self._sender_name} <{self._email_address}>"
        msg["To"] = f"{message.to_name} <{message.to_email}>" if message.to_name else message.to_email
        msg["Subject"] = message.subject

        # Body
        body = MIMEMultipart("alternative")
        body.attach(MIMEText(message.body_html, "html", "utf-8"))
        msg.attach(body)

        # Attachment
        if message.attachment_path:
            attachment_path = Path(message.attachment_path)
            if attachment_path.exists():
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), _subtype="pdf")
                    part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=attachment_path.name,
                    )
                    msg.attach(part)
            else:
                logger.warning("Attachment not found: %s", attachment_path)

        return msg

    def _assert_configured(self) -> None:
        if not self._email_address or not self._app_password:
            raise RuntimeError(
                "GmailProvider is not configured. Call configure() first."
            )
