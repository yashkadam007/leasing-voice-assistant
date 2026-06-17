import base64
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from leasing_voice_assistant.answer_orchestration import AnswerOrchestrator
from leasing_voice_assistant.app import _twilio_signature, create_app
from leasing_voice_assistant.config import Settings
from leasing_voice_assistant.conversation_session import ConversationSessionService
from leasing_voice_assistant.database_tools import DatabaseQueryTools
from leasing_voice_assistant.fakes import (
    FakeModelProvider,
    FakeSpeechToTextProvider,
    FakeStreamingSpeechToTextProvider,
    FakeTextToSpeechProvider,
)
from leasing_voice_assistant.interfaces import StreamingTranscriptEvent, Transcript
from leasing_voice_assistant.knowledge_base import MarkdownKnowledgeRetriever
from leasing_voice_assistant.persistence import (
    SQLitePropertyRepository,
    SQLiteProspectRepository,
    initialize_database,
)
from leasing_voice_assistant.prospect_capture import ProspectCaptureService
from leasing_voice_assistant.twilio_transport import (
    TWILIO_MULAW_CONTENT_TYPE,
    TwilioCallManager,
    TwilioVoiceWebhook,
    build_twilio_voice_twiml,
)
from leasing_voice_assistant.voice_pipeline import VoicePipeline

KB_DIR = Path("data/kb")


def build_settings(**values: Any) -> Settings:
    return Settings(**{"_env_file": None, **values})


def build_manager(
    tmp_path: Path,
    *,
    transcript: str = "How much is the lake-facing unit at Lakeview Flats?",
    tts_content_type: str = "audio/x-mulaw",
    streaming_events: tuple[tuple[StreamingTranscriptEvent, ...], ...] | None = None,
    streaming_fail_on_audio: bool = False,
    streaming_enabled: bool = True,
) -> TwilioCallManager:
    connection = initialize_database(tmp_path / "twilio.sqlite3")
    session_service = ConversationSessionService(
        answer_orchestrator=AnswerOrchestrator(
            database_tools=DatabaseQueryTools(SQLitePropertyRepository(connection)),
            knowledge_retriever=MarkdownKnowledgeRetriever.from_directory(KB_DIR),
        ),
        prospect_capture_service=ProspectCaptureService(SQLiteProspectRepository(connection)),
        source="twilio_call",
    )
    pipeline = VoicePipeline(
        speech_to_text=FakeSpeechToTextProvider(Transcript(text=transcript, confidence=0.93)),
        model=FakeModelProvider("For Lakeview Flats unit 2B, rent is $2,450 per month."),
        text_to_speech=FakeTextToSpeechProvider(content_type=tts_content_type),
        session_service=session_service,
    )
    streaming_provider = (
        FakeStreamingSpeechToTextProvider(
            streaming_events
            or (
                (
                    StreamingTranscriptEvent(
                        type="final_transcript",
                        transcript=Transcript(text=transcript, confidence=0.93),
                    ),
                    StreamingTranscriptEvent(type="utterance_complete", event_id="turn-1"),
                ),
            ),
            fail_on_audio=streaming_fail_on_audio,
        )
        if streaming_enabled
        else None
    )
    return TwilioCallManager(
        voice_pipeline=pipeline,
        streaming_speech_to_text=streaming_provider,
    )


def media_message(stream_sid: str, payload: bytes, sequence: int = 2) -> dict[str, object]:
    return {
        "event": "media",
        "streamSid": stream_sid,
        "sequenceNumber": str(sequence),
        "media": {"payload": base64.b64encode(payload).decode("ascii")},
    }


def test_twilio_voice_twiml_connects_media_stream_with_caller_metadata() -> None:
    twiml = build_twilio_voice_twiml(
        TwilioVoiceWebhook(
            call_sid="CA123",
            caller_phone="+15551234567",
            public_base_url="https://example.ngrok.app",
        )
    )

    assert "<Response><Say>Thanks for calling." in twiml
    assert '<Stream url="wss://example.ngrok.app/twilio/media">' in twiml
    assert '<Parameter name="callSid" value="CA123" />' in twiml
    assert '<Parameter name="callerPhone" value="+15551234567" />' in twiml


def test_twilio_media_streaming_endpoint_completes_turn_before_stop(tmp_path: Path) -> None:
    manager = build_manager(tmp_path)

    started = manager.handle_event(
        {
            "event": "start",
            "start": {
                "callSid": "CA123",
                "streamSid": "MZ123",
                "customParameters": {"callerPhone": "+15551234567"},
            },
        }
    )
    completed = manager.handle_event(media_message("MZ123", b"caller audio"))
    stopped = manager.handle_event({"event": "stop", "streamSid": "MZ123"})

    assert started.status == "accepted"
    assert completed.status == "completed"
    assert completed.assistant_text == "For Lakeview Flats unit 2B, rent is $2,450 per month."
    assert completed.degradation == "none"
    assert completed.outbound_messages[0]["event"] == "media"
    assert completed.outbound_messages[0]["streamSid"] == "MZ123"
    assert completed.outbound_messages[1] == {
        "event": "mark",
        "streamSid": "MZ123",
        "mark": {"name": "assistant-turn"},
    }
    assert manager.sessions["CA123"].caller_phone == "+15551234567"
    assert manager.sessions["CA123"].session_state is not None
    assert stopped.status == "accepted"


def test_twilio_start_accepts_top_level_stream_sid(tmp_path: Path) -> None:
    manager = build_manager(tmp_path)

    started = manager.handle_event(
        {
            "event": "start",
            "streamSid": "MZ123",
            "start": {
                "callSid": "CA123",
                "customParameters": {"callerPhone": "+15551234567"},
            },
        }
    )
    completed = manager.handle_event(media_message("MZ123", b"caller audio"))

    assert started.status == "accepted"
    assert completed.status == "completed"
    assert manager.sessions["CA123"].stream_sid == "MZ123"


def test_twilio_manager_poll_completes_delayed_streaming_endpoint(tmp_path: Path) -> None:
    manager = build_manager(
        tmp_path,
        streaming_events=(
            (),
            (
                StreamingTranscriptEvent(
                    type="final_transcript",
                    transcript=Transcript(
                        text="How much is the lake-facing unit at Lakeview Flats?",
                        confidence=0.93,
                    ),
                ),
                StreamingTranscriptEvent(type="utterance_complete", event_id="turn-1"),
            ),
        ),
    )
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})
    accepted = manager.handle_event(media_message("MZ123", b"caller audio"))

    results = manager.poll_streaming_events()

    assert accepted.status == "accepted"
    assert len(results) == 1
    assert results[0].status == "completed"
    assert "$2,450 per month" in (results[0].assistant_text or "")


def test_twilio_media_accumulates_multiple_final_segments(tmp_path: Path) -> None:
    manager = build_manager(
        tmp_path,
        streaming_events=(
            (
                StreamingTranscriptEvent(
                    type="final_transcript",
                    transcript=Transcript(text="How much is", confidence=0.91),
                ),
            ),
            (
                StreamingTranscriptEvent(
                    type="final_transcript",
                    transcript=Transcript(
                        text="the lake-facing unit at Lakeview Flats?",
                        confidence=0.95,
                    ),
                ),
                StreamingTranscriptEvent(type="utterance_complete", event_id="turn-1"),
            ),
        ),
    )
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})

    first = manager.handle_event(media_message("MZ123", b"first"))
    completed = manager.handle_event(media_message("MZ123", b"second", sequence=3))

    assert first.status == "accepted"
    assert completed.status == "completed"
    assert "$2,450 per month" in (completed.assistant_text or "")


def test_twilio_media_ignores_interim_only_and_empty_final_transcripts(tmp_path: Path) -> None:
    manager = build_manager(
        tmp_path,
        streaming_events=(
            (
                StreamingTranscriptEvent(
                    type="interim_transcript",
                    transcript=Transcript(text="How much", confidence=0.6),
                ),
            ),
            (
                StreamingTranscriptEvent(
                    type="final_transcript",
                    transcript=Transcript(text=" ", confidence=0.9),
                ),
                StreamingTranscriptEvent(type="utterance_complete", event_id="turn-1"),
            ),
        ),
    )
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})

    interim = manager.handle_event(media_message("MZ123", b"first"))
    empty = manager.handle_event(media_message("MZ123", b"second", sequence=3))

    assert interim.status == "accepted"
    assert empty.status == "accepted"
    assert empty.reason == "empty_streaming_transcript"
    assert manager.sessions["CA123"].session_state is None


def test_twilio_media_suppresses_duplicate_endpoint_events(tmp_path: Path) -> None:
    manager = build_manager(
        tmp_path,
        streaming_events=(
            (
                StreamingTranscriptEvent(
                    type="final_transcript",
                    transcript=Transcript(
                        text="How much is the lake-facing unit at Lakeview Flats?",
                        confidence=0.93,
                    ),
                ),
                StreamingTranscriptEvent(type="utterance_complete", event_id="turn-1"),
                StreamingTranscriptEvent(type="utterance_complete", event_id="turn-1"),
            ),
        ),
    )
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})

    completed = manager.handle_event(media_message("MZ123", b"caller audio"))

    assert completed.status == "completed"
    assert manager.sessions["CA123"].completed_turns == 1


def test_twilio_media_does_not_stream_non_twilio_tts_audio(tmp_path: Path) -> None:
    manager = build_manager(tmp_path, tts_content_type="audio/wav")
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})

    completed = manager.handle_event(media_message("MZ123", b"caller audio"))

    assert completed.status == "completed"
    assert completed.assistant_text is not None
    assert completed.outbound_messages == ()


def test_twilio_media_streams_deepgram_mulaw_tts_audio(tmp_path: Path) -> None:
    manager = build_manager(tmp_path, tts_content_type="audio/mulaw;rate=8000")
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})

    completed = manager.handle_event(media_message("MZ123", b"caller audio"))

    assert completed.status == "completed"
    assert completed.outbound_messages[0]["event"] == "media"


def test_twilio_media_ignores_malformed_stale_and_empty_events(tmp_path: Path) -> None:
    manager = build_manager(tmp_path)
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})

    malformed = manager.handle_event(
        {"event": "media", "streamSid": "MZ123", "media": {"payload": "%%%"}}
    )
    first = manager.handle_event(media_message("MZ123", b"first", sequence=4))
    stale = manager.handle_event(media_message("MZ123", b"duplicate", sequence=4))
    empty_stop = manager.handle_event({"event": "stop", "streamSid": "MZ999"})

    assert malformed.status == "ignored"
    assert malformed.reason == "invalid_media_payload"
    assert first.status == "completed"
    assert stale.status == "ignored"
    assert stale.reason == "stale_sequence"
    assert empty_stop.status == "ignored"
    assert empty_stop.reason == "unknown_call"


def test_twilio_media_bounds_audio_buffer(tmp_path: Path) -> None:
    manager = TwilioCallManager(
        voice_pipeline=build_manager(tmp_path).voice_pipeline,
        max_audio_bytes=4,
    )
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})

    result = manager.handle_event(media_message("MZ123", b"too large"))

    assert result.status == "failed"
    assert result.reason == "audio_buffer_exceeded"


def test_twilio_media_falls_back_to_stop_buffer_when_streaming_is_disabled(
    tmp_path: Path,
) -> None:
    manager = build_manager(tmp_path, streaming_enabled=False)
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})
    buffered = manager.handle_event(media_message("MZ123", b"caller audio"))
    completed = manager.handle_event({"event": "stop", "streamSid": "MZ123"})

    assert buffered.status == "accepted"
    assert completed.status == "completed"


def test_twilio_streaming_provider_failure_degrades_without_write(tmp_path: Path) -> None:
    manager = build_manager(tmp_path, streaming_fail_on_audio=True)
    manager.handle_event({"event": "start", "start": {"callSid": "CA123", "streamSid": "MZ123"}})

    result = manager.handle_event(media_message("MZ123", b"caller audio"))

    assert result.status == "failed"
    assert result.reason == "streaming_stt_failed: fake streaming STT failure"
    assert manager.sessions["CA123"].session_state is None


def test_twilio_low_confidence_streaming_transcript_uses_write_gate(tmp_path: Path) -> None:
    manager = build_manager(
        tmp_path,
        transcript="How much is the lake-facing unit at Lakeview Flats?",
    )
    manager.handle_event(
        {
            "event": "start",
            "start": {
                "callSid": "CA123",
                "streamSid": "MZ123",
                "customParameters": {"callerPhone": "555-123-4567"},
            },
        }
    )
    first = manager.handle_event(media_message("MZ123", b"first"))
    manager.streaming_speech_to_text = FakeStreamingSpeechToTextProvider(
        (
            (
                StreamingTranscriptEvent(
                    type="final_transcript",
                    transcript=Transcript(
                        text="My name is Avery Lee and I am interested in this.",
                        confidence=0.42,
                    ),
                ),
                StreamingTranscriptEvent(type="utterance_complete", event_id="turn-2"),
            ),
        )
    )
    manager.sessions["CA123"].streaming_stt = manager.streaming_speech_to_text.start_stream()

    second = manager.handle_event(media_message("MZ123", b"second", sequence=3))

    assert first.status == "completed"
    assert second.status == "completed"
    state = manager.sessions["CA123"].session_state
    assert state is not None
    assert state.capture is not None
    assert state.capture.pending_confirmation is not None


def test_twilio_voice_endpoint_returns_twiml_and_websocket_accepts_media(
    tmp_path: Path,
) -> None:
    settings = build_settings(telephony_public_base_url="https://voice.example.test")
    manager = build_manager(
        tmp_path,
        streaming_events=(
            (
                StreamingTranscriptEvent(
                    type="interim_transcript",
                    transcript=Transcript(text="How much", confidence=0.6),
                ),
            ),
        ),
    )
    client = TestClient(create_app(settings=settings, twilio_call_manager=manager))

    response = client.post(
        "/twilio/voice",
        content="CallSid=CA123&From=%2B15551234567",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "wss://voice.example.test/twilio/media" in response.text

    with client.websocket_connect("/twilio/media") as websocket:
        websocket.send_json(
            {
                "event": "start",
                "start": {
                    "callSid": "CA123",
                    "streamSid": "MZ123",
                    "customParameters": {"callerPhone": "+15551234567"},
                },
            }
        )
        websocket.send_json(media_message("MZ123", b"caller audio"))

    assert manager.sessions["CA123"].caller_phone == "+15551234567"
    assert manager.sessions["CA123"].streaming_stt is not None
    assert TWILIO_MULAW_CONTENT_TYPE == "audio/x-mulaw;rate=8000"


def test_twilio_voice_endpoint_rejects_missing_signature_when_token_is_configured(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        telephony_auth_token=SecretStr("synthetic-token"),
        telephony_public_base_url="https://voice.example.test",
    )
    client = TestClient(create_app(settings=settings, twilio_call_manager=build_manager(tmp_path)))

    response = client.post(
        "/twilio/voice",
        content="CallSid=CA123&From=%2B15551234567",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing Twilio signature"


def test_twilio_voice_endpoint_accepts_valid_signature_when_token_is_configured(
    tmp_path: Path,
) -> None:
    form = {"CallSid": "CA123", "From": "+15551234567"}
    signature = _twilio_signature(
        "https://voice.example.test/twilio/voice",
        form,
        "synthetic-token",
    )
    settings = build_settings(
        telephony_auth_token=SecretStr("synthetic-token"),
        telephony_public_base_url="https://voice.example.test",
    )
    client = TestClient(create_app(settings=settings, twilio_call_manager=build_manager(tmp_path)))

    response = client.post(
        "/twilio/voice",
        content="CallSid=CA123&From=%2B15551234567",
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "x-twilio-signature": signature,
        },
    )

    assert response.status_code == 200
    assert "wss://voice.example.test/twilio/media" in response.text
