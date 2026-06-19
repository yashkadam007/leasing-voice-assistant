import pytest

from leasing_voice_assistant.agent.resolution import (
    property_candidate_from_result,
    property_facts,
    resolved_target_from_candidate,
    score_property_result,
    serialize_resolved_target,
    unit_facts,
)
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from leasing_voice_assistant.repositories.properties import PropertiesRepository


@pytest.fixture()
def properties():
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()
        yield PropertiesRepository(session)


def test_property_and_unit_facts_preserve_agent_payload_shapes(properties) -> None:
    property_ = properties.get_property(1)
    unit = properties.get_unit(2)

    assert property_ is not None
    assert unit is not None
    assert property_facts(property_) == {
        "id": 1,
        "name": "Aurora Heights",
        "address": "1250 Market Street",
        "city": "San Francisco",
        "state": "CA",
        "phone": "+14155550140",
        "description": "Transit-friendly apartments with rooftop lounge and in-building fitness.",
        "pet_policy": (
            "Cats and dogs are welcome, up to two pets per home, with breed restrictions."
        ),
        "parking_policy": "Garage parking is available for $275 per month.",
        "application_fee_cents": 5500,
        "security_deposit_cents": 75000,
        "lease_terms": "9, 12, and 15 month lease terms",
    }
    assert unit_facts(unit) == {
        "id": 2,
        "unit_number": "8A",
        "bedroom_count": 2,
        "bathroom_count": 2.0,
        "rent_cents": 482500,
        "square_feet": 1040,
        "availability_date": "2026-08-01",
        "status": "available",
        "floor": 8,
        "view": "bay",
        "notes": "Two-bedroom home with balcony and bay view.",
        "property": property_facts(property_),
    }


def test_property_candidate_scores_exact_unit_and_resolves_target(properties) -> None:
    result = properties.search("unit eight a")[0]

    assert score_property_result(result, query="unit eight a", total_results=1) == (
        "unit_exact",
        0.98,
    )

    candidate = property_candidate_from_result(result, query="unit eight a", total_results=1)
    target = resolved_target_from_candidate(candidate, ambiguity_resolved=True)

    assert candidate["target_type"] == "unit"
    assert candidate["label"] == "Aurora Heights unit 8A"
    assert [unit["unit_number"] for unit in candidate["available_units"]] == ["4B", "8A"]
    assert serialize_resolved_target(target) == {
        "target_type": "unit",
        "target_id": 2,
        "label": "Aurora Heights unit 8A",
        "confidence": 0.98,
        "ambiguous": False,
        "ambiguity_resolved": True,
    }


def test_property_candidate_marks_lexical_resolution_ambiguous(properties) -> None:
    results = properties.search("available")
    candidate = property_candidate_from_result(
        results[0], query="available", total_results=len(results)
    )
    candidate["ambiguous"] = True

    target = resolved_target_from_candidate(candidate, ambiguity_resolved=False)

    assert candidate["match_type"] == "lexical"
    assert candidate["confidence"] == 0.62
    assert target.ambiguous is True
    assert target.ambiguity_resolved is False
    assert serialize_resolved_target(None) is None
