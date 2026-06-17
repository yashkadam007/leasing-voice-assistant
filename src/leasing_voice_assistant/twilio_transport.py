from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from leasing_voice_assistant.conversation_session import ConversationSessionState
from leasing_voice_assistant.interfaces import (
    StreamingSpeechToTextProvider,
    StreamingSpeechToTextSession,
    StreamingTranscriptEvent,
    Transcript,
)
from leasing_voice_assistant.voice_pipeline import (
    AudioInput,
    TranscriptVoiceTurnRequest,
    VoicePipeline,
    VoiceTurnRequest,
)

TwilioEventName = Literal["connected", "start", "media", "stop", "mark"]
TwilioFrameStatus = Literal["accepted", "ignored", "completed", "failed"]

TWILIO_MULAW_CONTENT_TYPE = "audio/x-mulaw;rate=8000"
logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class TwilioVoiceWebhook:
    call_sid: str
    caller_phone: str | None = None
    public_base_url: str | None = None


@dataclass(frozen=True)
class TwilioFrameResult:
    status: TwilioFrameStatus
    reason: str | None = None
    outbound_messages: tuple[dict[str, Any], ...] = ()
    assistant_text: str | None = None
    degradation: str | None = None


@dataclass
class TwilioCallState:
    call_sid: str
    caller_phone: str | None = None
    stream_sid: str | None = None
    session_state: ConversationSessionState | None = None
    audio_chunks: list[bytes] | None = None
    streaming_stt: StreamingSpeechToTextSession | None = None
    transcript_segments: list[Transcript] | None = None
    active_utterance_key: str | None = None
    last_sequence_number: int = 0
    completed_turns: int = 0
    media_frame_count: int = 0
    inbound_audio_bytes: int = 0

    def append_audio(self, chunk: bytes, *, max_audio_bytes: int) -> bool:
        if self.audio_chunks is None:
            self.audio_chunks = []
        buffered = sum(len(item) for item in self.audio_chunks)
        if buffered + len(chunk) > max_audio_bytes:
            return False
        self.audio_chunks.append(chunk)
        return True

    def consume_audio(self) -> bytes:
        audio = b"".join(self.audio_chunks or [])
        self.audio_chunks = []
        return audio

    def append_transcript(self, transcript: Transcript, *, max_transcript_chars: int) -> bool:
        if self.transcript_segments is None:
            self.transcript_segments = []
        current_size = sum(len(segment.text) for segment in self.transcript_segments)
        if current_size + len(transcript.text) > max_transcript_chars:
            self.transcript_segments = []
            return False
        self.transcript_segments.append(transcript)
        return True

    def consume_transcript(self) -> Transcript | None:
        segments = self.transcript_segments or []
        self.transcript_segments = []
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        if not text:
            return None
        confidences = [segment.confidence for segment in segments if segment.confidence is not None]
        confidence = sum(confidences) / len(confidences) if confidences else None
        metadata: list[tuple[str, str]] = [("source", "streaming_stt")]
        for segment in segments:
            metadata.extend(segment.metadata)
        return Transcript(text=text, confidence=confidence, metadata=tuple(metadata))


class TwilioCallManager:
    def __init__(
        self,
        *,
        voice_pipeline: VoicePipeline,
        streaming_speech_to_text: StreamingSpeechToTextProvider | None = None,
        max_audio_bytes: int = 1_000_000,
        max_transcript_chars: int = 4_000,
    ) -> None:
        self.voice_pipeline = voice_pipeline
        self.streaming_speech_to_text = streaming_speech_to_text
        self.max_audio_bytes = max_audio_bytes
        self.max_transcript_chars = max_transcript_chars
        self.sessions: dict[str, TwilioCallState] = {}

    def start_call(self, call_sid: str, *, caller_phone: str | None = None) -> TwilioCallState:
        state = self.sessions.get(call_sid)
        if state is None:
            state = TwilioCallState(call_sid=call_sid, caller_phone=caller_phone)
            self.sessions[call_sid] = state
            logger.info(
                "twilio_call_started call=%s caller_present=%s",
                _safe_id(call_sid),
                bool(caller_phone),
            )
        elif caller_phone and not state.caller_phone:
            state.caller_phone = caller_phone
        return state

    def handle_event(self, message: dict[str, Any]) -> TwilioFrameResult:
        event = message.get("event")
        if not isinstance(event, str):
            return TwilioFrameResult(status="ignored", reason="missing_event")

        if event == "connected":
            return TwilioFrameResult(status="accepted")
        if event == "start":
            return self._handle_start(message)
        if event == "media":
            return self._handle_media(message)
        if event == "stop":
            return self._handle_stop(message)
        if event == "mark":
            return TwilioFrameResult(status="accepted")
        return TwilioFrameResult(status="ignored", reason="unsupported_event")

    def poll_streaming_events(self) -> tuple[TwilioFrameResult, ...]:
        results: list[TwilioFrameResult] = []
        for state in self.sessions.values():
            if state.streaming_stt is None:
                continue
            try:
                events = state.streaming_stt.poll_events()
            except Exception as error:
                results.append(
                    TwilioFrameResult(
                        status="failed",
                        reason=f"streaming_stt_poll_failed: {error}",
                    )
                )
                continue
            if events:
                results.append(self._handle_streaming_events(state, events))
        return tuple(results)

    def _handle_start(self, message: dict[str, Any]) -> TwilioFrameResult:
        start = _object_field(message, "start")
        if start is None:
            return TwilioFrameResult(status="ignored", reason="missing_start")

        call_sid = _string_field(start, "callSid") or _custom_parameter(start, "callSid")
        stream_sid = _string_field(start, "streamSid") or _string_field(message, "streamSid")
        if not call_sid:
            return TwilioFrameResult(status="ignored", reason="missing_call_sid")

        caller_phone = _custom_parameter(start, "callerPhone")
        state = self.start_call(call_sid, caller_phone=caller_phone)
        state.stream_sid = stream_sid
        logger.info(
            "twilio_stream_started call=%s stream=%s streaming_stt_configured=%s caller_present=%s",
            _safe_id(call_sid),
            _safe_id(stream_sid),
            self.streaming_speech_to_text is not None,
            bool(state.caller_phone),
        )
        if self.streaming_speech_to_text is not None and state.streaming_stt is None:
            try:
                state.streaming_stt = self.streaming_speech_to_text.start_stream()
            except Exception as error:
                logger.warning(
                    "streaming_stt_start_failed call=%s stream=%s error=%s",
                    _safe_id(call_sid),
                    _safe_id(stream_sid),
                    error,
                )
                return TwilioFrameResult(
                    status="failed",
                    reason=f"streaming_stt_start_failed: {error}",
                )
            logger.info(
                "streaming_stt_started call=%s stream=%s",
                _safe_id(call_sid),
                _safe_id(stream_sid),
            )
        return TwilioFrameResult(status="accepted")

    def _handle_media(self, message: dict[str, Any]) -> TwilioFrameResult:
        state = self._state_for_message(message)
        if state is None:
            return TwilioFrameResult(status="ignored", reason="unknown_call")
        if self._is_stale_sequence(state, message):
            return TwilioFrameResult(status="ignored", reason="stale_sequence")

        media = _object_field(message, "media")
        payload = _string_field(media, "payload") if media else None
        if not payload:
            return TwilioFrameResult(status="ignored", reason="missing_media_payload")
        try:
            chunk = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            return TwilioFrameResult(status="ignored", reason="invalid_media_payload")
        if not chunk:
            return TwilioFrameResult(status="ignored", reason="empty_media_payload")
        state.media_frame_count += 1
        state.inbound_audio_bytes += len(chunk)
        if state.media_frame_count == 1 or state.media_frame_count % 50 == 0:
            logger.info(
                "twilio_media_inbound call=%s stream=%s frames=%s bytes=%s streaming_stt_active=%s",
                _safe_id(state.call_sid),
                _safe_id(state.stream_sid),
                state.media_frame_count,
                state.inbound_audio_bytes,
                state.streaming_stt is not None,
            )
        if state.streaming_stt is not None:
            try:
                events = state.streaming_stt.send_audio(chunk)
            except Exception as error:
                logger.warning(
                    "streaming_stt_send_failed call=%s stream=%s error=%s",
                    _safe_id(state.call_sid),
                    _safe_id(state.stream_sid),
                    error,
                )
                return TwilioFrameResult(
                    status="failed",
                    reason=f"streaming_stt_failed: {error}",
                )
            return self._handle_streaming_events(state, events)
        if not state.append_audio(chunk, max_audio_bytes=self.max_audio_bytes):
            state.consume_audio()
            return TwilioFrameResult(status="failed", reason="audio_buffer_exceeded")
        return TwilioFrameResult(status="accepted")

    def _handle_stop(self, message: dict[str, Any]) -> TwilioFrameResult:
        state = self._state_for_message(message)
        if state is None:
            return TwilioFrameResult(status="ignored", reason="unknown_call")
        if state.streaming_stt is not None:
            try:
                events = state.streaming_stt.close()
            except Exception as error:
                state.streaming_stt = None
                logger.warning(
                    "streaming_stt_close_failed call=%s stream=%s error=%s",
                    _safe_id(state.call_sid),
                    _safe_id(state.stream_sid),
                    error,
                )
                return TwilioFrameResult(
                    status="failed",
                    reason=f"streaming_stt_close_failed: {error}",
                )
            state.streaming_stt = None
            result = self._handle_streaming_events(state, events)
            if result.status == "accepted":
                return TwilioFrameResult(status="accepted", reason="stream_closed")
            return result
        audio = state.consume_audio()
        if not audio:
            return TwilioFrameResult(status="ignored", reason="empty_audio_turn")

        state.completed_turns += 1
        turn_id = state.completed_turns
        try:
            voice_result = self.voice_pipeline.handle_turn(
                VoiceTurnRequest(
                    session_id=state.call_sid,
                    audio=AudioInput(audio=audio, content_type=TWILIO_MULAW_CONTENT_TYPE),
                    state=state.session_state,
                    caller_phone=state.caller_phone,
                    include_debug_trace=True,
                )
            )
        except Exception as error:
            return TwilioFrameResult(status="failed", reason=f"voice_pipeline_failed: {error}")
        if turn_id != state.completed_turns:
            return TwilioFrameResult(status="ignored", reason="stale_turn")

        state.session_state = voice_result.state
        return TwilioFrameResult(
            status="completed",
            outbound_messages=_outbound_messages(state.stream_sid, voice_result.speech),
            assistant_text=voice_result.assistant_text,
            degradation=voice_result.degradation,
        )

    def _handle_streaming_events(
        self,
        state: TwilioCallState,
        events: Sequence[StreamingTranscriptEvent],
    ) -> TwilioFrameResult:
        accepted_reason: str | None = None
        if events:
            logger.info(
                "streaming_stt_events call=%s stream=%s events=%s",
                _safe_id(state.call_sid),
                _safe_id(state.stream_sid),
                ",".join(_streaming_event_label(event) for event in events),
            )
        for event in events:
            if event.type == "provider_error":
                logger.warning(
                    "streaming_stt_provider_error call=%s stream=%s message=%s",
                    _safe_id(state.call_sid),
                    _safe_id(state.stream_sid),
                    event.message or "unknown",
                )
                return TwilioFrameResult(
                    status="failed",
                    reason=f"streaming_stt_provider_error: {event.message or 'unknown'}",
                )
            if (
                event.type in {"final_transcript", "utterance_complete"}
                and event.transcript is not None
                and not state.append_transcript(
                    event.transcript,
                    max_transcript_chars=self.max_transcript_chars,
                )
            ):
                return TwilioFrameResult(status="failed", reason="transcript_buffer_exceeded")
            if event.type == "utterance_complete":
                result = self._complete_streaming_utterance(state, event)
                if result.status != "accepted":
                    return result
                accepted_reason = result.reason
        return TwilioFrameResult(status="accepted", reason=accepted_reason)

    def _complete_streaming_utterance(
        self,
        state: TwilioCallState,
        event: StreamingTranscriptEvent,
    ) -> TwilioFrameResult:
        utterance_key = event.event_id or "|".join(
            segment.text for segment in state.transcript_segments or ()
        )
        if utterance_key and utterance_key == state.active_utterance_key:
            return TwilioFrameResult(status="ignored", reason="duplicate_utterance")
        transcript = state.consume_transcript()
        if transcript is None:
            logger.info(
                "streaming_utterance_empty call=%s stream=%s",
                _safe_id(state.call_sid),
                _safe_id(state.stream_sid),
            )
            return TwilioFrameResult(status="accepted", reason="empty_streaming_transcript")
        state.active_utterance_key = utterance_key
        state.completed_turns += 1
        turn_id = state.completed_turns
        logger.info(
            "streaming_utterance_complete call=%s stream=%s transcript_chars=%s confidence=%s",
            _safe_id(state.call_sid),
            _safe_id(state.stream_sid),
            len(transcript.text),
            _confidence_label(transcript.confidence),
        )
        try:
            result = self.voice_pipeline.handle_transcript_turn(
                TranscriptVoiceTurnRequest(
                    session_id=state.call_sid,
                    transcript=transcript,
                    state=state.session_state,
                    caller_phone=state.caller_phone,
                    include_debug_trace=True,
                )
            )
        except Exception as error:
            logger.warning(
                "voice_pipeline_failed call=%s stream=%s error=%s",
                _safe_id(state.call_sid),
                _safe_id(state.stream_sid),
                error,
            )
            return TwilioFrameResult(status="failed", reason=f"voice_pipeline_failed: {error}")
        if turn_id != state.completed_turns:
            return TwilioFrameResult(status="ignored", reason="stale_turn")

        state.session_state = result.state
        outbound = _outbound_messages(state.stream_sid, result.speech)
        speech_content_type = getattr(result.speech, "content_type", None)
        speech_audio = getattr(result.speech, "audio", b"")
        speech_bytes = len(speech_audio) if isinstance(speech_audio, bytes) else 0
        model_error = result.debug.model_error if result.debug else None
        tts_error = result.debug.tts_error if result.debug else None
        logger.info(
            "voice_pipeline_completed call=%s stream=%s assistant_chars=%s "
            "outbound=%s degradation=%s speech_present=%s speech_content_type=%s "
            "speech_bytes=%s model_error=%s tts_error=%s assistant_text=%r",
            _safe_id(state.call_sid),
            _safe_id(state.stream_sid),
            len(result.assistant_text),
            len(outbound),
            result.degradation,
            result.speech is not None,
            speech_content_type,
            speech_bytes,
            _safe_error(model_error),
            _safe_error(tts_error),
            _safe_text(result.assistant_text),
        )
        return TwilioFrameResult(
            status="completed",
            outbound_messages=outbound,
            assistant_text=result.assistant_text,
            degradation=result.degradation,
        )

    def _state_for_message(self, message: dict[str, Any]) -> TwilioCallState | None:
        stream_sid = _string_field(message, "streamSid")
        if stream_sid:
            for state in self.sessions.values():
                if state.stream_sid == stream_sid:
                    return state
        call_sid = _string_field(message, "callSid")
        if call_sid:
            return self.sessions.get(call_sid)
        return None

    def _is_stale_sequence(self, state: TwilioCallState, message: dict[str, Any]) -> bool:
        sequence = _sequence_number(message)
        if sequence is None:
            return False
        if sequence <= state.last_sequence_number:
            return True
        state.last_sequence_number = sequence
        return False


def build_twilio_voice_twiml(
    webhook: TwilioVoiceWebhook,
    *,
    stream_path: str = "/twilio/media",
    greeting: str = "Thanks for calling. How can I help with your apartment search today?",
) -> str:
    if not webhook.call_sid:
        raise ValueError("call_sid is required")
    if not webhook.public_base_url:
        raise ValueError("public_base_url is required for Twilio media streams")

    stream_url = _websocket_url(webhook.public_base_url, stream_path)
    parameters = [
        ("callSid", webhook.call_sid),
        ("callerPhone", webhook.caller_phone or ""),
    ]
    parameter_xml = "".join(
        f'<Parameter name="{escape(name)}" value="{escape(value)}" />'
        for name, value in parameters
        if value
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Say>{escape(greeting)}</Say>"
        "<Connect>"
        f'<Stream url="{escape(stream_url)}">{parameter_xml}</Stream>'
        "</Connect>"
        "</Response>"
    )


def _websocket_url(public_base_url: str, stream_path: str) -> str:
    parsed = urlparse(public_base_url)
    if parsed.scheme not in {"http", "https", "ws", "wss"} or not parsed.netloc:
        raise ValueError("public_base_url must include scheme and host")
    scheme = "wss" if parsed.scheme in {"https", "wss"} else "ws"
    base_path = parsed.path.rstrip("/")
    path = stream_path if stream_path.startswith("/") else f"/{stream_path}"
    return f"{scheme}://{parsed.netloc}{base_path}{path}"


def _outbound_messages(
    stream_sid: str | None,
    speech: object,
) -> tuple[dict[str, Any], ...]:
    if stream_sid is None or speech is None:
        return ()
    audio = getattr(speech, "audio", None)
    content_type = getattr(speech, "content_type", "")
    if not isinstance(audio, bytes):
        return ()
    if not _is_twilio_mulaw_content_type(content_type):
        return ()
    payload = base64.b64encode(audio).decode("ascii")
    return (
        {"event": "media", "streamSid": stream_sid, "media": {"payload": payload}},
        {"event": "mark", "streamSid": stream_sid, "mark": {"name": "assistant-turn"}},
    )


def _is_twilio_mulaw_content_type(content_type: object) -> bool:
    if not isinstance(content_type, str):
        return False
    normalized = content_type.lower().replace(" ", "")
    if normalized in {"audio/x-mulaw", "audio/basic"}:
        return True
    if normalized in {"audio/x-mulaw;rate=8000", "audio/mulaw;rate=8000"}:
        return True
    return normalized in {"audio/x-mulaw;sample_rate=8000", "audio/mulaw;sample_rate=8000"}


def _object_field(message: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = message.get(key)
    return value if isinstance(value, dict) else None


def _string_field(message: dict[str, Any] | None, key: str) -> str | None:
    if message is None:
        return None
    value = message.get(key)
    return value if isinstance(value, str) and value else None


def _custom_parameter(start: dict[str, Any], key: str) -> str | None:
    custom = start.get("customParameters")
    if not isinstance(custom, dict):
        return None
    value = custom.get(key)
    return value if isinstance(value, str) and value else None


def _sequence_number(message: dict[str, Any]) -> int | None:
    value = message.get("sequenceNumber")
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _safe_id(value: str | None) -> str:
    if not value:
        return "missing"
    return f"...{value[-6:]}" if len(value) > 6 else value


def _confidence_label(value: float | None) -> str:
    return "unknown" if value is None else f"{value:.2f}"


def _safe_error(value: str | None) -> str:
    if not value:
        return "none"
    value = " ".join(value.split())
    return value[:160]


def _safe_text(value: str, *, limit: int = 240) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _streaming_event_label(event: StreamingTranscriptEvent) -> str:
    transcript = event.transcript
    if transcript is None:
        return event.type
    confidence = _confidence_label(transcript.confidence)
    return f"{event.type}:chars={len(transcript.text)}:conf={confidence}"
