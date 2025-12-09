from __future__ import annotations
from dataclasses import dataclass
from app.application.missing_sla import missing_sla


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
class DummyHelpdeskRequest:
    raw_id: str
    request_category: str | None = None
    request_type: str | None = None
    sla_unit: str | None = None
    sla_value: int | None = None

# fills missing SLA when category+type match and SLA is None
def test_missing_sla_fills_when_missing_and_match() -> None:
    catalog = DummyCatalog(
        categories=[
            DummyCategory(
                name="Other/Uncategorized",
                requests=[
                    DummyRequestType("General Inquiry/Undefined", DummySLA("hours", 0)),
                ],
            )
        ]
    )

    req = DummyHelpdeskRequest(
        raw_id="req_1",
        request_category="Other/Uncategorized",
        request_type="General Inquiry/Undefined",
        sla_unit=None,
        sla_value=None,
    )

    missing_sla([req], catalog)                                                                                     # type: ignore[arg-type]

    assert req.sla_unit == "hours"
    assert req.sla_value == 0


# does not overwrite SLA when already present
def test_missing_sla_does_not_overwrite_existing_sla() -> None:
    catalog = DummyCatalog(
        categories=[
            DummyCategory(
                name="Access Management",
                requests=[
                    DummyRequestType("Reset forgotten password", DummySLA("hours", 4)),
                ],
            )
        ]
    )

    req = DummyHelpdeskRequest(
        raw_id="req_2",
        request_category="Access Management",
        request_type="Reset forgotten password",
        sla_unit="hours",
        sla_value=8,                                                                                                        # deliberately different from catalog
    )

    missing_sla([req], catalog)                                                                                     # type: ignore[arg-type]

    # value must stay as set by LLM
    assert req.sla_unit == "hours"
    assert req.sla_value == 8


# does nothing when category/type pair is not in catalog
def test_missing_sla_ignores_unknown_category_type() -> None:
    catalog = DummyCatalog(categories=[])

    req = DummyHelpdeskRequest(
        raw_id="req_3",
        request_category="Nonexistent Category",
        request_type="Nonexistent Type",
        sla_unit=None,
        sla_value=None,
    )

    missing_sla([req], catalog)                                                                                     # type: ignore[arg-type]

    assert req.sla_unit is None
    assert req.sla_value is None


# does nothing when category or type is missing on request
def test_missing_sla_skips_when_category_or_type_missing() -> None:
    catalog = DummyCatalog(
        categories=[
            DummyCategory(
                name="Access Management",
                requests=[
                    DummyRequestType("Reset forgotten password", DummySLA("hours", 4)),
                ],
            )
        ]
    )

    req_missing_category = DummyHelpdeskRequest(
        raw_id="req_4",
        request_category=None,
        request_type="Reset forgotten password",
        sla_unit=None,
        sla_value=None,
    )

    req_missing_type = DummyHelpdeskRequest(
        raw_id="req_5",
        request_category="Access Management",
        request_type=None,
        sla_unit=None,
        sla_value=None,
    )

    missing_sla([req_missing_category, req_missing_type], catalog)                                                  # type: ignore[arg-type]

    assert req_missing_category.sla_unit is None
    assert req_missing_category.sla_value is None
    assert req_missing_type.sla_unit is None
    assert req_missing_type.sla_value is None