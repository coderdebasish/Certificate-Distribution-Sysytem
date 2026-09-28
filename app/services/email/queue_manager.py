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
            cert_id, cert_name, cert_path = self._resolve_cert_path(project, p, cert)

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
                team_name=p.team_name,
                leader_name=p.full_name if p.is_team_leader else "",
                team_members=p.full_name,
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

    def build_team_queue(
        self,
        project: Project,
        participants: list[Participant],
        cert_map: dict[int, Certificate],
        template: EmailTemplate,
    ) -> tuple[list[EmailQueueItem], list[str]]:
        """
        Build the queue grouped by teams.

        Emails are addressed ONLY to each team's leader, with ALL team members'
        certificates attached to that single email.
        Participants without a team name are treated as individual 1-person teams
        so no participant is omitted.
        """
        items: list[EmailQueueItem] = []
        errors: list[str] = []

        # 1. Group participants by team
        team_groups: dict[str, list[Participant]] = {}
        for p in participants:
            t_name = (p.team_name or "").strip()
            key = t_name if t_name else f"__individual_{p.id}__"
            team_groups.setdefault(key, []).append(p)

        position = 1
        for team_key, members in team_groups.items():
            is_named_team = not team_key.startswith("__individual_")
            team_display_name = team_key if is_named_team else ""

            # 2. Identify the leader: member with is_team_leader=True, else first member
            leader = next((m for m in members if m.is_team_leader), members[0])

            if not leader.email or "@" not in leader.email:
                prefix = f"Team '{team_display_name}'" if team_display_name else leader.full_name
                errors.append(f"{prefix}: Leader {leader.full_name} has invalid email ({leader.email or 'missing'}).")
                continue

            # 3. Collect certificates for all members in the team
            cert_paths: list[str] = []
            cert_names: list[str] = []
            primary_cert_id = 0

            for m in members:
                m_cert = cert_map.get(m.certificate_id)
                cid, cname, cpath = self._resolve_cert_path(project, m, m_cert)
                if m.id == leader.id:
                    primary_cert_id = cid
                if cname:
                    cert_names.append(cname)
                if cpath:
                    cert_paths.append(cpath)

            member_names = [m.full_name for m in members]
            team_members_str = ", ".join(member_names)

            # 4. Build context
            context = self._engine.build_context(
                name=leader.full_name,
                email=leader.email,
                certificate_filename=", ".join(cert_names) if cert_names else f"{leader.full_name}.pdf",
                event_name=project.event_name,
                project_name=project.name,
                college=leader.college or members[0].college,
                department=leader.department or members[0].department,
                designation=leader.designation or ("Team Leader" if is_named_team else ""),
                team_name=team_display_name,
                leader_name=leader.full_name,
                team_members=team_members_str,
            )

            result = self._engine.render(
                subject=template.subject,
                body_html=template.body_html,
                context=context,
            )

            items.append(EmailQueueItem(
                project_id=project.id,
                queue_position=position,
                participant_id=leader.id,
                certificate_id=primary_cert_id,
                template_id=template.id,
                to_email=leader.email,
                to_name=leader.full_name,
                subject=result.subject,
                body_html=result.body_html,
                attachment_path=";".join(cert_paths),
            ))
            position += 1

        return items, errors

    def _resolve_cert_path(
        self,
        project: Project,
        p: Participant,
        cert: Certificate | None,
    ) -> tuple[int, str, str]:
        """Resolve certificate id, display name, and absolute file path."""
        cert_id = cert.id if cert else 0
        cert_name = (cert.renamed_filename or cert.original_filename) if cert else f"{p.full_name}.pdf"
        cert_path = (cert.renamed_file_path or cert.original_file_path) if cert else ""

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
            cert_path = ""

        return cert_id, cert_name, cert_path
