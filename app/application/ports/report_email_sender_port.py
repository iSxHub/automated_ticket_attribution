from __future__ import annotations
from pathlib import Path
from typing import Protocol


class ReportEmailSenderPort(Protocol):
    def send_report_email(
        self,
        subject: str,
        body: str,
        attachments: list[Path],
        html_body: str | None = None,
    ) -> None:
        ...