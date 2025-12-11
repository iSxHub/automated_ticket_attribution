from __future__ import annotations
import logging
from app.application.helpdesk_services import HelpdeskService
from app.infrastructure.service_catalog_client import ServiceCatalogClient
from app.infrastructure.llm_classifier import LLMClassifier
from app.application.missing_sla import missing_sla
from app.application.classify_requests import classify_requests
from app.cmd.spinner import Spinner
from app.infrastructure.save_excel import save_excel
from pathlib import Path
from app.infrastructure.report_log import SQLiteReportLog
from app.cmd.pipeline_helpers import (
    _load_service_catalog,
    _log_sample_requests,
    _send_report,
    _collect_unsent_reports,
)
from dataclasses import dataclass
from app.infrastructure.excel import ExcelReportError


logger = logging.getLogger(__name__)

@dataclass
class PipelineDeps:
    project_root: Path
    helpdesk_service: HelpdeskService
    service_catalog_client: ServiceCatalogClient
    llm_classifier: LLMClassifier
    report_log: SQLiteReportLog
    batch_size: int

def run_pipeline(deps: PipelineDeps, explicit_report_path: str | None = None) -> None:
    project_root = deps.project_root
    report_log = deps.report_log

    # check if any reports were unsent
    unsent_reports, explicit_report_path_obj = _collect_unsent_reports(
        project_root=project_root,
        report_log=report_log,
        explicit_report=explicit_report_path,
    )

    # send all unsent reports if any
    if unsent_reports:
        logger.info(
            "Found %d unsent report(s); sending them without calling LLM",
            len(unsent_reports),
        )
        _send_report(unsent_reports, report_log)
        return

    # if a specific report is already logged as sent — nothing to do
    if explicit_report_path_obj is not None:
        logger.info(
            "Explicit report %s is already logged as sent and no unsent reports remain",
            explicit_report_path_obj,
        )
        return

    # [part 1] fetch helpdesk requests
    requests_ = deps.helpdesk_service.load_helpdesk_requests()

    # [part 2] fetch service catalog
    service_catalog = _load_service_catalog(deps.service_catalog_client)

    # [part 3 and 4] classify the requests by LLM
    # classify all requests (even if not success by LLM) and log first 3 of them
    # (displaying spinner while requests in LLM in progress)
    with Spinner("Classifying helpdesk requests with LLM"):
        classified_requests = classify_requests(
            deps.llm_classifier,
            service_catalog,
            requests_,
            batch_size=deps.batch_size,
        )

    # [part 5] build Excel file
    missing_sla(classified_requests, service_catalog)
    try:
        excel_path_str = save_excel(classified_requests)
    except ExcelReportError as exc:
        logger.error("Aborting pipeline: failed to save Excel report: %s", exc)
        return

    _log_sample_requests(requests_)

    report_path = Path(excel_path_str).resolve()

    # [part 6] send the report to email
    _send_report([report_path], report_log)