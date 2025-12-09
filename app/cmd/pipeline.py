from __future__ import annotations
import logging
from app.infrastructure.helpdesk_client import HelpdeskClient, HelpdeskAPIError
from app.application.helpdesk_services import HelpdeskService
from app.config import (
    load_helpdesk_config,
    load_service_catalog_config,
    load_llm_config,
)
from app.infrastructure.service_catalog_client import ServiceCatalogClient, ServiceCatalogError
from app.infrastructure.llm_classifier import LLMClassifier
from app.infrastructure.excel import build_excel, ExcelReportError
from app.application.missing_sla import missing_sla
from app.application.classify_requests import classify_requests
from app.domain.helpdesk import HelpdeskRequest
from app.domain.service_catalog import ServiceCatalog
from datetime import datetime


logger = logging.getLogger(__name__)

def pipeline() -> int:
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

    # classify all requests (even if not success by LLM) and log first 3 of them
    classified_requests = classify_requests(llm, service_catalog, requests_)

    # [part 5] build Excel file
    missing_sla(classified_requests, service_catalog)
    _build_excel(classified_requests)

    _log_sample_requests(requests_)

    return 0

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

def _build_excel(classified_requests: list[HelpdeskRequest], output_path: str | None = None) -> None:
    try:
        excel_bytes = build_excel(classified_requests)
    except ExcelReportError as exc:
        logger.error("Could not generate Excel report: %s", exc)
        return

    if output_path is None:
        now = datetime.now()
        timestamp = now.strftime("%d-%m-%Y %H-%M-%S")
        output_path = f"classified_requests_{timestamp}.xlsx"

    with open(output_path, "wb") as f:
        f.write(excel_bytes)

    logger.info("[part 5] Excel report generated at %s", output_path)

def _log_sample_requests(requests_: list[HelpdeskRequest], limit: int = 5) -> None:
    for req in requests_[:limit]:
        logger.info(
            "[part 1] Request ID=%s short_description=%r",
            req.raw_id,
            req.short_description,
        )