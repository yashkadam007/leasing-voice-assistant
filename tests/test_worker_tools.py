import asyncio
import inspect

from sqlalchemy import select

from leasing_voice_assistant.db.models import Prospect, ProspectInterest
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from leasing_voice_assistant.worker.call_context import build_call_context
from leasing_voice_assistant.worker.tools import build_livekit_tool_adapter


def test_adapter_preserves_missing_phone_capture_rejection() -> None:
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()

        state = build_call_context().to_call_state()
        tools = build_livekit_tool_adapter(session, state)
        tools.search_properties("Aurora Heights")

        result = tools.capture_prospect_interest(
            caller_name="Sam Rivera",
            confirmed_interest=True,
        )

        assert result["status"] == "rejected"
        assert "missing_phone" in result["reasons"]
        assert session.scalars(select(Prospect)).all() == []


def test_worker_capture_commits_interest_for_api_verification(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'worker-capture.db'}"
    engine = create_sqlite_engine(database_url)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()

        state = build_call_context(attributes={"sip.phoneNumber": "+14155551212"}).to_call_state()
        tools = build_livekit_tool_adapter(session, state)
        tools.search_properties("Aurora Heights")

        result = tools.capture_prospect_interest(
            caller_name="Sam Rivera",
            caller_email="sam@example.com",
            confirmed_interest=True,
        )

        assert result["status"] == "captured"

    with session_factory() as verification_session:
        prospect = verification_session.scalar(select(Prospect))
        interest = verification_session.scalar(select(ProspectInterest))

        assert prospect is not None
        assert prospect.phone_number == "+14155551212"
        assert prospect.name == "Sam Rivera"
        assert prospect.email == "sam@example.com"
        assert interest is not None
        assert interest.property_id == result["interest"]["property_id"]


def test_livekit_tools_are_awaitable_and_preserve_signature() -> None:
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()

        state = build_call_context().to_call_state()
        tools = build_livekit_tool_adapter(session, state)
        livekit_tools = tools.legacy_read_and_capture_tools()
        search_properties = livekit_tools[0]

        assert [tool.__name__ for tool in livekit_tools] == [
            "search_properties",
            "get_unit_details",
            "search_knowledge_base",
            "capture_prospect_interest",
        ]
        assert [set(inspect.signature(tool).parameters) for tool in livekit_tools] == [
            {"query", "limit"},
            {"unit_number"},
            {"query", "limit", "property_identifier"},
            {"caller_name", "caller_email", "confirmed_interest", "notes"},
        ]

        result = asyncio.run(search_properties(query="Aurora Heights"))

        assert result["status"] == "matched"


def test_hybrid_livekit_surface_exposes_only_capture() -> None:
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()
        tool = build_livekit_tool_adapter(
            session, build_call_context().to_call_state()
        ).capture_tool()

        assert tool.__name__ == "capture_prospect_interest"
        assert set(inspect.signature(tool).parameters) == {
            "caller_name",
            "caller_email",
            "confirmed_interest",
            "notes",
        }
