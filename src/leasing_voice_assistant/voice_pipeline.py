from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from leasing_voice_assistant.conversation_session import (
    ConversationSessionService,
    ConversationSessionState,
    ConversationTurnRequest,
    ConversationTurnResult,
)
from leasing_voice_assistant.interfaces import (
    ModelMessage,
    ModelProvider,
    SpeechToTextProvider,
    SynthesizedSpeech,
    TextToSpeechProvider,
    Transcript,
)

VoiceDegradation = Literal["none", "stt_failed", "model_failed", "model_rejected", "tts_failed"]

_MAX_AUDIO_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class AudioInput:
    audio: bytes
    content_type: str


@dataclass(frozen=True)
class VoiceTurnRequest:
    session_id: str
    audio: AudioInput
    state: ConversationSessionState | None = None
    caller_phone: str | None = None
    voice: str | None = None
    include_debug_trace: bool = False


@dataclass(frozen=True)
class VoiceTiming:
    stt_ms: float
    session_ms: float
    model_ms: float
    tts_ms: float
    total_ms: float


@dataclass(frozen=True)
class VoiceDebug:
    session_result: ConversationTurnResult | None
    model_metadata: tuple[tuple[str, str], ...] = ()
    stt_error: str | None = None
    model_error: str | None = None
    tts_error: str | None = None
    grounding_reason: str | None = None


@dataclass(frozen=True)
class VoiceTurnResult:
    session_id: str
    transcript: Transcript
    assistant_text: str
    speech: SynthesizedSpeech | None
    state: ConversationSessionState
    timing: VoiceTiming
    degradation: VoiceDegradation = "none"
    debug: VoiceDebug | None = None


class VoicePipeline:
    def __init__(
        self,
        *,
        speech_to_text: SpeechToTextProvider,
        model: ModelProvider,
        text_to_speech: TextToSpeechProvider,
        session_service: ConversationSessionService,
    ) -> None:
        self.speech_to_text = speech_to_text
        self.model = model
        self.text_to_speech = text_to_speech
        self.session_service = session_service

    def handle_turn(self, request: VoiceTurnRequest) -> VoiceTurnResult:
        started = time.perf_counter()
        _validate_audio(request.audio)

        stt_started = time.perf_counter()
        try:
            transcript = self.speech_to_text.transcribe(
                request.audio.audio,
                content_type=request.audio.content_type,
            )
        except Exception as error:
            timings = _timing(
                started,
                stt_started=stt_started,
                session_started=None,
                model_started=None,
                tts_started=None,
            )
            fallback_text = "I had trouble hearing that. Could you please repeat it?"
            return VoiceTurnResult(
                session_id=request.session_id,
                transcript=Transcript(text="", confidence=None),
                assistant_text=fallback_text,
                speech=None,
                state=request.state or ConversationSessionState(),
                timing=timings,
                degradation="stt_failed",
                debug=VoiceDebug(session_result=None, stt_error=str(error)),
            )

        session_started = time.perf_counter()
        session_result = self.session_service.handle_turn(
            ConversationTurnRequest(
                user_text=transcript.text,
                state=request.state,
                caller_phone=request.caller_phone,
                transcript_confidence=transcript.confidence,
                include_debug_trace=request.include_debug_trace,
            )
        )

        safe_text = session_result.assistant_text
        assistant_text = safe_text
        degradation: VoiceDegradation = "none"
        model_metadata: tuple[tuple[str, str], ...] = ()
        model_error: str | None = None
        grounding_reason: str | None = None

        model_started = time.perf_counter()
        try:
            model_response = self.model.generate(_model_messages(transcript.text, session_result))
            model_metadata = model_response.metadata
            candidate = model_response.text.strip()
            grounding_reason = _grounding_rejection_reason(candidate, safe_text, session_result)
            if candidate and grounding_reason is None:
                assistant_text = candidate
            elif candidate:
                degradation = "model_rejected"
        except Exception as error:
            degradation = "model_failed"
            model_error = str(error)

        tts_started = time.perf_counter()
        speech: SynthesizedSpeech | None
        tts_error: str | None = None
        try:
            speech = self.text_to_speech.synthesize(assistant_text, voice=request.voice)
        except Exception as error:
            speech = None
            tts_error = str(error)
            if degradation == "none":
                degradation = "tts_failed"

        return VoiceTurnResult(
            session_id=request.session_id,
            transcript=transcript,
            assistant_text=assistant_text,
            speech=speech,
            state=session_result.state,
            timing=_timing(
                started,
                stt_started=stt_started,
                session_started=session_started,
                model_started=model_started,
                tts_started=tts_started,
            ),
            degradation=degradation,
            debug=VoiceDebug(
                session_result=session_result,
                model_metadata=model_metadata,
                model_error=model_error,
                tts_error=tts_error,
                grounding_reason=grounding_reason,
            ),
        )


def _validate_audio(audio: AudioInput) -> None:
    if not audio.content_type:
        raise ValueError("audio content_type is required")
    if not audio.audio:
        raise ValueError("audio payload is required")
    if len(audio.audio) > _MAX_AUDIO_BYTES:
        raise ValueError("audio payload exceeds maximum supported size")


def _model_messages(
    user_text: str, session_result: ConversationTurnResult
) -> tuple[ModelMessage, ...]:
    evidence = _evidence_summary(session_result)
    capture = session_result.capture
    capture_summary = "none"
    if capture is not None:
        capture_summary = (
            f"{capture.outcome}; reason={capture.reason}; prompt={capture.prompt or ''}"
        )
    return (
        ModelMessage(
            role="system",
            content=(
                "Rewrite the safe assistant reply for natural spoken delivery. "
                "Do not add property facts, prices, availability, policies, names, phone numbers, "
                "or commitments that are not present in the safe reply or evidence. "
                "If the safe reply asks a clarification or confirmation question, keep that intent."
            ),
        ),
        ModelMessage(
            role="user",
            content=(
                f"Caller transcript: {user_text}\n"
                f"Safe reply: {session_result.assistant_text}\n"
                f"Answer route: {session_result.answer.route}\n"
                f"Fallback reason: {session_result.answer.fallback_reason}\n"
                f"Evidence: {evidence}\n"
                f"Capture: {capture_summary}\n"
                "Return only the spoken assistant reply."
            ),
        ),
    )


def _evidence_summary(session_result: ConversationTurnResult) -> str:
    database_evidence = [
        f"{item.source}:{item.record_id}:{item.field}={item.value}"
        for item in session_result.answer.database_evidence
    ]
    kb_evidence = [
        f"{snippet.source_id}:{snippet.section_heading or snippet.title or 'snippet'}"
        for snippet in session_result.answer.knowledge_snippets
    ]
    values = database_evidence + kb_evidence
    return "; ".join(values) if values else "none"


def _grounding_rejection_reason(
    candidate: str,
    safe_text: str,
    session_result: ConversationTurnResult,
) -> str | None:
    if not candidate:
        return "empty_model_response"
    safe_numbers = set(_numbers(safe_text))
    candidate_numbers = set(_numbers(candidate))
    if not candidate_numbers.issubset(safe_numbers | _evidence_numbers(session_result)):
        return "model_introduced_unsupported_number"
    safe_property_terms = _property_terms(session_result)
    if safe_property_terms and any(term in candidate.casefold() for term in safe_property_terms):
        return None
    if _meaningful_overlap(candidate, safe_text):
        return None
    return "model_response_did_not_overlap_safe_reply_or_evidence"


def _numbers(text: str) -> tuple[str, ...]:
    return tuple(
        part for part in text.replace(",", "").split() if any(char.isdigit() for char in part)
    )


def _evidence_numbers(session_result: ConversationTurnResult) -> set[str]:
    numbers: set[str] = set()
    for item in session_result.answer.database_evidence:
        numbers.update(_numbers(str(item.value)))
    return numbers


def _property_terms(session_result: ConversationTurnResult) -> tuple[str, ...]:
    terms = []
    resolution = session_result.answer.resolution
    if resolution.property_name:
        terms.append(resolution.property_name.casefold())
    if resolution.unit_label:
        terms.append(f"unit {resolution.unit_label}".casefold())
    return tuple(terms)


def _meaningful_overlap(left: str, right: str) -> bool:
    left_words = _content_words(left)
    right_words = _content_words(right)
    return len(left_words & right_words) >= 2


def _content_words(text: str) -> set[str]:
    stop_words = {"the", "and", "that", "you", "for", "with", "this", "your", "about"}
    return {
        word.strip(".,?!:;()").casefold()
        for word in text.split()
        if len(word.strip(".,?!:;()")) > 3 and word.casefold() not in stop_words
    }


def _timing(
    started: float,
    *,
    stt_started: float,
    session_started: float | None,
    model_started: float | None,
    tts_started: float | None,
) -> VoiceTiming:
    now = time.perf_counter()
    stt_end = session_started or now
    session_end = model_started or stt_end
    model_end = tts_started or session_end
    return VoiceTiming(
        stt_ms=(stt_end - stt_started) * 1000,
        session_ms=(session_end - session_started) * 1000 if session_started else 0.0,
        model_ms=(model_end - model_started) * 1000 if model_started else 0.0,
        tts_ms=(now - tts_started) * 1000 if tts_started else 0.0,
        total_ms=(now - started) * 1000,
    )
