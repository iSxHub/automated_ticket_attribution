from __future__ import annotations
import logging
from app.infrastructure.helpdesk_client import HelpdeskAPIError
from app.application.helpdesk_services import HelpdeskService
from app.infrastructure.config_loader import load_email_config
from app.infrastructure.service_catalog_client import ServiceCatalogClient, ServiceCatalogError
from app.domain.helpdesk import HelpdeskRequest
from app.domain.service_catalog import ServiceCatalog
from app.infrastructure.email_sender import SMTPSender
from app.application.send_report import send_report
from datetime import datetime
from pathlib import Path
from app.infrastructure.report_log import SQLiteReportLog
from typing import Iterable


logger = logging.getLogger(__name__)

def _load_helpdesk_requests(service: HelpdeskService) -> list[HelpdeskRequest]:
    try:
        requests_ = service.load_helpdesk_requests()
    except HelpdeskAPIError as exc:
        logger.error("Failed to load helpdesk requests: %s", exc)
        raise SystemExit(1) from exc

    logger.info("Successfully loaded %d requests", len(requests_))
    return requests_

def _load_service_catalog(catalog_client: ServiceCatalogClient) -> ServiceCatalog:
    try:
        service_catalog = catalog_client.fetch_catalog()
    except ServiceCatalogError as exc:
        logger.error("Failed to load Service Catalog: %s", exc)
        raise SystemExit(1) from exc

    logger.info(
        "Service Catalog loaded: %d categories",
        len(service_catalog.categories),
    )
    return service_catalog

def _log_sample_requests(requests_: list[HelpdeskRequest], limit: int = 5) -> None:
    for req in requests_[:limit]:
        logger.info(
            "[part 1] Request ID=%s short_description=%r",
            req.raw_id,
            req.short_description,
        )

def _send_report(
    report_path: list[Path],
    report_log: SQLiteReportLog,
) -> None:
    email_config = load_email_config()
    email_sender = SMTPSender(email_config)

    try:
        attachment_paths = _resolve_report_paths(report_path)
    except FileNotFoundError as exc:
        logger.error(
            "Cannot send report email because an attachment file is missing: %s",
            exc,
        )
        raise SystemExit(1) from exc

    send_report(
        email_sender=email_sender,
        attachment_paths=attachment_paths,
        codebase_url="https://github.com/Steaxy/automated_ticket_attribution",
        candidate_name=email_config.candidate_name,
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
    report_log: SQLiteReportLog,
    explicit_report: str | None,
) -> tuple[list[Path], Path | None]:
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
    paths: list[Path] = []
    for path in report_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Report file does not exist: {path}")
        paths.append(path.resolve())
    return paths