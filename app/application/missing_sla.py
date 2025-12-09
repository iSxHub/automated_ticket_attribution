from app.domain.helpdesk import HelpdeskRequest
from app.domain.service_catalog import ServiceCatalog
import logging


logger = logging.getLogger(__name__)

# fill missing SLA from service catalog after LLM. Check only if exact category, type match
def missing_sla(requests: list[HelpdeskRequest], catalog: ServiceCatalog) -> None:
    logger.info(
        "Filling missing SLA for %d requests using Service Catalog",
        len(requests),
    )

    # Build (category, request_type) -> (unit, value) index from catalog
    sla_index: dict[tuple[str, str], tuple[str, int]] = {}
    for cat in catalog.categories:
        for req_type in cat.requests:
            key = (cat.name, req_type.name)
            sla_index[key] = (req_type.sla.unit, req_type.sla.value)

    for req in requests:
        if not req.request_category or not req.request_type:
            continue

        key = (req.request_category, req.request_type)
        if key not in sla_index:
            continue

        # only override if LLM didn't provide SLA
        if req.sla_unit is None or req.sla_value is None:
            unit, value = sla_index[key]
            req.sla_unit = unit
            req.sla_value = value