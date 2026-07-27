"""
app.models package — data model definitions.
"""

from app.models.project import Project, ProjectStage, ProjectStatus
from app.models.participant import Participant, MatchStatus, EmailStatus
from app.models.certificate import Certificate, CertificateStatus, ExtractionMethod
from app.models.email_template import EmailTemplate, EmailTemplate as Template, TemplateVersion
from app.models.email_queue import QueueItem, QueueStatus

__all__ = [
    "Project",
    "ProjectStage",
    "ProjectStatus",
    "Participant",
    "MatchStatus",
    "EmailStatus",
    "Certificate",
    "CertificateStatus",
    "ExtractionMethod",
    "EmailTemplate",
    "Template",
    "TemplateVersion",
    "QueueItem",
    "QueueStatus",
]
