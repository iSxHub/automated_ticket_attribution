from __future__ import annotations
import logging
from typing import Any, Dict, List
import requests
from requests import HTTPError, RequestException
from app.config import HelpdeskAPIConfig
from app.domain.helpdesk import HelpdeskRequest
import time


logger = logging.getLogger(__name__)

class HelpdeskAPIError(RuntimeError):
    """Raised when the Service Catalog cannot be retrieved, parsed, or validated."""

class HelpdeskClient:
    """HTTP client for fetching raw helpdesk requests from the Helpdesk API.
        Uses the configured URL and credentials to POST a JSON payload and then
        maps the response into HelpdeskRequest domain objects.
        """

    def __init__(
        self,
        config: HelpdeskAPIConfig,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self._config = config
        self._session = requests.Session()
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    def _post_json(self) -> Any:
        """Call the Helpdesk API and return the parsed JSON body.
            Raises HelpdeskAPIError if the HTTP request fails or if the response
            body is not valid JSON.
            """

        payload = {
            "api_key": self._config.api_key,
            "api_secret": self._config.api_secret,
        }

        # retry POST with exponential backoff on HTTP/network errors
        response: requests.Response | None = None
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._session.post(
                    self._config.url,
                    json=payload,
                    timeout=self._config.timeout_seconds,
                )
                response.raise_for_status()
                break
            except (HTTPError, RequestException) as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    msg = (
                        f"Error calling Helpdesk API after {self._max_retries} "
                        f"attempts: {exc}"
                    )
                    logger.error(msg)
                    raise HelpdeskAPIError(msg) from exc

                sleep_seconds = self._backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "Helpdesk API call failed on attempt %d/%d: %s; "
                    "retrying in %.1f seconds",
                    attempt,
                    self._max_retries,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

        if response is None:
            msg = "Helpdesk API call failed without a response object"
            logger.error(msg)
            if last_exc is not None:
                raise HelpdeskAPIError(msg) from last_exc
            raise HelpdeskAPIError(msg)

        try:
            return response.json()
        except ValueError as exc:
            msg = "Failed to parse Helpdesk API response as JSON"
            logger.error(msg)
            raise HelpdeskAPIError(msg) from exc

    def fetch_raw(self) -> Any:
        return self._post_json()

    def fetch_requests(self) -> List[HelpdeskRequest]:
        """Fetch helpdesk requests and map them into HelpdeskRequest objects.
            Handles several common response shapes, logs basic response metadata,
            and skips any non-dict items in the payload. Raises HelpdeskAPIError
            if the response shape is unexpected.
            """

        data = self._post_json()
        logger.info(
            "Raw Helpdesk API response keys: %s",
            list(data.keys()) if isinstance(data, dict) else type(data),
        )

        items = self._extract_items(data)

        requests_list: List[HelpdeskRequest] = []
        for item in items:
            if not isinstance(item, dict):
                logger.warning("Skipping non-object item in response: %r", item)
                continue

            raw_id = _safe_str(item.get("id") or item.get("ticket_id"))
            short_description = _safe_str(
                item.get("short_description") or item.get("subject")
            )

            requests_list.append(
                HelpdeskRequest(
                    raw_id=raw_id,
                    short_description=short_description,
                    raw_payload=item,
                )
            )

        logger.info("Fetched %d helpdesk requests", len(requests_list))
        return requests_list

    def _extract_items(self, data: Any) -> List[Dict[str, Any]]:
        """Extract a list of item dicts from the raw Helpdesk API JSON.

            Supports responses where the items are:
            - a top-level list of dicts, or
            - under data (list), or
            - under data.requests (list).

            Raises HelpdeskAPIError if the response does not match any of the
            expected shapes.
            """

        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            payload = data.get("data", data)

            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]

            if isinstance(payload, dict):
                requests = payload.get("requests")
                if isinstance(requests, list):
                    return [item for item in requests if isinstance(item, dict)]

                logger.error(
                    "Helpdesk API 'data' dict has no 'requests' list. data keys=%s, payload keys=%s",
                    list(data.keys()),
                    list(payload.keys()),
                )
                raise HelpdeskAPIError(
                    "Unexpected response shape from Helpdesk API: "
                    "'data.requests' key missing or not a list"
                )

            logger.error(
                "Helpdesk API 'data' has unexpected type: %s",
                type(payload).__name__,
            )
            raise HelpdeskAPIError(
                "Unexpected response shape from Helpdesk API: 'data' is not dict or list"
            )

        msg = f"Unexpected response format from Helpdesk API: {type(data).__name__}"
        logger.error(msg)
        raise HelpdeskAPIError(msg)

def _safe_str(value: Any) -> str | None:
    """Return value as string, or None if the value itself is None."""

    if value is None:
        return None
    return str(value)