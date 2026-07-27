"""
app.services.email.base
========================
Abstract email provider interface.

All email providers (Gmail, Outlook, Resend, ...) must implement this
interface so the rest of the application remains provider-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EmailMessage:
    """A fully rendered email ready to be sent."""
    to_email: str
    to_name: str
    subject: str
    body_html: str
    attachment_path: str = ""   # Path to the certificate PDF
    from_email: str = ""
    from_name: str = ""


@dataclass
class SendResult:
    """Result of a single send attempt."""
    success: bool = False
    error_message: str = ""
    provider_message_id: str = ""


class EmailProvider(ABC):
    """
    Abstract email provider.

    Concrete classes implement SMTP / API-specific logic while the
    EmailSendingEngine only deals with this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name, e.g. 'Gmail'."""

    @abstractmethod
    def test_connection(self) -> SendResult:
        """
        Verify that credentials are valid and the server is reachable.
        Should NOT send a real email.
        """

    @abstractmethod
    def send(self, message: EmailMessage) -> SendResult:
        """
        Send one email.

        :param message: Fully rendered EmailMessage including attachment path.
        :returns: SendResult indicating success or failure with details.
        """

    @abstractmethod
    def configure(self, **kwargs) -> None:
        """
        Apply provider-specific configuration (credentials, server, port, etc.).
        Implementations must validate and raise ValueError on bad config.
        """
