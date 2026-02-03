from __future__ import annotations
import logging
from app.domain.helpdesk import HelpdeskRequest
from app.application.send_report import send_report
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence
from app.application.ports.email_body_builder_port import EmailBodyBuilder
from app.cmd.ports import ReportLogPort, ServiceCatalogClientPort
from app.domain.service_catalog import ServiceCatalog
from app.application.ports.report_email_sender_port import ReportEmailSenderPort
from app.shared.errors import ServiceCatalogLoadError


logger = logging.getLogger(__name__)

def _load_service_catalog(client: ServiceCatalogClientPort) -> ServiceCatalog:
    """Logs the number of categories in the loaded catalog."""

    try:
        service_catalog = client.fetch_catalog()
    except ServiceCatalogLoadError as exc:
        logger.error("Failed to load Service Catalog: %s", exc)
        raise

    logger.info(
        "Service Catalog loaded: %d categories",
        len(service_catalog.categories),
    )
    return service_catalog

def _log_sample_requests(requests_: Sequence[HelpdeskRequest], limit: int = 5) -> None:
    """Logs up to ``limit`` requests, showing their raw IDs and short descriptions.
        This is intended to give quick visibility into the incoming data shape.
        """

    for req in requests_[:limit]:
        logger.info(
            "[part 1] Request ID=%s short_description=%r",
            req.id,
            req.short_description,
        )

def _send_report(
    report_paths: list[Path],
    report_log: ReportLogPort,
    body_builder: EmailBodyBuilder,
    email_sender: ReportEmailSenderPort,
    codebase_url: str,
    candidate_name: str,
    email_title: str,
) -> None:
    """Send one or more report files via injected ports and mark them as sent."""

    try:
        attachment_paths = _resolve_report_paths(report_paths)
    except FileNotFoundError as exc:
        logger.error(
            "Cannot send report email because an attachment file is missing: %s",
            exc,
        )
        raise SystemExit(1) from exc

    send_report(
        email_sender=email_sender,
        body_builder=body_builder,
        attachment_paths=attachment_paths,
        codebase_url=codebase_url,
        candidate_name=candidate_name,
        email_title=email_title,
    )

    # mark the resolved paths as sent
    now = datetime.now()
    for report in attachment_paths:
        report_log.mark_sent(report, created_at=now)
        logger.info(
            "Classified report %s marked as sent in log at %s",
            report.name,
            now.isoformat(sep=" ", timespec="seconds"),
        )

def _collect_unsent_reports(
    project_root: Path,
    report_log: ReportLogPort,
    explicit_report: str | None,
) -> tuple[list[Path], Path | None]:
    """Collect report files that have not yet been logged as sent.

        If ``explicit_report`` is provided, only that path is considered and
        returned (if it has no sent record in the log). Otherwise, all ``*.xlsx``
        files inside ``project_root / "output"`` are scanned and sorted by
        modification time (oldest first).

        Returns a tuple ``(unsent_report_paths, explicit_report_path)`` where:
          - ``unsent_report_paths`` is the list of report paths that do not have a
            corresponding 'sent' record in the log.
          - ``explicit_report_path`` is the resolved Path for the explicitly
            provided report, or ``None`` when auto-discovery is used.
        """

    if explicit_report is not None:
        candidates = [Path(explicit_report).resolve()]
        explicit_report_path: Path | None = candidates[0]
    else:
        output_dir = project_root / "output"
        if not output_dir.is_dir():
            return [], None

        candidates = sorted(
            output_dir.glob("*.xlsx"),
            key=lambda p: p.stat().st_mtime,
        )
        explicit_report_path = None

    unsent_report_paths: list[Path] = []
    for candidate in candidates:
        record = report_log.get_record(candidate)
        if record is None:
            unsent_report_paths.append(candidate)
        else:
            logger.info(
                "Classified report %s was already sent at %s",
                candidate.name,
                record.created_at.isoformat(sep=" ", timespec="seconds"),
            )

    return unsent_report_paths, explicit_report_path

def _resolve_report_paths(report_paths: Iterable[Path]) -> list[Path]:
    """Validate that all given report paths exist and return their absolute paths.
        Raises FileNotFoundError if any of the paths does not point to an existing
        file. All returned paths are resolved to absolute Paths.
        """

    paths: list[Path] = []
    for path in report_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Report file does not exist: {path}")
        paths.append(path.resolve())
    return paths