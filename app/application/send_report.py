from __future__ import annotations
import logging
from pathlib import Path
from app.application.ports.email_body_builder_port import EmailBodyBuilder
from app.application.ports.report_email_sender_port import ReportEmailSenderPort


logger = logging.getLogger(__name__)

def send_report(
    email_sender: ReportEmailSenderPort,
    body_builder: EmailBodyBuilder,
    attachment_paths: list[Path],
    codebase_url: str,
    candidate_name: str,
    email_title: str,
) -> None:
    subject = f"{email_title} - {candidate_name}"

    text_body, html_body = body_builder.build(
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