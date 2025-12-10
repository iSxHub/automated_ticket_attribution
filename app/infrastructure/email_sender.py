from __future__ import annotations
import logging
import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from app.config import EmailConfig


logger = logging.getLogger(__name__)

class EmailSendError(RuntimeError):
    """Raised when sending the report email fails."""

class SMTPSender:
    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    # send a single email with one or more attachments
    def send_report_email(
        self,
        subject: str,
        body: str,
        reports: list[Path],
    ) -> None:
        if not reports:
            raise EmailSendError("No attachments provided for report email")

        for report in reports:
            if not report.is_file():
                raise EmailSendError(f"Attachment does not exist: {report}")

        total_size = sum(p.stat().st_size for p in reports)
        logger.info(
            "Preparing email to %s with %d attachment(s) (total %d bytes)",
            self._config.recipient,
            len(reports),
            total_size,
        )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._config.sender
        msg["To"] = self._config.recipient
        msg.set_content(body)

        for report in reports:
            mime_type, _ = mimetypes.guess_type(report.name)
            if mime_type is None:
                maintype, subtype = "application", "octet-stream"
            else:
                maintype, subtype = mime_type.split("/", 1)

            with report.open("rb") as f:
                file_bytes = f.read()

            msg.add_attachment(
                file_bytes,
                maintype=maintype,
                subtype=subtype,
                filename=report.name,
            )

        logger.info(
            "Connecting to SMTP server %s:%s (TLS=%s)...",
            self._config.smtp_host,
            self._config.smtp_port,
            self._config.use_tls,
        )

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as smtp:
                if self._config.use_tls:
                    smtp.starttls(context=context)

                smtp.login(self._config.username, self._config.password)
                smtp.send_message(msg)

        except smtplib.SMTPException as exc:
            logger.exception("Failed to send report email via SMTP")
            raise EmailSendError("Failed to send report email") from exc

        logger.info("Report email successfully sent to %s", self._config.recipient)