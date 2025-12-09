from __future__ import annotations
from typing import Mapping, Dict, List
import pytest
from app.application.classify_requests import classify_requests
from app.application.llm_classifier import LLMClassificationResult, LLMClassificationError
from app.domain.helpdesk import HelpdeskRequest
from app.domain.service_catalog import ServiceCatalog


# construct a valid HelpdeskRequest
def _make_request(raw_id: str) -> HelpdeskRequest:
    return HelpdeskRequest(
        raw_id=raw_id,
        short_description=f"test {raw_id}",
        raw_payload={},
    )

class FakeClassifier:
    def __init__(self, results_by_id: Dict[str, LLMClassificationResult], fail_on_call: int | None = None) -> None:
        self._results_by_id = results_by_id
        self._fail_on_call = fail_on_call
        self.calls: int = 0
        self.batches: List[list[HelpdeskRequest]] = []

    def classify_batch(self, requests: list[HelpdeskRequest], service_catalog: ServiceCatalog) -> Mapping[str, LLMClassificationResult]:
        self.calls += 1
        self.batches.append(requests)

        if self._fail_on_call is not None and self.calls == self._fail_on_call:
            raise LLMClassificationError("boom")

        return {
            r.raw_id: self._results_by_id[r.raw_id]
            for r in requests
            if r.raw_id in self._results_by_id
        }

# all requests classified, no errors
def test_classify_requests_with_llm_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # disable real sleeping
    monkeypatch.setattr(
        "app.application.classify_requests.time.sleep",
        lambda _seconds: None,
    )

    req1 = _make_request("r1")
    req2 = _make_request("r2")
    requests = [req1, req2]

    service_catalog = ServiceCatalog(categories=[])

    results = {
        "r1": LLMClassificationResult(
            request_category="Access",
            request_type="Password reset",
            sla_unit="hours",
            sla_value=4,
        ),
        "r2": LLMClassificationResult(
            request_category="Hardware",
            request_type="Laptop issue",
            sla_unit="days",
            sla_value=1,
        ),
    }

    classifier = FakeClassifier(results_by_id=results)

    classified = classify_requests(
        classifier=classifier,
        service_catalog=service_catalog,
        requests_=requests,
        batch_size=10,
        examples_to_log=3,
    )

    # same number of items and same order
    assert [r.raw_id for r in classified] == ["r1", "r2"]

    # fields updated from LLM result
    assert req1.request_category == "Access"
    assert req1.request_type == "Password reset"
    assert req1.sla_unit == "hours"
    assert req1.sla_value == 4

    assert req2.request_category == "Hardware"
    assert req2.request_type == "Laptop issue"
    assert req2.sla_unit == "days"
    assert req2.sla_value == 1

    # classifier was called once
    assert classifier.calls == 1


# batch failure – first batch ok, second batch fails, but all requests returned
def test_classify_requests_with_llm_batch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.application.classify_requests.time.sleep",
        lambda _seconds: None,
    )

    # three requests, batch_size=2 -> 2 batches
    req1 = _make_request("r1")
    req2 = _make_request("r2")
    req3 = _make_request("r3")
    requests = [req1, req2, req3]

    service_catalog = ServiceCatalog(categories=[])

    results = {
        "r1": LLMClassificationResult(
            request_category="Cat1",
            request_type="Type1",
            sla_unit="hours",
            sla_value=2,
        ),
        # r2 intentionally missing
        "r3": LLMClassificationResult(
            request_category="Cat3",
            request_type="Type3",
            sla_unit="days",
            sla_value=1,
        ),
    }

    # fail on second call (second batch)
    classifier = FakeClassifier(results_by_id=results, fail_on_call=2)

    classified = classify_requests(
        classifier=classifier,
        service_catalog=service_catalog,
        requests_=requests,
        batch_size=2,
        examples_to_log=3,
    )

    # all requests are still returned
    assert [r.raw_id for r in classified] == ["r1", "r2", "r3"]

    # first batch processed OK
    assert req1.request_category == "Cat1"
    # r2 had no result -> stays None
    assert req2.request_category is None

    # second batch failed completely -> no classification for r3
    assert req3.request_category is None