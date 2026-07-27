"""
app.services.placeholder.engine
================================
Email template placeholder engine.

Replaces {placeholder} tokens in email subjects and bodies with
participant-specific values.  Unknown placeholders are flagged as
validation errors rather than silently ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.config.constants import SUPPORTED_PLACEHOLDERS


PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")


@dataclass
class RenderResult:
    subject: str = ""
    body_html: str = ""
    unknown_placeholders: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.unknown_placeholders is None:
            self.unknown_placeholders = []

    @property
    def is_valid(self) -> bool:
        return len(self.unknown_placeholders) == 0


class PlaceholderEngine:
    """
    Renders email templates by substituting placeholder tokens.

    Usage::

        engine = PlaceholderEngine()
        context = engine.build_context(participant, project)
        result = engine.render(subject=tmpl.subject, body_html=tmpl.body_html, context=context)
    """

    def render(
        self,
        subject: str,
        body_html: str,
        context: dict[str, str],
    ) -> RenderResult:
        """
        Perform placeholder substitution.

        :param subject:   Raw email subject with {placeholders}.
        :param body_html: Raw HTML email body with {placeholders}.
        :param context:   Mapping of placeholder name → value.
        :returns: RenderResult with substituted content and any unknowns.
        """
        unknown: list[str] = []

        def replacer(match: re.Match) -> str:
            key = match.group(1)
            if key in context:
                return context[key]
            token = f"{{{key}}}"
            if token not in SUPPORTED_PLACEHOLDERS:
                unknown.append(token)
            return match.group(0)  # Leave unknown placeholders as-is

        rendered_subject = PLACEHOLDER_PATTERN.sub(replacer, subject)
        rendered_body = PLACEHOLDER_PATTERN.sub(replacer, body_html)

        return RenderResult(
            subject=rendered_subject,
            body_html=rendered_body,
            unknown_placeholders=list(set(unknown)),
        )

    def build_context(
        self,
        name: str,
        email: str,
        certificate_filename: str = "",
        event_name: str = "",
        project_name: str = "",
        college: str = "",
        department: str = "",
        designation: str = "",
    ) -> dict[str, str]:
        """
        Build a substitution context dictionary for one participant.
        """
        today = date.today()
        return {
            "name": name,
            "email": email,
            "certificate": certificate_filename,
            "event_name": event_name,
            "project_name": project_name,
            "college": college,
            "department": department,
            "designation": designation,
            "date": today.strftime("%d %B %Y"),
            "year": str(today.year),
        }

    def validate_template(self, subject: str, body_html: str) -> list[str]:
        """
        Return a list of unknown placeholder tokens found in the template.
        An empty list means the template is valid.
        """
        all_tokens = set(PLACEHOLDER_PATTERN.findall(subject)) | set(
            PLACEHOLDER_PATTERN.findall(body_html)
        )
        supported_names = {p.strip("{}") for p in SUPPORTED_PLACEHOLDERS}
        return [f"{{{tok}}}" for tok in all_tokens if tok not in supported_names]
