from __future__ import annotations
import json
import logging
from typing import Any
from app.application.llm_classifier import (
    LLMClassificationResult,
    LLMClassificationError,
)
from app.domain.helpdesk import HelpdeskRequest
from app.domain.service_catalog import ServiceCatalog
from app.config import LLMConfig
from google import genai
from google.genai import types
from app.shared.normalization import normalize_str_or_none, normalize_int_or_none
from app.infrastructure.llm_classifier_prompt import LLM_PROMPT_TEMPLATE, LLM_BATCH_PROMPT_TEMPLATE


logger = logging.getLogger(__name__)

class LLMClassifier:
    def __init__(self, config: LLMConfig) -> None:
        if not config.api_key:
            raise LLMClassificationError("LLM_API_KEY must be configured.")

        self._client = genai.Client(api_key=config.api_key)
        self._model = config.model_name

    def classify_helpdesk_request(
        self,
        request: HelpdeskRequest,
        catalog: ServiceCatalog,
    ) -> LLMClassificationResult:
        catalog_fragment = _catalog_to_prompt_fragment(catalog)
        raw_payload_str = json.dumps(request.raw_payload or {}, ensure_ascii=False)

        prompt = LLM_PROMPT_TEMPLATE.format(
            catalog=catalog_fragment,
            request_id=request.raw_id or "",
            short_description=request.short_description or "",
            raw_payload=raw_payload_str,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
        except Exception as exc:
            logger.error("LLM classification call failed: %s", exc)
            raise LLMClassificationError("LLM API call failed") from exc

        text = _get_response_text(response)

        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("LLM returned non-JSON output: %r", text[:300])
            raise LLMClassificationError("LLM output was not valid JSON") from exc

        result = LLMClassificationResult(
            request_category=normalize_str_or_none(data.get("request_category")),
            request_type=normalize_str_or_none(data.get("request_type")),
            sla_unit=normalize_str_or_none(data.get("sla_unit")),
            sla_value=normalize_int_or_none(data.get("sla_value")),
        )
        logger.debug(
            "LLM classification result for request %s: %s",
            getattr(request, "raw_id", None),
            result,
        )
        return result

    def classify_batch(self, requests: list[HelpdeskRequest], catalog: ServiceCatalog) -> dict[
        str, LLMClassificationResult]:
        if not requests:
            return {}

        catalog_fragment = _catalog_to_prompt_fragment(catalog)
        requests_block = _build_batch(requests)

        prompt = LLM_BATCH_PROMPT_TEMPLATE.format(
            catalog=catalog_fragment,
            requests_block=requests_block,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
        except Exception as exc:
            logger.error("LLM batch classification call failed: %s", exc)
            raise LLMClassificationError("LLM batch API call failed") from exc

        text = _get_response_text(response)

        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("LLM batch returned non-JSON output: %r", text[:300])
            raise LLMClassificationError("LLM batch output was not valid JSON") from exc

        items = data.get("items")
        if not isinstance(items, list):
            logger.error("LLM batch JSON missing 'items' list: %r", data)
            raise LLMClassificationError("LLM batch JSON missing 'items' list")

        results: dict[str, LLMClassificationResult] = {}
        for item in items:
            if not isinstance(item, dict):
                continue

            raw_id_raw = item.get("raw_id")
            raw_id = normalize_str_or_none(raw_id_raw)
            if not raw_id:
                continue

            result = LLMClassificationResult(
                request_category=normalize_str_or_none(item.get("request_category")),
                request_type=normalize_str_or_none(item.get("request_type")),
                sla_unit=normalize_str_or_none(item.get("sla_unit")),
                sla_value=normalize_int_or_none(item.get("sla_value")),
            )
            results[raw_id] = result

        logger.debug("LLM batch classification produced %d items", len(results))
        return results

def _catalog_to_prompt_fragment(catalog: ServiceCatalog) -> str:
    lines: list[str] = []
    for category in catalog.categories:
        for req_type in category.requests:
            sla = req_type.sla
            lines.append(
                f"- Category: {category.name} | "
                f"Request Type: {req_type.name} | "
                f"SLA: {sla.value} {sla.unit}"
            )
    return "\n".join(lines)

def _build_batch(requests: list[HelpdeskRequest]) -> str:
    parts: list[str] = []
    for req in requests:
        raw_payload_str = json.dumps(req.raw_payload or {}, ensure_ascii=False)
        parts.append(
            f"ID: {req.raw_id or ''}\n"
            f"Short description: {req.short_description or ''}\n"
            f"Raw payload JSON: {raw_payload_str}"
        )
    return "\n\n---\n\n".join(parts)

def _get_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    raise LLMClassificationError("LLM response contained no text")