import asyncio

import pytest

from leasing_voice_assistant.agent.grounding.builder import GroundedTurnContextBuilder
from leasing_voice_assistant.agent.grounding.models import CallStateSnapshot, GroundingCancelled
from leasing_voice_assistant.agent.grounding.parser import GroundingQueryParser
from leasing_voice_assistant.agent.state import CallState, ResolvedTarget
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


@pytest.fixture()
def grounding_builder():
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()
        yield GroundedTurnContextBuilder(session)


def test_parser_extracts_supported_compound_comparison() -> None:
    query = GroundingQueryParser().parse(
        "Compare units eight a and four b at Aurora Heights. Are pets allowed?",
        property_names=["Aurora Heights", "Pine Garden Flats"],
        locations=["San Francisco", "Oakland"],
    )

    assert query.property_terms == ("Aurora Heights",)
    assert query.unit_numbers == ("8A", "4B")
    assert query.policy_topics == ("pets",)
    assert query.comparison_requested is True
    assert query.compound_question is True


def test_parser_extracts_bare_numeric_unit_comparison() -> None:
    query = GroundingQueryParser().parse("Compare 11 and 24 at Pine Garden Flats")
    spoken = GroundingQueryParser().parse(
        "Compare unit eleven and unit twenty four at Pine Garden Flats"
    )

    assert query.unit_numbers == ("11", "24")
    assert query.comparison_requested is True
    assert spoken.unit_numbers == ("11", "24")


def test_parser_extracts_structured_bedroom_price_and_location() -> None:
    query = GroundingQueryParser().parse(
        "Do you have a two-bedroom in Oakland under $3,500?",
        property_names=["Aurora Heights", "Pine Garden Flats"],
        locations=["San Francisco", "Oakland"],
    )

    assert query.location_terms == ("Oakland",)
    assert query.bedroom_count == 2
    assert query.maximum_rent_cents == 350000
    assert query.availability_requested is True


def test_parser_marks_indirect_constraints_for_clarification() -> None:
    query = GroundingQueryParser().parse("What is the cheapest place close to downtown?")

    assert set(query.unsupported_constraints) == {"subjective_price", "relative_location"}


def test_builder_returns_exact_units_and_policy_sources(grounding_builder) -> None:
    outcome = asyncio.run(
        grounding_builder.build(
            "Compare units 8A and 4B at Aurora Heights and tell me the pet policy",
            CallStateSnapshot.from_state(CallState()),
        )
    )

    unit_results = [
        item for item in outcome.payload["results"] if item["source_type"] == "unit_database"
    ]
    assert [item["unit"]["unit_number"] for item in unit_results] == ["8A", "4B"]
    assert any(item["source_type"] == "knowledge_base" for item in outcome.payload["results"])
    assert len(outcome.serialized().encode()) <= 8 * 1024


def test_builder_uses_current_target_for_short_follow_up(grounding_builder) -> None:
    state = CallState(current_target=ResolvedTarget("unit", 2, "Aurora Heights unit 8A", 1.0))

    outcome = asyncio.run(
        grounding_builder.build("What is the rent?", CallStateSnapshot.from_state(state))
    )

    current = outcome.payload["results"][0]
    assert current["source_type"] == "current_unit"
    assert current["facts"]["rent_cents"] == 482500
    assert outcome.should_apply_transition is False


def test_builder_does_not_clear_target_for_unrelated_no_match(grounding_builder) -> None:
    state = CallState(current_target=ResolvedTarget("property", 1, "Aurora Heights", 0.98))

    outcome = asyncio.run(
        grounding_builder.build("How is your day?", CallStateSnapshot.from_state(state))
    )

    assert outcome.should_apply_transition is False
    assert outcome.target_transition is None


def test_builder_cooperatively_cancels_before_state_transition(grounding_builder) -> None:
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 2

    with pytest.raises(GroundingCancelled):
        asyncio.run(
            grounding_builder.build(
                "Tell me about Aurora Heights",
                CallStateSnapshot.from_state(CallState()),
                is_cancelled=cancelled,
            )
        )


def test_builder_returns_unavailable_when_deadline_expires() -> None:
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()
        builder = GroundedTurnContextBuilder(session, deadline_ms=1)

        original = builder.properties.list_property_identifiers

        def slow_catalog():
            import time

            result = original()
            time.sleep(0.005)
            return result

        builder.properties.list_property_identifiers = slow_catalog
        outcome = asyncio.run(
            builder.build("Aurora Heights", CallStateSnapshot.from_state(CallState()))
        )

    assert outcome.payload["statuses"] == ["unavailable"]
    assert outcome.deadline_exceeded is True
