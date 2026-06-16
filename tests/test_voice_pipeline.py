from pathlib import Path

from leasing_voice_assistant.answer_orchestration import AnswerOrchestrator
from leasing_voice_assistant.conversation_session import (
    ConversationSessionService,
    ConversationSessionState,
)
from leasing_voice_assistant.database_tools import DatabaseQueryTools
from leasing_voice_assistant.fakes import (
    FakeModelProvider,
    FakeSpeechToTextProvider,
    FakeTextToSpeechProvider,
)
from leasing_voice_assistant.interfaces import Transcript
from leasing_voice_assistant.knowledge_base import MarkdownKnowledgeRetriever
from leasing_voice_assistant.persistence import (
    SQLitePropertyRepository,
    SQLiteProspectRepository,
    initialize_database,
)
from leasing_voice_assistant.prospect_capture import ProspectCaptureService
from leasing_voice_assistant.voice_pipeline import AudioInput, VoicePipeline, VoiceTurnRequest

KB_DIR = Path("data/kb")


def build_pipeline(
    tmp_path: Path,
    *,
    transcript: Transcript | None = None,
    model_text: str = "For Lakeview Flats unit 2B, rent is $2,450 per month.",
    stt_fail: bool = False,
    model_fail: bool = False,
    tts_fail: bool = False,
) -> VoicePipeline:
    connection = initialize_database(tmp_path / "voice.sqlite3")
    database_tools = DatabaseQueryTools(SQLitePropertyRepository(connection))
    session_service = ConversationSessionService(
        answer_orchestrator=AnswerOrchestrator(
            database_tools=database_tools,
            knowledge_retriever=MarkdownKnowledgeRetriever.from_directory(KB_DIR),
        ),
        prospect_capture_service=ProspectCaptureService(
            prospect_repository=SQLiteProspectRepository(connection)
        ),
        source="voice_pipeline",
    )
    return VoicePipeline(
        speech_to_text=FakeSpeechToTextProvider(transcript, fail=stt_fail),
        model=FakeModelProvider(model_text, fail=model_fail),
        text_to_speech=FakeTextToSpeechProvider(fail=tts_fail),
        session_service=session_service,
    )


def audio_request(
    *,
    session_id: str = "session-1",
    state: ConversationSessionState | None = None,
    caller_phone: str | None = None,
) -> VoiceTurnRequest:
    return VoiceTurnRequest(
        session_id=session_id,
        audio=AudioInput(audio=b"fake caller audio", content_type="audio/wav"),
        state=state,
        caller_phone=caller_phone,
        include_debug_trace=True,
    )


def test_voice_pipeline_transcribes_answers_with_grounded_model_text_and_synthesizes(
    tmp_path: Path,
) -> None:
    pipeline = build_pipeline(
        tmp_path,
        transcript=Transcript(
            text="How much is the lake-facing unit at Lakeview Flats?",
            confidence=0.94,
        ),
    )

    result = pipeline.handle_turn(audio_request())

    assert result.degradation == "none"
    assert result.transcript.confidence == 0.94
    assert result.assistant_text == "For Lakeview Flats unit 2B, rent is $2,450 per month."
    assert result.speech is not None
    assert (
        result.speech.audio == b"fake audio: For Lakeview Flats unit 2B, rent is $2,450 per month."
    )
    assert result.debug is not None
    assert result.debug.session_result is not None
    assert result.debug.session_result.answer.route == "database"
    assert result.state.turn_number == 1


def test_voice_pipeline_preserves_caller_metadata_and_low_confidence_write_gate(
    tmp_path: Path,
) -> None:
    pipeline = build_pipeline(
        tmp_path,
        transcript=Transcript(
            text="How much is the lake-facing unit at Lakeview Flats?",
            confidence=0.95,
        ),
    )
    first = pipeline.handle_turn(audio_request())

    capture_pipeline = build_pipeline(
        tmp_path,
        transcript=Transcript(
            text="My name is Avery Lee and I am interested in this.",
            confidence=0.42,
        ),
        model_text=(
            "Just to confirm, should I have the leasing team contact Avery Lee "
            "at 555-123-4567 about the selected unit?"
        ),
    )
    second = capture_pipeline.handle_turn(
        audio_request(state=first.state, caller_phone="555-123-4567")
    )

    assert second.debug is not None
    assert second.debug.session_result is not None
    assert second.debug.session_result.capture is not None
    assert second.debug.session_result.capture.outcome == "needs_confirmation"
    assert second.debug.session_result.capture.reason == "low_transcript_confidence"
    assert second.debug.session_result.capture.interest is None
    assert "Just to confirm" in second.assistant_text


def test_voice_pipeline_rejects_unsupported_model_facts_and_uses_safe_reply(
    tmp_path: Path,
) -> None:
    pipeline = build_pipeline(
        tmp_path,
        transcript=Transcript(
            text="How much is the lake-facing unit at Lakeview Flats?",
            confidence=0.91,
        ),
        model_text="Great news, that unit is $9,999 and move-in is guaranteed today.",
    )

    result = pipeline.handle_turn(audio_request())

    assert result.degradation == "model_rejected"
    assert (
        result.assistant_text != "Great news, that unit is $9,999 and move-in is guaranteed today."
    )
    assert "$2,450 per month" in result.assistant_text
    assert result.debug is not None
    assert result.debug.grounding_reason == "model_introduced_unsupported_number"


def test_voice_pipeline_stt_failure_returns_caller_safe_fallback(tmp_path: Path) -> None:
    pipeline = build_pipeline(tmp_path, stt_fail=True)

    result = pipeline.handle_turn(audio_request())

    assert result.degradation == "stt_failed"
    assert result.transcript.text == ""
    assert result.assistant_text == "I had trouble hearing that. Could you please repeat it?"
    assert result.speech is None
    assert result.state.turn_number == 0


def test_voice_pipeline_model_failure_falls_back_to_safe_session_reply(tmp_path: Path) -> None:
    pipeline = build_pipeline(
        tmp_path,
        transcript=Transcript(
            text="How much is the lake-facing unit at Lakeview Flats?",
            confidence=0.96,
        ),
        model_fail=True,
    )

    result = pipeline.handle_turn(audio_request())

    assert result.degradation == "model_failed"
    assert "$2,450 per month" in result.assistant_text
    assert result.speech is not None
    assert result.debug is not None
    assert result.debug.model_error == "fake model failure"


def test_voice_pipeline_tts_failure_returns_text_and_degraded_result(tmp_path: Path) -> None:
    pipeline = build_pipeline(
        tmp_path,
        transcript=Transcript(
            text="How much is the lake-facing unit at Lakeview Flats?",
            confidence=0.96,
        ),
        tts_fail=True,
    )

    result = pipeline.handle_turn(audio_request())

    assert result.degradation == "tts_failed"
    assert result.assistant_text == "For Lakeview Flats unit 2B, rent is $2,450 per month."
    assert result.speech is None
    assert result.debug is not None
    assert result.debug.tts_error == "fake TTS failure"
