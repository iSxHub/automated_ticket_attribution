from __future__ import annotations
import logging
from app.infrastructure.helpdesk_client import HelpdeskClient
from app.application.helpdesk_services import HelpdeskService
from app.config import (
    load_helpdesk_config,
    load_service_catalog_config,
    load_llm_config,
    load_report_log_config,
)
from app.infrastructure.service_catalog_client import ServiceCatalogClient
from app.infrastructure.llm_classifier import LLMClassifier
from app.application.missing_sla import missing_sla
from app.application.classify_requests import classify_requests
from app.cmd.spinner import Spinner
from app.infrastructure.save_excel import save_excel
from pathlib import Path
from app.infrastructure.report_log import SQLiteReportLog
from app.cmd.pipeline_helpers import (
    _load_helpdesk_requests,
    _load_service_catalog,
    _log_sample_requests,
    _send_report,
    _collect_unsent_reports,
)


logger = logging.getLogger(__name__)

def pipeline(report: str | None = None) -> None:

    # check if the report was already sent
    project_root = Path(__file__).resolve().parent.parent.parent
    report_log_config = load_report_log_config()

    # db
    db_path = Path(report_log_config.db_path)
    if not db_path.is_absolute():
        db_path = project_root / db_path
    report_log = SQLiteReportLog(db_path)

    # check if any reports were unsent
    unsent_reports, explicit_report_path = _collect_unsent_reports(
        project_root=project_root,
        report_log=report_log,
        explicit_report=report,
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
    if explicit_report_path is not None:
        logger.info(
            "Explicit report %s is already logged as sent and no unsent reports remain",
            explicit_report_path,
        )
        return

    helpdesk_config = load_helpdesk_config()
    client = HelpdeskClient(helpdesk_config)
    service = HelpdeskService(client)

    catalog_config = load_service_catalog_config()
    catalog_client = ServiceCatalogClient(catalog_config)

    # [part 1] fetch helpdesk requests
    requests_ = _load_helpdesk_requests(service)

    # [part 2] fetch service catalog
    service_catalog = _load_service_catalog(catalog_client)

    # [part 3 and 4] classify the requests by LLM
    llm_config = load_llm_config()
    llm = LLMClassifier(llm_config)

    # classify all requests (even if not success by LLM) and log first 3 of them (displaying spinner while requests in LLM in progress)
    with Spinner("Classifying helpdesk requests with LLM"):
        classified_requests = classify_requests(
            llm,
            service_catalog,
            requests_,
            batch_size=llm_config.batch_size,
        )

    # [part 5] build Excel file
    missing_sla(classified_requests, service_catalog)
    excel = save_excel(classified_requests)

    _log_sample_requests(requests_)

    report = Path(excel).resolve()

    # [part 6] send the report to email
    _send_report([report], report_log)
