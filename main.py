import logging
from app.infrastructure.helpdesk_client import HelpdeskClient, HelpdeskAPIError
from app.application.helpdesk_services import HelpdeskService
from app.config import (
    load_helpdesk_config,
    load_service_catalog_config,
    load_llm_config,
)
from app.infrastructure.service_catalog_client import ServiceCatalogClient, ServiceCatalogError
from app.infrastructure.llm_gemini_classifier import GeminiLLMClassifier
from app.application.llm_classifier import LLMClassificationError


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

    # helpdesk requests
    try:
        requests_ = service.load_helpdesk_requests()
    except HelpdeskAPIError as exc:
        logging.getLogger(__name__).error("Failed to load helpdesk requests: %s", exc)
        raise SystemExit(1) from exc
    logger.info("Successfully loaded %d requests", len(requests_))

    # service catalog
    try:
        service_catalog = catalog_client.fetch_catalog()
    except ServiceCatalogError as exc:
        logger.error("Failed to load Service Catalog: %s", exc)
        raise SystemExit(1) from exc
    logger.info(
        "Service Catalog loaded: %d categories",
        len(service_catalog.categories),
    )

    # 3.

    llm_config = load_llm_config()
    gemini = GeminiLLMClassifier(llm_config)

    # classify first 3 requests and log results
    for req in requests_[:3]:
        try:
            result = gemini.classify_helpdesk_request(req, service_catalog)
        except LLMClassificationError as exc:
            logger.error("LLM classification failed for %s: %s", req.raw_id, exc)
            continue

        logger.info(
            "[part 3 and 4] LLM result for %s: category=%r type=%r sla=%r %r",
            req.raw_id,
            result.request_category,
            result.request_type,
            result.sla_value,
            result.sla_unit,
        )

    for req in requests_[:5]:
        logger.info("[part 1] Request ID=%s short_description=%r", req.raw_id, req.short_description)


if __name__ == "__main__":
    main()