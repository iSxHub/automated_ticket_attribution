

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
- If the Service Catalog defines an SLA for the chosen request_type, you MUST return that exact SLA (unit and value) in the JSON, even when the value is 0. Never replace a defined SLA with null or omit it.

Rules:
- You MUST respond with STRICT JSON, no extra text.
- JSON schema:
  {{
    "request_category": "<category name or null>",
    "request_type": "<request type name or null>",
    "sla_unit": "<hours|days|minutes or null>",
    "sla_value": <integer or null>
  }}
- Never return null for "sla_value" when the Service Catalog defines an SLA for the chosen "request_type". For example, if the catalog SLA is 0 hours, you MUST return "sla_unit": "hours" and "sla_value": 0.

Service Catalog:
{catalog}

Helpdesk request:
ID: {request_id}
Short description: {short_description}
Raw payload JSON: {raw_payload}
"""

LLM_BATCH_PROMPT_TEMPLATE = """
You are an internal IT helpdesk ticket classifier.

You receive:
1) An IT Service Catalog with categories, request types, and their SLAs.
2) A list of helpdesk requests, each with an ID, short description, and raw payload.

Your job:
- For EACH helpdesk request, choose the best matching request_category and request_type from the Service Catalog.
- request_category and request_type MUST be taken verbatim from the Service Catalog lines above.
- Choose a reasonable SLA (unit + integer value) based on the catalog entries.
- If the catalog already defines SLA for a chosen request type, use that SLA directly.
- If nothing fits, use "Other/Uncategorized" for category and "General Inquiry/Undefined" for request_type.
- If you are not sure, pick the closest match and still return a best-effort SLA.
- If the Service Catalog defines an SLA for the chosen request_type, you MUST return that exact SLA (unit and value) in the JSON, even when the value is 0. Never replace a defined SLA with null or omit it.

Rules:
- You MUST respond with STRICT JSON, no extra text.
- JSON schema:
  {{
    "items": [
      {{
        "raw_id": "<request id as string>",
        "request_category": "<category name or null>",
        "request_type": "<request type name or null>",
        "sla_unit": "<hours|days|minutes or null>",
        "sla_value": <integer or null>
      }}
    ]
  }}
- Never return null for "sla_value" when the Service Catalog defines an SLA for the chosen "request_type". For example, if the catalog SLA is 0 hours, you MUST return "sla_unit": "hours" and "sla_value": 0.

Service Catalog:
{catalog}

Helpdesk requests:
{requests_block}
"""