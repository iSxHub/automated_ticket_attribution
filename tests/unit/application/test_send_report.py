from __future__ import annotations
from pathlib import Path
from app.application.send_report import send_report


class FakeReportEmailSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[Path], str | None]] = []

    def send_report_email(
        self,
        subject: str,
        body: str,
        attachments: list[Path],
        html_body: str | None = None,
    ) -> None:
        self.calls.append((subject, body, attachments, html_body))

def test_send_report(tmp_path: Path) -> None:
    # given
    report_file = tmp_path / "report.xlsx"
    report_file.write_bytes(b"dummy content")

    sender = FakeReportEmailSender()
    codebase_url = "https://github.com/Steaxy/automated_ticket_attribution"
    candidate_name = "John Doe"

    send_report(
        email_sender=sender,
        attachment_paths=[report_file],
        codebase_url=codebase_url,
        candidate_name=candidate_name,
    )

    # then
    assert len(sender.calls) == 1

    subject, body, attachments, html_body = sender.calls[0]

    assert subject == "Automation Engineer interview - technical task - John Doe"
    assert codebase_url in body
    assert "Please find attached the classified helpdesk requests report." in body
    assert "Best regards," in body
    assert "John Doe" in body
    assert attachments == [report_file]