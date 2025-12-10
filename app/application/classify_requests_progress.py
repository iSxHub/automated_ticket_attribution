from __future__ import annotations
import logging
from typing import Iterator, Tuple
from app.domain.helpdesk import HelpdeskRequest


logger = logging.getLogger(__name__)

# display progress for batches when classify_requests in terminal
def _batches_progress(requests_: list[HelpdeskRequest], batch_size: int, ) -> Iterator[Tuple[int, int, int, int, list[HelpdeskRequest]]]:
    total_requests = len(requests_)
    if total_requests == 0:
        logger.info("[part 3 and 4] No requests to classify; skipping LLM step")
        return

    total_batches = (total_requests + batch_size - 1) // batch_size

    for batch_index, batch_start in enumerate(
        range(0, total_requests, batch_size),
    ):
        batch = requests_[batch_start : batch_start + batch_size]
        batch_end = batch_start + len(batch) - 1

        logger.info(
            "[part 3 and 4] Sending batch %d/%d to LLM "
            "(%d requests, index %d..%d)...",
            batch_index + 1,
            total_batches,
            len(batch),
            batch_start,
            batch_end,
        )

        yield batch_index, total_batches, batch_start, batch_end, batch