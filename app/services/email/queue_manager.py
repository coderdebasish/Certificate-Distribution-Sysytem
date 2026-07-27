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
            if not p.email or "@" not in p.email:
                errors.append(f"{p.full_name}: Invalid email address ({p.email or 'missing'}).")
                continue

            cert = cert_map.get(p.certificate_id)
            cert_id = cert.id if cert else 0
            cert_name = (cert.renamed_filename or cert.original_filename) if cert else f"{p.full_name}.pdf"
            cert_path = (cert.renamed_file_path or cert.original_file_path) if cert else ""

            # Fallback path search if cert_path does not exist
            if not cert_path or not Path(cert_path).exists():
                proj_dir = Path(project.project_dir)
                possible_paths = [
                    proj_dir / "Renamed_Certificates" / cert_name,
                    proj_dir / "Renamed Certificates" / cert_name,
                    proj_dir / "Renamed_Certificates" / f"{p.full_name}.pdf",
                    proj_dir / "Renamed Certificates" / f"{p.full_name}.pdf",
                    proj_dir.parent / "Renamed_Certificates" / cert_name,
                    proj_dir.parent / "Renamed Certificates" / cert_name,
                    proj_dir.parent / "Renamed_Certificates" / f"{p.full_name}.pdf",
                    proj_dir.parent / "Renamed Certificates" / f"{p.full_name}.pdf",
                ]
                for candidate in possible_paths:
                    if candidate.exists():
                        cert_path = str(candidate)
                        break

            if not cert_path or not Path(cert_path).exists():
                errors.append(f"{p.full_name}: Certificate file not found for email attachment.")
                continue

            # Render placeholders
            context = self._engine.build_context(
                name=p.full_name,
                email=p.email,
                certificate_filename=cert_name,
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

            items.append(EmailQueueItem(
                project_id=project.id,
                queue_position=position,
                participant_id=p.id,
                certificate_id=cert_id,
                template_id=template.id,
                to_email=p.email,
                to_name=p.full_name,
                subject=result.subject,
                body_html=result.body_html,
                attachment_path=cert_path,
            ))

        return items, errors
