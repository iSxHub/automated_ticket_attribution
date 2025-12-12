from __future__ import annotations
import logging
from app.infrastructure.helpdesk_client import HelpdeskClient
from app.application.helpdesk_services import HelpdeskService
from app.infrastructure.config_loader import (
    load_helpdesk_config,
    load_service_catalog_config,
    load_llm_config,
    load_report_log_config,
)
from app.infrastructure.service_catalog_client import ServiceCatalogClient
from app.infrastructure.llm_classifier import LLMClassifier
from pathlib import Path
from app.infrastructure.report_log import SQLiteReportLog
from app.cmd.pipeline_service import run_pipeline, PipelineDeps
from app.infrastructure.email_templates.email_body_builder import TemplateEmailBodyBuilder
from app.infrastructure.report_exporter_excel import ExcelReportExporter
from app.infrastructure.config_loader import load_email_config
from app.infrastructure.email_sender import SMTPSender


logger = logging.getLogger(__name__)

def _build_pipeline_deps() -> PipelineDeps:
    project_root = Path(__file__).resolve().parent.parent.parent

    # db / report log
    report_log_config = load_report_log_config()
    db_path = Path(report_log_config.db_path)
    if not db_path.is_absolute():
        db_path = project_root / db_path
    report_log = SQLiteReportLog(db_path)

    # helpdesk
    helpdesk_config = load_helpdesk_config()
    helpdesk_client = HelpdeskClient(helpdesk_config)
    helpdesk_service = HelpdeskService(helpdesk_client)

    # service catalog
    service_catalog_config = load_service_catalog_config()
    service_catalog_client = ServiceCatalogClient(service_catalog_config)

    # llm
    llm_config = load_llm_config()
    llm_classifier = LLMClassifier(llm_config)

    # email body builder (templates)
    email_body_builder = TemplateEmailBodyBuilder()

    # email sender/config built
    email_config = load_email_config()
    email_sender = SMTPSender(email_config)

    # report exporter adapter
    report_exporter = ExcelReportExporter()

    return PipelineDeps(
        project_root=project_root,
        helpdesk_service=helpdesk_service,
        service_catalog_client=service_catalog_client,
        llm_classifier=llm_classifier,
        report_log=report_log,
        batch_size=llm_config.batch_size,
        email_body_builder=email_body_builder,
        report_exporter=report_exporter,
        email_sender=email_sender,
        codebase_url="https://github.com/Steaxy/automated_ticket_attribution",
        candidate_name=email_config.candidate_name,
    )

def pipeline(explicit_report_path: str | None = None) -> None:
    deps = _build_pipeline_deps()
    run_pipeline(deps, explicit_report_path=explicit_report_path)
