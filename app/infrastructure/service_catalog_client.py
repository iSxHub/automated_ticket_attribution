from __future__ import annotations
import logging
from typing import Any, List
import requests
from requests import HTTPError, RequestException
from app.config import ServiceCatalogConfig
from app.domain.service_catalog import SLA, ServiceRequestType, ServiceCategory, ServiceCatalog
import time
from app.shared.errors import ServiceCatalogLoadError


logger = logging.getLogger(__name__)

class ServiceCatalogError(RuntimeError):
    """Raised when the Service Catalog cannot be retrieved, parsed, or validated."""

class ServiceCatalogClient:
    """HTTP client for downloading and parsing the Service Catalog.
        Fetches a YAML document from the configured URL and maps it into
        ServiceCatalog domain objects.
        """

    def __init__(
        self,
        config: ServiceCatalogConfig,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self._config = config
        self._session = requests.Session()
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    def fetch_catalog(self) -> ServiceCatalog:
        """Download and parse the Service Catalog into domain models.
            Raises ServiceCatalogError on HTTP failures, YAML parse errors, or when
            the YAML structure does not match the expected schema.
            """

        try:
            text = self._download_text()
            data = self._parse_yaml(text)

            try:
                categories_raw = data["service_catalog"]["catalog"]["categories"]
            except (TypeError, KeyError) as exc:
                msg = (
                    "Unexpected Service Catalog shape; "
                    "expected 'service_catalog.catalog.categories'"
                )
                logger.error("%s: %s", msg, exc)
                raise ServiceCatalogError(msg) from exc

            try:
                categories: List[ServiceCategory] = []
                for cat in categories_raw:
                    name = cat["name"]
                    requests_raw = cat["requests"]

                    requests = [
                        ServiceRequestType(
                            name=req["name"],
                            sla=SLA(
                                unit=req["sla"]["unit"],
                                value=int(req["sla"]["value"]),
                            ),
                        )
                        for req in requests_raw
                    ]

                    categories.append(ServiceCategory(name=name, requests=requests))
            except (KeyError, TypeError, ValueError) as exc:
                msg = "Failed to map Service Catalog to domain models"
                logger.error("%s: %s", msg, exc)
                raise ServiceCatalogError(msg) from exc

            catalog = ServiceCatalog(categories=categories)
            logger.info(
                "[part 2] Loaded Service Catalog: %d categories, %d total request types",
                len(catalog.categories),
                sum(len(c.requests) for c in catalog.categories),
            )
            return catalog
        except ServiceCatalogError as exc:
            raise ServiceCatalogLoadError(str(exc)) from exc
        except (RequestException, HTTPError, ValueError, TypeError, KeyError) as exc:
            raise ServiceCatalogLoadError("Failed to load Service Catalog") from exc

    def _download_text(self) -> str:
        """Download the raw YAML text for the Service Catalog."""

        # retry GET with exponential backoff on HTTP/network errors
        response: requests.Response | None = None
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._session.get(
                    self._config.url,
                    timeout=self._config.timeout_seconds,
                )
                response.raise_for_status()
                break
            except (HTTPError, RequestException) as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    msg = (
                        "Error calling Service Catalog endpoint after "
                        f"{self._max_retries} attempts: {exc}"
                    )
                    logger.error(msg)
                    raise ServiceCatalogError(msg) from exc

                sleep_seconds = self._backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "Service Catalog request failed on attempt %d/%d: %s; "
                    "retrying in %.1f seconds",
                    attempt,
                    self._max_retries,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

        if response is None:
            msg = "Service Catalog request failed without a response object"
            logger.error(msg)
            if last_exc is not None:
                raise ServiceCatalogError(msg) from last_exc
            raise ServiceCatalogError(msg)

        text = response.text
        logger.debug("Raw Service Catalog response length=%d", len(text))
        return text

    def _parse_yaml(self, text: str) -> Any:
        """Parse the given YAML text into a Python structure"""

        try:
            import yaml
        except ImportError as exc:
            msg = "PyYAML is required to parse the Service Catalog"
            logger.error(msg)
            raise ServiceCatalogError(msg) from exc

        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            msg = "Failed to parse Service Catalog YAML"
            logger.error(msg)
            raise ServiceCatalogError(msg) from exc