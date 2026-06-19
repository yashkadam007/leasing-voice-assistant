from decimal import Decimal

import pytest

from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from leasing_voice_assistant.repositories.properties import (
    PropertiesRepository,
    normalize_unit_number,
)
from leasing_voice_assistant.repositories.prospects import (
    ProspectsRepository,
    normalize_phone_number,
)


@pytest.fixture()
def session():
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as db_session:
        seed_database(db_session)
        db_session.commit()
        yield db_session


def test_seed_data_supports_exact_unit_fact_lookup(session) -> None:
    properties = PropertiesRepository(session)

    results = properties.search("Aurora Heights")
    aurora = results[0].property
    unit = properties.get_unit_by_number(aurora.id, "8A")

    assert unit is not None
    assert unit.property.name == "Aurora Heights"
    assert unit.bedroom_count == 2
    assert unit.bathroom_count == Decimal("2.0")
    assert unit.rent_cents == 482500
    assert unit.square_feet == 1040
    assert unit.status == "available"
    assert unit.view == "bay"


def test_property_search_matches_unit_caller_text(session) -> None:
    properties = PropertiesRepository(session)

    results = properties.search("bay")

    assert [result.property.name for result in results] == ["Aurora Heights"]
    assert [unit.unit_number for unit in results[0].matched_units] == ["8A"]


def test_unit_number_normalization_handles_compound_spoken_number() -> None:
    assert normalize_unit_number("unit twenty four") == "24"


def test_prospect_upsert_dedupes_by_normalized_phone(session) -> None:
    prospects = ProspectsRepository(session)

    first = prospects.upsert_by_phone("(415) 555-1212", name="Sam Rivera")
    second = prospects.upsert_by_phone("+1 415 555 1212", email="sam@example.com")

    assert first.id == second.id
    assert second.phone_number == "+14155551212"
    assert second.name == "Sam Rivera"
    assert second.email == "sam@example.com"


def test_create_interest_is_idempotent_for_same_property(session) -> None:
    properties = PropertiesRepository(session)
    prospects = ProspectsRepository(session)
    aurora = properties.search("Aurora Heights")[0].property
    prospect = prospects.upsert_by_phone("415-555-3434", name="Lee Chen")

    first_interest, first_created = prospects.create_interest(
        prospect_id=prospect.id,
        property_id=aurora.id,
    )
    second_interest, second_created = prospects.create_interest(
        prospect_id=prospect.id,
        property_id=aurora.id,
    )

    assert first_created is True
    assert second_created is False
    assert first_interest.id == second_interest.id


def test_create_interest_is_idempotent_for_same_unit(session) -> None:
    properties = PropertiesRepository(session)
    prospects = ProspectsRepository(session)
    aurora = properties.search("Aurora Heights")[0].property
    unit = properties.get_unit_by_number(aurora.id, "4B")
    prospect = prospects.upsert_by_phone("510-555-7777")

    assert unit is not None
    first_interest, first_created = prospects.create_interest(
        prospect_id=prospect.id,
        unit_id=unit.id,
    )
    second_interest, second_created = prospects.create_interest(
        prospect_id=prospect.id,
        unit_id=unit.id,
    )

    assert first_created is True
    assert second_created is False
    assert first_interest.id == second_interest.id


def test_interest_requires_exactly_one_target(session) -> None:
    prospects = ProspectsRepository(session)
    prospect = prospects.upsert_by_phone("415-555-9999")

    with pytest.raises(ValueError, match="exactly one"):
        prospects.create_interest(prospect_id=prospect.id)


def test_phone_normalization_rejects_short_values() -> None:
    with pytest.raises(ValueError, match="at least seven digits"):
        normalize_phone_number("555")
