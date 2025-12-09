from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Dict
import pytest
from app.infrastructure.llm_classifier import LLMClassifier, LLMClassificationResult
from app.application.llm_classifier import LLMClassificationError


@dataclass
class DummyLLMConfig:
    api_key: str = "dummy-key"
    model_name: str = "dummy-model"

@dataclass
class DummyHelpdeskRequest:
    raw_id: str
    short_description: str = ""
    raw_payload: Dict[str, Any] | None = None

@dataclass
class DummySLA:
    unit: str
    value: int

@dataclass
class DummyRequestType:
    name: str
    sla: DummySLA

@dataclass
class DummyCategory:
    name: str
    requests: list[DummyRequestType]

@dataclass
class DummyCatalog:
    categories: list[DummyCategory]

@dataclass
class DummyResponse:
    text: str

class DummyModels:
    def __init__(self, response: DummyResponse) -> None:
        self._response = response
        self.last_kwargs: dict[str, Any] | None = None

    def generate_content(self, **kwargs: Any) -> DummyResponse:
        self.last_kwargs = kwargs
        return self._response

class DummyClient:
    def __init__(self, response: DummyResponse) -> None:
        self.models = DummyModels(response)


# classify_batch parses JSON and returns mapping raw_id -> result
def test_classify_batch_happy_path() -> None:
    # fake LLM JSON output
    payload = {
        "items": [
            {
                "raw_id": "req_101",
                "request_category": "Access Management",
                "request_type": "Reset forgotten password",
                "sla_unit": "hours",
                "sla_value": 4,
            },
            {
                "raw_id": "req_102",
                "request_category": "Hardware Support",
                "request_type": "Laptop Repair/Replacement",
                "sla_unit": "days",
                "sla_value": 7,
            },
        ]
    }
    response = DummyResponse(text=json.dumps(payload))

    # construct classifier with dummy config and client
    cfg = DummyLLMConfig()
    classifier = LLMClassifier(cfg)                                                                                         # type: ignore[arg-type]
    classifier._client = DummyClient(response)                                                                              # type: ignore[attr-defined]

    # build minimal catalog (content is irrelevant, just needs to be structurally valid)
    catalog = DummyCatalog(
        categories=[
            DummyCategory(
                name="Access Management",
                requests=[DummyRequestType("Reset forgotten password", DummySLA("hours", 4))],
            ),
            DummyCategory(
                name="Hardware Support",
                requests=[DummyRequestType("Laptop Repair/Replacement", DummySLA("days", 7))],
            ),
        ]
    )

    requests = [
        DummyHelpdeskRequest(raw_id="req_101", short_description="Forgot my Okta password"),
        DummyHelpdeskRequest(raw_id="req_102", short_description="Laptop does not start"),
    ]

    results = classifier.classify_batch(requests, catalog)                                                                  # type: ignore[arg-type]

    assert set(results.keys()) == {"req_101", "req_102"}

    r1 = results["req_101"]
    assert isinstance(r1, LLMClassificationResult)
    assert r1.request_category == "Access Management"
    assert r1.request_type == "Reset forgotten password"
    assert r1.sla_unit == "hours"
    assert r1.sla_value == 4

    r2 = results["req_102"]
    assert r2.request_category == "Hardware Support"
    assert r2.request_type == "Laptop Repair/Replacement"
    assert r2.sla_unit == "days"
    assert r2.sla_value == 7

    # check that the classifier used the configured model name
    models = classifier._client.models                                                                                      # type: ignore[attr-defined]
    assert models.last_kwargs is not None
    assert models.last_kwargs["model"] == cfg.model_name


# empty input returns empty mapping and must not call generate_content
def test_classify_batch_empty_requests() -> None:
    response = DummyResponse(text=json.dumps({"items": []}))
    cfg = DummyLLMConfig()
    classifier = LLMClassifier(cfg)                                                                                         # type: ignore[arg-type]
    classifier._client = DummyClient(response)                                                                              # type: ignore[attr-defined]

    catalog = DummyCatalog(categories=[])
    results = classifier.classify_batch([], catalog)                                                                # type: ignore[arg-type]

    assert results == {}


# invalid JSON in response raises LLMClassificationError
def test_classify_batch_invalid_json_raises() -> None:
    response = DummyResponse(text="this is not json")
    cfg = DummyLLMConfig()
    classifier = LLMClassifier(cfg)                                                                                         # type: ignore[arg-type]
    classifier._client = DummyClient(response)                                                                              # type: ignore[attr-defined]

    catalog = DummyCatalog(categories=[])
    requests = [DummyHelpdeskRequest(raw_id="req_1")]

    with pytest.raises(LLMClassificationError):
        classifier.classify_batch(requests, catalog)                                                                        # type: ignore[arg-type]


# missing 'items' key raises LLMClassificationError
def test_classify_batch_missing_items_raises() -> None:
    response = DummyResponse(text=json.dumps({"foo": "bar"}))
    cfg = DummyLLMConfig()
    classifier = LLMClassifier(cfg)                                                                                         # type: ignore[arg-type]
    classifier._client = DummyClient(response)                                                                              # type: ignore[attr-defined]

    catalog = DummyCatalog(categories=[])
    requests = [DummyHelpdeskRequest(raw_id="req_1")]

    with pytest.raises(LLMClassificationError):
        classifier.classify_batch(requests, catalog)                                                                        # type: ignore[arg-type]