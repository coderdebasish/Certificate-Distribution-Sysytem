"""
app.services.email.queue_manager
==================================
Builds the email sending queue from validated participants,
certificates, and the active template.

This module DOES NOT send emails.
That is the responsibility of EmailWorker.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.models.email_queue import EmailQueueItem
from app.models.participant import Participant
from app.models.certificate import Certificate
from app.models.email_template import EmailTemplate
from app.services.placeholder.engine import PlaceholderEngine
from app.models.project import Project

logger = logging.getLogger(__name__)


class QueueBuilder:
    """
    Generates a fully-rendered EmailQueueItem for every participant.

    Pre-renders all placeholders so that the EmailWorker only needs to
    call send() — no template logic during sending.
    """

    def __init__(self) -> None:
        self._engine = PlaceholderEngine()

    def build(
        self,
        project: Project,
        participants: list[Participant],
        cert_map: dict[int, Certificate],    # {certificate_id: Certificate}
        template: EmailTemplate,
    ) -> tuple[list[EmailQueueItem], list[str]]:
        """
        Build the queue and return (items, validation_errors).

        validation_errors is empty if every item is ready to send.
        """
        items: list[EmailQueueItem] = []
        errors: list[str] = []

        for position, p in enumerate(participants, start=1):
            cert = cert_map.get(p.certificate_id)

            # Validation
            if not cert:
                errors.append(f"{p.full_name}: No certificate assigned.")
                continue
            if not Path(cert.renamed_file_path).exists():
                errors.append(f"{p.full_name}: Certificate file not found: {cert.renamed_file_path}")
                continue
            if "@" not in p.email:
                errors.append(f"{p.full_name}: Invalid email: {p.email}")
                continue

            # Render placeholders
            context = self._engine.build_context(
                name=p.full_name,
                email=p.email,
                certificate_filename=cert.renamed_filename,
                event_name=project.event_name,
                project_name=project.name,
                college=p.college,
                department=p.department,
                designation=p.designation,
            )
            result = self._engine.render(
                subject=template.subject,
                body_html=template.body_html,
                context=context,
            )
            if not result.is_valid:
                errors.append(
                    f"{p.full_name}: Unknown placeholders: {result.unknown_placeholders}"
                )
                continue

            items.append(EmailQueueItem(
                project_id=project.id,
                queue_position=position,
                participant_id=p.id,
                certificate_id=cert.id,
                template_id=template.id,
                to_email=p.email,
                to_name=p.full_name,
                subject=result.subject,
                body_html=result.body_html,
                attachment_path=cert.renamed_file_path,
            ))

        return items, errors
