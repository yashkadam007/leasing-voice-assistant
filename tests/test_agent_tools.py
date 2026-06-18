import pytest
from sqlalchemy import select

from leasing_voice_assistant.agent import CallState, LeasingAgentTools
from leasing_voice_assistant.agent.state import ResolvedTarget
from leasing_voice_assistant.db.models import Prospect, ProspectInterest
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
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


def test_search_properties_resolves_single_property_candidate(session) -> None:
    state = CallState(caller_phone_number="415-555-1212")
    tools = LeasingAgentTools(session, state)

    result = tools.search_properties("Aurora Heights")

    assert result["status"] == "matched"
    assert result["ambiguous"] is False
    assert result["candidates"][0]["match_type"] == "property_exact"
    assert state.current_target is not None
    assert state.current_target.label == "Aurora Heights"
    assert state.current_target.confidence >= 0.8


def test_search_properties_marks_multiple_candidates_ambiguous(session) -> None:
    state = CallState(caller_phone_number="415-555-1212")
    tools = LeasingAgentTools(session, state)

    result = tools.search_properties("available")

    assert result["status"] == "ambiguous"
    assert result["ambiguous"] is True
    assert len(result["candidates"]) == 2
    assert all(candidate["ambiguous"] is True for candidate in result["candidates"])
    assert state.current_target is not None
    assert state.current_target.ambiguous is True
    assert state.current_target.ambiguity_resolved is False


def test_get_unit_details_returns_authoritative_unit_facts(session) -> None:
    state = CallState()
    tools = LeasingAgentTools(session, state)
    search = tools.search_properties("8A")
    unit_id = search["candidates"][0]["target_id"]

    result = tools.get_unit_details(unit_id)

    assert result["status"] == "found"
    assert result["unit"]["unit_number"] == "8A"
    assert result["unit"]["property"]["name"] == "Aurora Heights"
    assert result["unit"]["rent_cents"] == 482500
    assert state.current_target is not None
    assert state.current_target.target_type == "unit"


def test_search_knowledge_base_returns_source_backed_results(session) -> None:
    tools = LeasingAgentTools(session, CallState())

    result = tools.search_knowledge_base("application fee")

    assert result["status"] == "matched"
    assert result["results"]
    assert {"path", "document_title", "section", "chunk_id", "property_identifier"} == set(
        result["results"][0]["source"]
    )


def test_capture_rejects_missing_phone_without_writing(session) -> None:
    state = CallState(caller_name="Sam Rivera")
    state.current_target = ResolvedTarget(
        target_type="property",
        target_id=1,
        label="Aurora Heights",
        confidence=0.98,
    )
    tools = LeasingAgentTools(session, state)

    result = tools.capture_prospect_interest(confirmed_interest=True)

    assert result["status"] == "rejected"
    assert "missing_phone" in result["reasons"]
    assert session.scalars(select(Prospect)).all() == []


def test_capture_rejects_missing_name_without_writing(session) -> None:
    state = CallState(caller_phone_number="415-555-1212")
    tools = LeasingAgentTools(session, state)
    tools.search_properties("Aurora Heights")

    result = tools.capture_prospect_interest(confirmed_interest=True)

    assert result["status"] == "rejected"
    assert "missing_name" in result["reasons"]
    assert session.scalars(select(Prospect)).all() == []


def test_capture_rejects_ambiguous_property_without_writing(session) -> None:
    state = CallState(caller_phone_number="415-555-1212", caller_name="Sam Rivera")
    tools = LeasingAgentTools(session, state)
    tools.search_properties("available")

    result = tools.capture_prospect_interest(confirmed_interest=True)

    assert result["status"] == "rejected"
    assert "ambiguous_property" in result["reasons"]
    assert session.scalars(select(Prospect)).all() == []


def test_capture_rejects_low_confidence_without_writing(session) -> None:
    state = CallState(
        caller_phone_number="415-555-1212",
        caller_name="Sam Rivera",
        current_target=ResolvedTarget(
            target_type="property",
            target_id=1,
            label="Aurora Heights",
            confidence=0.5,
        ),
        confirmed_interest=True,
    )
    tools = LeasingAgentTools(session, state)

    result = tools.capture_prospect_interest()

    assert result["status"] == "rejected"
    assert "low_confidence" in result["reasons"]
    assert session.scalars(select(Prospect)).all() == []


def test_capture_rejects_missing_confirmation_without_writing(session) -> None:
    state = CallState(caller_phone_number="415-555-1212", caller_name="Sam Rivera")
    tools = LeasingAgentTools(session, state)
    tools.search_properties("Aurora Heights")

    result = tools.capture_prospect_interest()

    assert result["status"] == "rejected"
    assert "needs_confirmation" in result["reasons"]
    assert session.scalars(select(Prospect)).all() == []


def test_capture_creates_idempotent_prospect_interest_when_safe(session) -> None:
    state = CallState(caller_phone_number="(415) 555-1212")
    tools = LeasingAgentTools(session, state)
    tools.search_properties("Aurora Heights")

    first = tools.capture_prospect_interest(
        caller_name="Sam Rivera",
        caller_email="sam@example.com",
        confirmed_interest=True,
        notes="Caller asked for a tour.",
    )
    second = tools.capture_prospect_interest(confirmed_interest=True)

    interests = session.scalars(select(ProspectInterest)).all()
    prospects = session.scalars(select(Prospect)).all()

    assert first["status"] == "captured"
    assert first["created"] is True
    assert second["status"] == "captured"
    assert second["created"] is False
    assert len(prospects) == 1
    assert prospects[0].phone_number == "+14155551212"
    assert prospects[0].name == "Sam Rivera"
    assert prospects[0].email == "sam@example.com"
    assert len(interests) == 1
