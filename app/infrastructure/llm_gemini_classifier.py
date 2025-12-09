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


logger = logging.getLogger(__name__)

LLM_PROMPT_TEMPLATE = """
You are an internal IT helpdesk ticket classifier.

You receive:
1) An IT Service Catalog with categories, request types, and their SLAs.
2) A single helpdesk request with a short description and raw payload.

Your job:
- request_category and request_type MUST be taken verbatim from the Service Catalog lines above.
- Choose a reasonable SLA (unit + integer value) based on the catalog entries.
- If the catalog already defines SLA for a chosen request type, use that SLA directly.
- If nothing fits, use "Other/Uncategorized" for category and "General Inquiry/Undefined" for request_type.
- If you are not sure, pick the closest match and still return a best-effort SLA.

Rules:
- You MUST respond with STRICT JSON, no extra text.
- JSON schema:
  {{
    "request_category": "<category name or null>",
    "request_type": "<request type name or null>",
    "sla_unit": "<hours|days|minutes or null>",
    "sla_value": <integer or null>
  }}

Service Catalog:
{catalog}

Helpdesk request:
ID: {request_id}
Short description: {short_description}
Raw payload JSON: {raw_payload}
"""

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

class GeminiLLMClassifier:
    def __init__(self, config: LLMConfig) -> None:
        if not config.api_key:
            raise LLMClassificationError("GEMINI_API_KEY must be configured.")

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
            logger.error("Gemini classification call failed: %s", exc)
            raise LLMClassificationError("Gemini API call failed") from exc

        text = _get_response_text(response)

        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Gemini returned non-JSON output: %r", text[:300])
            raise LLMClassificationError("Gemini output was not valid JSON") from exc

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

def _get_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    raise LLMClassificationError("Gemini response contained no text")