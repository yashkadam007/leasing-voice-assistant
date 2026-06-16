from pathlib import Path

from leasing_voice_assistant.answer_orchestration import AnswerOrchestrator
from leasing_voice_assistant.conversation_session import (
    ConversationSessionService,
    ConversationTurnRequest,
)
from leasing_voice_assistant.database_tools import DatabaseQueryTools
from leasing_voice_assistant.knowledge_base import MarkdownKnowledgeRetriever
from leasing_voice_assistant.persistence import (
    SQLitePropertyRepository,
    SQLiteProspectRepository,
    initialize_database,
)
from leasing_voice_assistant.prospect_capture import ProspectCaptureService
from leasing_voice_assistant.text_harness import build_text_harness

KB_DIR = Path("data/kb")


def create_session_service(tmp_path: Path) -> ConversationSessionService:
    connection = initialize_database(tmp_path / "conversation.sqlite3")
    database_tools = DatabaseQueryTools(SQLitePropertyRepository(connection))
    return ConversationSessionService(
        answer_orchestrator=AnswerOrchestrator(
            database_tools=database_tools,
            knowledge_retriever=MarkdownKnowledgeRetriever.from_directory(KB_DIR),
        ),
        prospect_capture_service=ProspectCaptureService(
            prospect_repository=SQLiteProspectRepository(connection)
        ),
    )


def test_multi_turn_answer_context_is_preserved(tmp_path: Path) -> None:
    service = create_session_service(tmp_path)

    first = service.handle_turn(
        ConversationTurnRequest(user_text="Tell me about Lakeview Flats", include_debug_trace=True)
    )
    second = service.handle_turn(
        ConversationTurnRequest(
            user_text="How much is the lake-facing one?",
            state=first.state,
            include_debug_trace=True,
        )
    )

    assert second.answer.route == "database"
    assert second.answer.resolution.unit_id == "unit-lakeview-2b"
    assert "$2,450 per month" in second.assistant_text
    assert second.state.turn_number == 2
    assert len(second.state.transcript) == 4
    assert second.debug_trace is not None
    assert second.debug_trace.property_id == "property-lakeview-flats"
    assert second.debug_trace.database_evidence_count >= 1


def test_complete_prospect_capture_flow_writes_interest(tmp_path: Path) -> None:
    service = create_session_service(tmp_path)

    first = service.handle_turn(
        ConversationTurnRequest(user_text="How much is the lake-facing unit at Lakeview Flats?")
    )
    second = service.handle_turn(
        ConversationTurnRequest(
            user_text=(
                "My name is Avery Lee, my phone is 555-123-4567, and I am interested in this."
            ),
            state=first.state,
        )
    )

    assert second.capture is not None
    assert second.capture.outcome == "written"
    assert second.capture.interest is not None
    assert second.capture.interest.unit_id == "unit-lakeview-2b"
    assert "recorded your interest in Lakeview Flats unit 2B" in second.assistant_text


def test_confirmation_required_flow_uses_pending_capture_state(tmp_path: Path) -> None:
    service = create_session_service(tmp_path)

    first = service.handle_turn(ConversationTurnRequest(user_text="Tell me about Lakeview Flats"))
    second = service.handle_turn(
        ConversationTurnRequest(
            user_text="My name is Avery Lee and my phone is 555-123-4567.",
            state=first.state,
        )
    )
    third = service.handle_turn(ConversationTurnRequest(user_text="yes", state=second.state))

    assert second.capture is not None
    assert second.capture.outcome == "needs_confirmation"
    assert "Just to confirm" in second.assistant_text
    assert third.capture is not None
    assert third.capture.outcome == "written"
    assert "recorded your interest in Lakeview Flats" in third.assistant_text


def test_ambiguous_property_flow_keeps_write_blocked(tmp_path: Path) -> None:
    service = create_session_service(tmp_path)

    result = service.handle_turn(
        ConversationTurnRequest(
            user_text=(
                "My name is Avery Lee, my phone is 555-123-4567, and I am interested in "
                "Lakeview Flats or Cedar Park Townhomes."
            ),
            include_debug_trace=True,
        )
    )

    assert result.answer.route == "clarification"
    assert result.capture is not None
    assert result.capture.outcome == "blocked"
    assert result.capture.reason == "target_not_write_ready"
    assert result.assistant_text == "Which property or unit should I record your interest in?"
    assert result.debug_trace is not None
    assert result.debug_trace.capture_processed is True


def test_build_text_harness_uses_real_repositories(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "harness.sqlite3")
    service = build_text_harness(connection)

    result = service.handle_turn(
        ConversationTurnRequest(user_text="What is the rent at Cedar Park Townhomes?")
    )

    assert result.answer.route == "database"
    assert "$3,100 per month" in result.assistant_text
