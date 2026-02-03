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

class FakeEmailBodyBuilder:
    def build(self, codebase_url: str, candidate_name: str) -> tuple[str, str]:
        text = (
            "Hi,\n\n"
            "Please find attached the classified helpdesk requests report.\n\n"
            f"Codebase: {codebase_url}\n\n"
            "Best regards,\n"
            f"{candidate_name}\n"
        )
        html = f"<p>Codebase: {codebase_url}</p><p>{candidate_name}</p>"
        return text, html

def test_send_report(tmp_path: Path) -> None:
    # given
    report_file = tmp_path / "report.xlsx"
    report_file.write_bytes(b"dummy content")

    sender = FakeReportEmailSender()
    body_builder = FakeEmailBodyBuilder()
    codebase_url = "https://github.com/Steaxy/automated_ticket_attribution"
    candidate_name = "John Doe"
    email_title = "Tasks report"

    send_report(
        email_sender=sender,
        body_builder=body_builder,
        attachment_paths=[report_file],
        codebase_url=codebase_url,
        candidate_name=candidate_name,
        email_title=email_title,
    )

    # then
    assert len(sender.calls) == 1

    subject, body, attachments, html_body = sender.calls[0]

    assert subject == "Tasks report - John Doe"
    assert codebase_url in body
    assert "Please find attached the classified helpdesk requests report." in body
    assert "Best regards," in body
    assert "John Doe" in body
    assert attachments == [report_file]