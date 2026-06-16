from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from leasing_voice_assistant.answer_orchestration import (
    AnswerOrchestrator,
    AnswerRoute,
    AnswerTurnRequest,
    AnswerTurnResult,
)
from leasing_voice_assistant.property_resolution import PropertyResolutionState
from leasing_voice_assistant.prospect_capture import (
    ProspectCaptureRequest,
    ProspectCaptureResult,
    ProspectCaptureService,
    ProspectCaptureState,
    WriteGateOutcome,
)

TranscriptRole = Literal["user", "assistant"]

_CAPTURE_NAME_PATTERNS = (
    r"\bmy name is\b",
    r"\bthis is\b",
)
_CAPTURE_INTEREST_PHRASES = (
    "i am interested",
    "i'm interested",
    "interested in",
    "register my interest",
    "record my interest",
    "put me down",
    "sign me up",
    "contact me about",
    "call me about",
    "i want this",
    "i want that",
    "i'd like this",
    "i would like this",
    "i want to apply",
)
_CONFIRMATIONS = frozenset({"yes", "yeah", "yep", "correct", "that's right", "that is right"})


@dataclass(frozen=True)
class TranscriptEntry:
    turn_number: int
    role: TranscriptRole
    text: str


@dataclass(frozen=True)
class ConversationSessionState:
    turn_number: int = 0
    resolution: PropertyResolutionState | None = None
    capture: ProspectCaptureState | None = None
    transcript: tuple[TranscriptEntry, ...] = ()


@dataclass(frozen=True)
class ConversationTurnRequest:
    user_text: str
    state: ConversationSessionState | None = None
    caller_phone: str | None = None
    transcript_confidence: float | None = None
    include_debug_trace: bool = False


@dataclass(frozen=True)
class ConversationDebugTrace:
    turn_number: int
    answer_route: AnswerRoute
    answer_fallback_reason: str
    property_id: str | None
    unit_id: str | None
    property_write_ready: bool
    database_evidence_count: int
    knowledge_snippet_count: int
    capture_processed: bool
    capture_outcome: WriteGateOutcome | None
    capture_reason: str | None


@dataclass(frozen=True)
class ConversationTurnResult:
    assistant_text: str
    state: ConversationSessionState
    answer: AnswerTurnResult
    capture: ProspectCaptureResult | None = None
    debug_trace: ConversationDebugTrace | None = None


class ConversationSessionService:
    def __init__(
        self,
        *,
        answer_orchestrator: AnswerOrchestrator,
        prospect_capture_service: ProspectCaptureService,
        source: str = "text_harness",
    ) -> None:
        self.answer_orchestrator = answer_orchestrator
        self.prospect_capture_service = prospect_capture_service
        self.source = source

    def handle_turn(self, request: ConversationTurnRequest) -> ConversationTurnResult:
        prior_state = request.state or ConversationSessionState()
        prior_resolution = prior_state.resolution
        answer = self.answer_orchestrator.answer_turn(
            AnswerTurnRequest(
                user_text=request.user_text,
                prior_resolution=prior_resolution,
            )
        )

        capture_result: ProspectCaptureResult | None = None
        if _should_process_capture(request.user_text, prior_state.capture):
            capture_result = self.prospect_capture_service.process(
                ProspectCaptureRequest(
                    user_text=request.user_text,
                    resolution=answer.resolution,
                    prior_state=prior_state.capture,
                    caller_phone=request.caller_phone,
                    transcript_confidence=request.transcript_confidence,
                    source=self.source,
                )
            )

        assistant_text = _assistant_text(answer, capture_result)
        turn_number = prior_state.turn_number + 1
        transcript = prior_state.transcript + (
            TranscriptEntry(turn_number=turn_number, role="user", text=request.user_text),
            TranscriptEntry(turn_number=turn_number, role="assistant", text=assistant_text),
        )
        next_state = ConversationSessionState(
            turn_number=turn_number,
            resolution=answer.resolution,
            capture=capture_result.state if capture_result else prior_state.capture,
            transcript=transcript,
        )
        return ConversationTurnResult(
            assistant_text=assistant_text,
            state=next_state,
            answer=answer,
            capture=capture_result,
            debug_trace=(
                _debug_trace(turn_number, answer, capture_result)
                if request.include_debug_trace
                else None
            ),
        )


def _should_process_capture(text: str, prior_state: ProspectCaptureState | None) -> bool:
    if prior_state is not None and (
        prior_state.name
        or prior_state.phone
        or prior_state.email
        or prior_state.interest_intent
        or prior_state.pending_confirmation
    ):
        return True

    normalized = " ".join(re.findall(r"[a-z0-9']+", text.casefold()))
    if any(phrase in normalized for phrase in _CAPTURE_INTEREST_PHRASES):
        return True
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _CAPTURE_NAME_PATTERNS):
        return True
    if re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", text):
        return True
    if re.search(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", text, flags=re.IGNORECASE):
        return True
    return normalized in _CONFIRMATIONS


def _assistant_text(
    answer: AnswerTurnResult,
    capture: ProspectCaptureResult | None,
) -> str:
    if capture is None:
        return answer.answer_text
    if capture.outcome in {"blocked", "needs_confirmation"} and capture.prompt:
        if answer.route in {"database", "knowledge_base", "combined"}:
            return f"{answer.answer_text} {capture.prompt}"
        return capture.prompt
    if capture.outcome == "written":
        target = answer.resolution.property_name or "the property"
        if answer.resolution.unit_label:
            target = f"{target} unit {answer.resolution.unit_label}"
        return f"You're all set. I recorded your interest in {target}."
    return answer.answer_text


def _debug_trace(
    turn_number: int,
    answer: AnswerTurnResult,
    capture: ProspectCaptureResult | None,
) -> ConversationDebugTrace:
    return ConversationDebugTrace(
        turn_number=turn_number,
        answer_route=answer.route,
        answer_fallback_reason=answer.fallback_reason,
        property_id=answer.resolution.property_id,
        unit_id=answer.resolution.unit_id,
        property_write_ready=answer.resolution.write_ready,
        database_evidence_count=len(answer.database_evidence),
        knowledge_snippet_count=len(answer.knowledge_snippets),
        capture_processed=capture is not None,
        capture_outcome=capture.outcome if capture else None,
        capture_reason=capture.reason if capture else None,
    )
