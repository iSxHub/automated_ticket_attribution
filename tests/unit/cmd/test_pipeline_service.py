from __future__ import annotations
from pathlib import Path
from typing import Any
import app.cmd.pipeline_service as ps
from app.cmd.pipeline_service import PipelineDeps, run_pipeline
from collections.abc import Mapping, Sequence
from app.application.llm_classifier import LLMClassificationResult
from app.domain.helpdesk import HelpdeskRequest
from app.domain.service_catalog import ServiceCatalog


class FakeHelpdeskService:
    def __init__(self, requests_: list[HelpdeskRequest]) -> None:
        self.requests = requests_
        self.called = False

    def load_helpdesk_requests(self) -> list[HelpdeskRequest]:
        self.called = True
        return self.requests

class FakeServiceCatalogClient:
    def __init__(self) -> None:
        self.called = False

    def fetch_catalog(self) -> ServiceCatalog:
        self.called = True
        return ServiceCatalog(categories=[])

class FakeLLMClassifier:
    def __init__(self) -> None:
        self.batches: list[list[Any]] = []

    def classify_batch(
        self,
        requests: Sequence[HelpdeskRequest],
        service_catalog: ServiceCatalog,
    ) -> Mapping[str, LLMClassificationResult]:
        self.batches.append(list(requests))
        return {}

class FakeReportLog:
    def __init__(self) -> None:
        self.marked: list[Path] = []

    def get_record(self, path: Path) -> Any:
        return None

    def mark_sent(self, path: Path, created_at: Any) -> None:
        self.marked.append(path)

class FakeEmailBodyBuilder:
    def build(self, codebase_url: str, candidate_name: str) -> tuple[str, str]:
        text = f"Codebase: {codebase_url}\nName: {candidate_name}\n"
        html = f"<p>{codebase_url}</p><p>{candidate_name}</p>"
        return text, html

class FakeReportExporter:
    def __init__(self, report_path: Path) -> None:
        self.report_path = report_path
        self.called_with: list[Sequence[HelpdeskRequest]] = []

    def export(self, requests: Sequence[HelpdeskRequest]) -> Path:
        self.called_with.append(requests)
        self.report_path.write_bytes(b"report")
        return self.report_path

class FakeEmailSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[Path], str | None]] = []

    def send_report_email(self, subject: str, body: str, attachments: list[Path], html_body: str | None = None) -> None:
        self.calls.append((subject, body, attachments, html_body))

def _make_req(raw_id: str) -> HelpdeskRequest:
    return HelpdeskRequest(
        raw_id=raw_id,
        short_description=raw_id,
        raw_payload={},
    )

# no unsent reports, classification and send happen
def test_run_pipeline_happy_path(monkeypatch, tmp_path) -> None:
    # arrange
    fake_helpdesk = FakeHelpdeskService(requests_=[_make_req("req1"), _make_req("req2")])
    fake_catalog_client = FakeServiceCatalogClient()
    fake_llm = FakeLLMClassifier()
    fake_log = FakeReportLog()
    report_path = tmp_path / "report.xlsx"
    fake_exporter = FakeReportExporter(report_path=report_path)
    fake_email_sender = FakeEmailSender()

    deps = PipelineDeps(
        project_root=tmp_path,
        helpdesk_service=fake_helpdesk,
        service_catalog_client=fake_catalog_client,
        llm_classifier=fake_llm,
        report_log=fake_log,
        batch_size=10,
        email_body_builder=FakeEmailBodyBuilder(),
        report_exporter=fake_exporter,
        email_sender=fake_email_sender,
        codebase_url="https://github.com/Steaxy/automated_ticket_attribution",
        candidate_name="John Doe",
    )

    def fake_collect_unsent_reports(*args, **kwargs):
        # no unsent reports, no explicit report already sent
        return [], None

    def fake_load_service_catalog(_client):
        return "fake_catalog"

    def fake_classify_requests(llm, service_catalog, requests_, batch_size: int):
        # echo requests back
        assert llm is fake_llm
        assert service_catalog == "fake_catalog"
        assert [r.raw_id for r in requests_] == ["req1", "req2"]
        assert batch_size == 10
        return ["classified1", "classified2"]

    def fake_missing_sla(requests_, service_catalog):
        # no-op, ensure it is called with classified requests
        assert requests_ == ["classified1", "classified2"]
        assert service_catalog == "fake_catalog"

    def fake_log_sample_requests(requests_, limit: int = 5) -> None:
        assert [r.raw_id for r in requests_] == ["req1", "req2"]

    # patch module-level functions used by run_pipeline
    monkeypatch.setattr(ps, "_collect_unsent_reports", fake_collect_unsent_reports)
    monkeypatch.setattr(ps, "_load_service_catalog", fake_load_service_catalog)
    monkeypatch.setattr(ps, "classify_requests", fake_classify_requests)
    monkeypatch.setattr(ps, "missing_sla", fake_missing_sla)
    monkeypatch.setattr(ps, "_log_sample_requests", fake_log_sample_requests)

    # act
    run_pipeline(deps, explicit_report_path=None)

    # assert
    assert fake_helpdesk.called is True
    assert len(fake_email_sender.calls) == 1

    subject, body, attachments, html_body = fake_email_sender.calls[0]
    assert subject == "Automation Engineer interview - technical task - John Doe"
    assert "https://github.com/Steaxy/automated_ticket_attribution" in body

    # _send_report resolves paths -> should be resolved
    assert attachments == [report_path.resolve()]

    # report was marked as sent
    assert fake_log.marked == [report_path.resolve()]
    assert fake_exporter.called_with == [["classified1", "classified2"]]


def test_run_pipeline_sends_unsent_reports(monkeypatch, tmp_path) -> None:
    fake_helpdesk = FakeHelpdeskService(requests_=[_make_req("req1"), _make_req("req2")])
    fake_catalog_client = FakeServiceCatalogClient()
    fake_llm = FakeLLMClassifier()
    fake_log = FakeReportLog()
    report_path = tmp_path / "report.xlsx"
    fake_exporter = FakeReportExporter(report_path=report_path)
    fake_email_sender = FakeEmailSender()

    deps = PipelineDeps(
        project_root=tmp_path,
        helpdesk_service=fake_helpdesk,
        service_catalog_client=fake_catalog_client,
        llm_classifier=fake_llm,
        report_log=fake_log,
        batch_size=10,
        email_body_builder=FakeEmailBodyBuilder(),
        report_exporter=fake_exporter,
        email_sender=fake_email_sender,
        codebase_url="https://github.com/Steaxy/automated_ticket_attribution",
        candidate_name="John Doe",
    )

    unsent1 = tmp_path / "unsent1.xlsx"
    unsent2 = tmp_path / "unsent2.xlsx"
    unsent1.write_bytes(b"data1")
    unsent2.write_bytes(b"data2")

    def fake_collect_unsent_reports(*args, **kwargs):
        # two unsent reports, no explicit report
        return [unsent1, unsent2], None

    # ensure these are not called
    def fail_classify_requests(*args, **kwargs):
        raise AssertionError("classify_requests should not be called when unsent reports exist")

    monkeypatch.setattr(ps, "_collect_unsent_reports", fake_collect_unsent_reports)
    monkeypatch.setattr(ps, "classify_requests", fail_classify_requests)

    run_pipeline(deps, explicit_report_path=None)

    # helpdesk should never be called in this branch
    assert fake_helpdesk.called is False

    # exporter should never be called in this branch
    assert fake_exporter.called_with == []

    # email should be sent with BOTH unsent attachments
    assert len(fake_email_sender.calls) == 1
    subject, body, attachments, html_body = fake_email_sender.calls[0]

    assert subject == "Automation Engineer interview - technical task - John Doe"
    assert set(attachments) == {unsent1.resolve(), unsent2.resolve()}

    # and both should be marked as sent
    assert set(fake_log.marked) == {unsent1.resolve(), unsent2.resolve()}