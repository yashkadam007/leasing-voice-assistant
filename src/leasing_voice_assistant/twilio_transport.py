from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from leasing_voice_assistant.conversation_session import ConversationSessionState
from leasing_voice_assistant.voice_pipeline import AudioInput, VoicePipeline, VoiceTurnRequest

TwilioEventName = Literal["connected", "start", "media", "stop", "mark"]
TwilioFrameStatus = Literal["accepted", "ignored", "completed", "failed"]

TWILIO_MULAW_CONTENT_TYPE = "audio/x-mulaw;rate=8000"


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
    last_sequence_number: int = 0
    completed_turns: int = 0

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


class TwilioCallManager:
    def __init__(
        self,
        *,
        voice_pipeline: VoicePipeline,
        max_audio_bytes: int = 1_000_000,
    ) -> None:
        self.voice_pipeline = voice_pipeline
        self.max_audio_bytes = max_audio_bytes
        self.sessions: dict[str, TwilioCallState] = {}

    def start_call(self, call_sid: str, *, caller_phone: str | None = None) -> TwilioCallState:
        state = self.sessions.get(call_sid)
        if state is None:
            state = TwilioCallState(call_sid=call_sid, caller_phone=caller_phone)
            self.sessions[call_sid] = state
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

    def _handle_start(self, message: dict[str, Any]) -> TwilioFrameResult:
        start = _object_field(message, "start")
        if start is None:
            return TwilioFrameResult(status="ignored", reason="missing_start")

        call_sid = _string_field(start, "callSid") or _custom_parameter(start, "callSid")
        stream_sid = _string_field(start, "streamSid")
        if not call_sid:
            return TwilioFrameResult(status="ignored", reason="missing_call_sid")

        caller_phone = _custom_parameter(start, "callerPhone")
        state = self.start_call(call_sid, caller_phone=caller_phone)
        state.stream_sid = stream_sid
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
        if not state.append_audio(chunk, max_audio_bytes=self.max_audio_bytes):
            state.consume_audio()
            return TwilioFrameResult(status="failed", reason="audio_buffer_exceeded")
        return TwilioFrameResult(status="accepted")

    def _handle_stop(self, message: dict[str, Any]) -> TwilioFrameResult:
        state = self._state_for_message(message)
        if state is None:
            return TwilioFrameResult(status="ignored", reason="unknown_call")
        audio = state.consume_audio()
        if not audio:
            return TwilioFrameResult(status="ignored", reason="empty_audio_turn")

        state.completed_turns += 1
        turn_id = state.completed_turns
        try:
            result = self.voice_pipeline.handle_turn(
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

        state.session_state = result.state
        return TwilioFrameResult(
            status="completed",
            outbound_messages=_outbound_messages(state.stream_sid, result.speech),
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
    if content_type not in {"audio/x-mulaw", TWILIO_MULAW_CONTENT_TYPE, "audio/basic"}:
        return ()
    payload = base64.b64encode(audio).decode("ascii")
    return (
        {"event": "media", "streamSid": stream_sid, "media": {"payload": payload}},
        {"event": "mark", "streamSid": stream_sid, "mark": {"name": "assistant-turn"}},
    )


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
