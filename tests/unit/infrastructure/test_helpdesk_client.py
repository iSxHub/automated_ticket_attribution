from typing import Any, Dict, List
from unittest.mock import Mock
import pytest
from app.config import HelpdeskAPIConfig
from app.domain.helpdesk import HelpdeskRequest
from app.infrastructure.helpdesk_client import HelpdeskClient, HelpdeskAPIError


def _make_client_with_mock_session(json_payload: Any) -> HelpdeskClient:
    config = HelpdeskAPIConfig(
        url="https://example.com/helpdesk",
        api_key="dummy-key",
        api_secret="dummy-secret",
        timeout_seconds=5.0,
    )

    client = HelpdeskClient(config)

    mock_session = Mock()
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json = Mock(return_value=json_payload)

    mock_session.post = Mock(return_value=mock_response)

    client._session = mock_session                                                                                          # type: ignore[attr-defined]
    return client

def test_fetch_requests_happy_path() -> None:
    sample_data: Dict[str, Any] = {
        "response_code": 200,
        "data": {
            "requests": [
                {
                    "id": "req_101",
                    "short_description": "Forgot my Okta password",
                    "long_description": "dummy",
                    "requester_email": "j.doe@company.com",
                    "request_category": "",
                    "request_type": "",
                    "sla": {"unit": "", "value": 0},
                }
            ]
        },
    }

    client = _make_client_with_mock_session(sample_data)

    result: List[HelpdeskRequest] = client.fetch_requests()

    assert len(result) == 1
    req = result[0]
    assert req.raw_id == "req_101"
    assert req.short_description == "Forgot my Okta password"
    assert req.raw_payload["requester_email"] == "j.doe@company.com"

def test_fetch_requests_unexpected_shape_raises() -> None:
    bad_data = {
        "response_code": 200,
        "data": {"not_requests": []},
    }

    client = _make_client_with_mock_session(bad_data)

    with pytest.raises(HelpdeskAPIError):
        _ = client.fetch_requests()

def test_fetch_raw_returns_json() -> None:
    sample_data = {"foo": "bar"}
    client = _make_client_with_mock_session(sample_data)

    raw = client.fetch_raw()
    assert raw == sample_data

def test_http_error_is_wrapped_in_helpdesk_api_error() -> None:
    config = HelpdeskAPIConfig(
        url="https://example.com/helpdesk",
        api_key="dummy-key",
        api_secret="dummy-secret",
        timeout_seconds=5.0,
    )

    client = HelpdeskClient(config)

    mock_session = Mock()
    mock_response = Mock()
    from requests import HTTPError

    mock_response.raise_for_status.side_effect = HTTPError("404 not found")
    mock_session.post.return_value = mock_response

    client._session = mock_session                                                                                          # type: ignore[attr-defined]

    with pytest.raises(HelpdeskAPIError):
        _ = client.fetch_requests()

def test_json_error_is_wrapped_in_helpdesk_api_error() -> None:
    config = HelpdeskAPIConfig(
        url="https://example.com/helpdesk",
        api_key="dummy-key",
        api_secret="dummy-secret",
        timeout_seconds=5.0,
    )

    client = HelpdeskClient(config)

    mock_session = Mock()
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.side_effect = ValueError("invalid json")

    mock_session.post.return_value = mock_response
    client._session = mock_session                                                                                          # type: ignore[attr-defined]

    with pytest.raises(HelpdeskAPIError):
        _ = client.fetch_requests()