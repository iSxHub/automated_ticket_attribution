from __future__ import annotations
import logging
import time
from typing import Protocol, Mapping
from app.domain.helpdesk import HelpdeskRequest
from app.domain.service_catalog import ServiceCatalog
from app.application.llm_classifier import LLMClassificationResult, LLMClassificationError
from app.application.classify_requests_progress import _batches_progress


logger = logging.getLogger(__name__)

class RequestClassifier(Protocol):
    def classify_batch(
        self,
        requests: list[HelpdeskRequest],
        service_catalog: ServiceCatalog,
    ) -> Mapping[str, LLMClassificationResult]:
        ...


def classify_requests(classifier: RequestClassifier, service_catalog: ServiceCatalog, requests_: list[HelpdeskRequest], batch_size: int = 20, examples_to_log: int = 3) -> list[HelpdeskRequest]:
    classified_requests: list[HelpdeskRequest] = []
    logged_examples = 0

    for batch_index, total_batches, batch_start, batch_end, batch in _batches_progress(
            requests_,
            batch_size,
    ):
        try:
            batch_results = classifier.classify_batch(batch, service_catalog)
        except LLMClassificationError as exc:
            logger.error(
                "LLM batch classification failed for requests %d..%d: %s",
                batch_start,
                batch_start + len(batch) - 1,
                exc,
            )
            # if the batch call fails, still include the raw requests in Excel
            classified_requests.extend(batch)
            continue

        logger.info(
            "[part 3 and 4] LLM batch classified %d requests (index %d..%d)",
            len(batch),
            batch_start,
            batch_start + len(batch) - 1,
        )

        for req in batch:
            raw_id = req.raw_id or ""
            result = batch_results.get(raw_id)
            if result is not None:
                req.request_category = result.request_category
                req.request_type = result.request_type
                req.sla_unit = result.sla_unit
                req.sla_value = result.sla_value

                if logged_examples < examples_to_log:
                    logger.info(
                        "[part 3 and 4] LLM result for %s: category=%r type=%r sla=%r %r",
                        req.raw_id,
                        result.request_category,
                        result.request_type,
                        result.sla_value,
                        result.sla_unit,
                    )
                    logged_examples += 1

            classified_requests.append(req)

        # batch every 3 sec
        time.sleep(3)

    return classified_requests