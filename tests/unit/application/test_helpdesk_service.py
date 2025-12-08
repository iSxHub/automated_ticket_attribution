from unittest.mock import Mock
from app.application.helpdesk_services import HelpdeskService
from app.domain.models import HelpdeskRequest
from app.infrastructure.helpdesk_client import HelpdeskClient


def test_helpdesk_service_delegates_to_client() -> None:
    mock_client = Mock(spec=HelpdeskClient)
    expected = [HelpdeskRequest(raw_id="x", short_description="y", raw_payload={})]
    mock_client.fetch_requests.return_value = expected

    service = HelpdeskService(mock_client)

    result = service.load_requests()

    assert result == expected
    mock_client.fetch_requests.assert_called_once()