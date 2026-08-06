"""
app.services.email.gmail_provider
===================================
Gmail SMTP provider implementation with high deliverability,
anti-spam headers, and MIME multipart compliance.

Authentication uses Gmail App Passwords — never the user's Google password.
Credentials are stored encrypted via app.utils.crypto.
"""

from __future__ import annotations

import logging
import re
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from app.services.email.base import EmailProvider, EmailMessage, SendResult

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


class GmailProvider(EmailProvider):
    """
    Sends emails through Gmail using SMTP with TLS.

    Implements full MIME multipart/alternative structure (Plain Text + HTML),
    RFC-compliant headers (Message-ID, Date, Reply-To), and UTF-8 formatting
    to maximize inbox deliverability and bypass spam filters.
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
        self._sender_name = sender_name.strip() or self._email_address.split("@")[0]

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

    def create_draft(self, message: EmailMessage) -> SendResult:
        """Save email directly to user's Gmail Drafts folder using IMAP SSL."""
        self._assert_configured()
        import imaplib
        import time

        try:
            mime = self._build_mime(message)
            with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
                imap.login(self._email_address, self._app_password)
                now = imaplib.Time2Internaldate(time.time())
                res, _ = imap.append("[Gmail]/Drafts", "\\Draft", now, mime.as_bytes())
                if res != "OK":
                    res, _ = imap.append("Drafts", "\\Draft", now, mime.as_bytes())

            logger.info("Email drafted to Gmail Drafts for %s", message.to_email)
            return SendResult(success=True)
        except Exception as exc:
            logger.error("Failed to draft email for %s: %s", message.to_email, exc)
            return SendResult(success=False, error_message=str(exc))

    # -----------------------------------------------------------------------
    # Internal MIME Builder (Anti-Spam & Deliverability Engine)
    # -----------------------------------------------------------------------

    def _build_mime(self, message: EmailMessage) -> MIMEMultipart:
        msg = MIMEMultipart("mixed")

        # RFC-compliant headers
        sender = formataddr((self._sender_name, self._email_address))
        recipient = formataddr((message.to_name, message.to_email)) if message.to_name else message.to_email

        domain = self._email_address.split("@")[-1] if "@" in self._email_address else "gmail.com"

        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = message.subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=domain)
        msg["Reply-To"] = self._email_address
        msg["X-Mailer"] = "Certificate Distribution System/1.0"
        msg["Auto-Submitted"] = "auto-generated"

        # Alternative container for Plain Text + HTML (Required to pass Gmail spam filters)
        alt = MIMEMultipart("alternative")
        plain_text = self._strip_html(message.body_html)
        
        alt.attach(MIMEText(plain_text, "plain", "utf-8"))
        alt.attach(MIMEText(message.body_html, "html", "utf-8"))
        
        msg.attach(alt)

        # PDF Attachment
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

    @staticmethod
    def _strip_html(html_content: str) -> str:
        """Convert HTML body into clean plain text for anti-spam multipart alternative compliance."""
        text = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        lines = [line.strip() for line in text.splitlines()]
        return '\n'.join(line for line in lines if line)

    def _assert_configured(self) -> None:
        if not self._email_address or not self._app_password:
            raise RuntimeError(
                "GmailProvider is not configured. Call configure() first."
            )
