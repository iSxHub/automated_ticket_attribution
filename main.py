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


logger = logging.getLogger(__name__)

def logging_conf() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def main() -> None:
    logging_conf()

    config = load_helpdesk_config()
    client = HelpdeskClient(config)

    # raw data check
    # raw = client.fetch_raw()
    # import pprint
    # pprint.pp(raw)
    # return

    service = HelpdeskService(client)

    catalog_config = load_service_catalog_config()
    catalog_client = ServiceCatalogClient(catalog_config)

    # [part 1] fetch helpdesk requests
    try:
        requests_ = service.load_helpdesk_requests()
    except HelpdeskAPIError as exc:
        logging.getLogger(__name__).error("Failed to load helpdesk requests: %s", exc)
        raise SystemExit(1) from exc
    logger.info("Successfully loaded %d requests", len(requests_))

    # [part 2] fetch service catalog
    try:
        service_catalog = catalog_client.fetch_catalog()
    except ServiceCatalogError as exc:
        logger.error("Failed to load Service Catalog: %s", exc)
        raise SystemExit(1) from exc
    logger.info(
        "Service Catalog loaded: %d categories",
        len(service_catalog.categories),
    )

    # [part 3 and 4] classify the requests by LLM
    llm_config = load_llm_config()
    llm = LLMClassifier(llm_config)

    # classify all requests (even if not success by LLM) and log first 3 of them
    classified_requests = classify_requests(llm, service_catalog, requests_)

    # [part 5] build Excel file
    missing_sla(classified_requests, service_catalog)

    try:
        excel_bytes = build_excel(classified_requests)
    except ExcelReportError as exc:
        logger.error("Could not generate Excel report: %s", exc)
    else:
        output_path = "classified_helpdesk_requests.xlsx"
        with open(output_path, "wb") as f:
            f.write(excel_bytes)
        logger.info("[part 5] Excel report generated at %s", output_path)

    for req in requests_[:5]:
        logger.info("[part 1] Request ID=%s short_description=%r", req.raw_id, req.short_description)

if __name__ == "__main__":
    main()