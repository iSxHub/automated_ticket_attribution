from datetime import datetime
from pathlib import Path
from app.cmd.pipeline import _collect_unsent_reports
from app.infrastructure.report_log import SQLiteReportLog
from typing import cast


class _FakeRecord:
    def __init__(self, created_at: datetime) -> None:
        self.created_at = created_at


class _FakeReportLog:
    def __init__(self, sent_paths: set[Path]) -> None:
        self._sent = sent_paths

    def get_record(self, path: Path):
        if path.resolve() in self._sent:
            return _FakeRecord(datetime(2025, 12, 10, 10, 0, 0))
        return None

    def mark_sent(self, path: Path, created_at: datetime) -> None:
        pass


def test_collect_unsent_reports_explicit_not_logged(tmp_path):
    project_root = tmp_path

    report = tmp_path / "report.xlsx"
    report.write_bytes(b"test")

    fake_log = _FakeReportLog(sent_paths=set())

    unsent, explicit = _collect_unsent_reports(
        project_root=project_root,
        report_log=cast(SQLiteReportLog, fake_log),
        explicit_report=str(report),
    )

    assert unsent == [report.resolve()]
    assert explicit == report.resolve()


def test_collect_unsent_reports_explicit_already_logged(tmp_path):
    project_root = tmp_path

    report = tmp_path / "report.xlsx"
    report.write_bytes(b"test")

    fake_log = _FakeReportLog(sent_paths={report.resolve()})

    unsent, explicit = _collect_unsent_reports(
        project_root=project_root,
        report_log=cast(SQLiteReportLog, fake_log),
        explicit_report=str(report),
    )

    assert unsent == []
    assert explicit == report.resolve()


def test_collect_unsent_reports_scan_output_with_mixed_reports(tmp_path):
    project_root = tmp_path
    output_dir = project_root / "output"
    output_dir.mkdir()

    sent_file = output_dir / "sent.xlsx"
    unsent_file = output_dir / "unsent.xlsx"

    sent_file.write_bytes(b"sent")
    unsent_file.write_bytes(b"unsent")

    fake_log = _FakeReportLog(sent_paths={sent_file.resolve()})

    unsent, explicit = _collect_unsent_reports(
        project_root=project_root,
        report_log=cast(SQLiteReportLog, fake_log),
        explicit_report=None,
    )

    assert explicit is None
    assert unsent == [unsent_file.resolve()]


def test_collect_unsent_reports_no_output_dir(tmp_path):
    project_root = tmp_path
    fake_log = _FakeReportLog(sent_paths=set())

    unsent, explicit = _collect_unsent_reports(
        project_root=project_root,
        report_log=cast(SQLiteReportLog, fake_log),
        explicit_report=None,
    )

    assert unsent == []
    assert explicit is None