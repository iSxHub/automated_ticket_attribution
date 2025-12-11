from __future__ import annotations
import logging
from pathlib import Path
from typing import Protocol
from app.application.send_report_email_template import build_email_body


logger = logging.getLogger(__name__)

class ReportEmailSender(Protocol):
    def send_report_email(
            self,
            subject: str,
            body: str,
            attachments: list[Path],
            html_body: str | None = None,
    ) -> None:
        ...

def send_report(
    email_sender: ReportEmailSender,
    attachment_paths: list[Path],
    codebase_url: str,
    candidate_name: str,
) -> None:
    subject = f"Automation Engineer interview - technical task - {candidate_name}"

    text_body, html_body = build_email_body(
        codebase_url=codebase_url,
        candidate_name=candidate_name,
    )

    logger.info(
        "Sending classified report %r with %d attachment(s)",
        subject,
        len(attachment_paths),
    )

    email_sender.send_report_email(
        subject,
        text_body,
        attachment_paths,
        html_body,
    )