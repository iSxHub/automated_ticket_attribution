from __future__ import annotations
from pathlib import Path
import pytest
from app.application.send_report import send_classified_requests_report


class FakeReportEmailSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[Path]]] = []

    def send_report_email(
        self,
        subject: str,
        body: str,
        attachments: list[Path],
    ) -> None:
        self.calls.append((subject, body, attachments))

def test_send_classified_requests_report(tmp_path: Path) -> None:
    # given
    report_file = tmp_path / "report.xlsx"
    report_file.write_bytes(b"dummy content")

    sender = FakeReportEmailSender()
    codebase_url = "https://github.com/Steaxy/automated_ticket_attribution"
    candidate_name = "John Doe"

    send_classified_requests_report(
        email_sender=sender,
        reports=[str(report_file)],
        codebase_url=codebase_url,
        candidate_name=candidate_name,
    )

    # then
    assert len(sender.calls) == 1
    subject, body, attachments = sender.calls[0]

    assert subject == "Automation Engineer interview - technical task - John Doe"
    assert codebase_url in body
    assert "Please find attached the classified helpdesk requests report." in body
    assert "Best regards," in body
    assert "John Doe" in body
    assert attachments == [report_file]


def test_send_classified_requests_report_missing_file(tmp_path: Path) -> None:
    # given
    missing_file = tmp_path / "missing.xlsx"
    sender = FakeReportEmailSender()

    # when / then
    with pytest.raises(FileNotFoundError):
        send_classified_requests_report(
            email_sender=sender,
            reports=[str(missing_file)],
            codebase_url="https://example.com",
            candidate_name="John Doe",
        )