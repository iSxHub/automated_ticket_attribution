from __future__ import annotations
import logging
from typing import List, Optional, Any
from app.domain.helpdesk import HelpdeskRequest
from app.domain.service_catalog import ServiceCatalog
from app.application.llm_classifier import (
    LLMClassifierFn,
    LLMClassificationResult,
    LLMClassificationError,
)
from app.shared.normalization import normalize_str_or_none


logger = logging.getLogger(__name__)

class ClassifyHelpdeskRequests:
    def __init__(self, classifier: LLMClassifierFn) -> None:
        self._classifier = classifier

    def execute(
        self,
        requests_: List[HelpdeskRequest],
        catalog: ServiceCatalog,
    ) -> List[HelpdeskRequest]:
        # Return all requests enriched with classification information.
        # Existing non-empty/positive fields on HelpdeskRequest are preserved.
        # Only empty/zero fields are filled with LLM results.
        results: List[HelpdeskRequest] = []

        for req in requests_:
            existing_cat, existing_type, existing_unit, existing_value = (
                _extract_existing_classification(req)
            )

            llm_result: Optional[LLMClassificationResult] = None
            if _needs_llm(existing_cat, existing_type, existing_unit, existing_value):
                try:
                    llm_result = self._classifier(req, catalog)
                except LLMClassificationError as exc:
                    logger.error(
                        "LLM classification failed for request %s: %s",
                        getattr(req, "raw_id", None),
                        exc,
                    )
                    # keep llm_result as None; only existing values (if any) will be used.

            # [part 4] merge existing values with LLM result back into the HelpdeskRequest object
            req.request_category = existing_cat or (
                llm_result.request_category if llm_result else None
            )
            req.request_type = existing_type or (
                llm_result.request_type if llm_result else None
            )
            req.sla_unit = existing_unit or (
                llm_result.sla_unit if llm_result else None
            )
            req.sla_value = existing_value or (
                llm_result.sla_value if llm_result else None
            )

            results.append(req)

        return results

def _extract_existing_classification(
    request: HelpdeskRequest,
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[int]]:

    # empty strings as missing
    # None as missing
    # sla_value <= 0 as missing
    cat_raw: Any = getattr(request, "request_category", None)
    type_raw: Any = getattr(request, "request_type", None)
    unit_raw: Any = getattr(request, "sla_unit", None)
    value_raw: Any = getattr(request, "sla_value", None)

    cat = normalize_str_or_none(cat_raw)
    req_type = normalize_str_or_none(type_raw)
    unit = normalize_str_or_none(unit_raw)

    value: Optional[int]
    try:
        v_int = int(value_raw) if value_raw is not None else None
        if v_int is None or v_int <= 0:
            value = None
        else:
            value = v_int
    except (TypeError, ValueError):
        value = None

    return cat, req_type, unit, value

def _needs_llm(
    request_category: Optional[str],
    request_type: Optional[str],
    sla_unit: Optional[str],
    sla_value: Optional[int],
) -> bool:
    # Return True if at least one classification/SLA field is missing.
    return (
        not request_category
        or not request_type
        or not sla_unit
        or sla_value is None
    )