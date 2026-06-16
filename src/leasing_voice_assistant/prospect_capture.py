from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from leasing_voice_assistant.interfaces import (
    ProspectInterestRecord,
    ProspectRecord,
    ProspectRepository,
)
from leasing_voice_assistant.property_resolution import PropertyResolutionState

WriteGateOutcome = Literal["blocked", "needs_confirmation", "written"]
WriteGateReason = Literal[
    "none",
    "target_not_write_ready",
    "missing_name",
    "missing_phone",
    "unclear_intent",
    "low_transcript_confidence",
]

_LOW_CONFIDENCE_THRESHOLD = 0.70
_GARBLED_MARKERS = (
    "[inaudible]",
    "[unclear]",
    "inaudible",
    "garbled",
    "transcription failed",
    "???",
)
_YES_CONFIRMATIONS = frozenset({"yes", "yeah", "yep", "correct", "that's right", "that is right"})
_INTEREST_PHRASES = (
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


@dataclass(frozen=True)
class PendingConfirmation:
    property_id: str
    unit_id: str | None
    name: str
    phone: str
    email: str | None
    source: str
    notes: str | None


@dataclass(frozen=True)
class ProspectCaptureState:
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    interest_intent: bool = False
    pending_confirmation: PendingConfirmation | None = None


@dataclass(frozen=True)
class ProspectCaptureRequest:
    user_text: str
    resolution: PropertyResolutionState
    prior_state: ProspectCaptureState | None = None
    caller_phone: str | None = None
    transcript_confidence: float | None = None
    source: str = "voice_call"


@dataclass(frozen=True)
class ProspectCaptureResult:
    outcome: WriteGateOutcome
    reason: WriteGateReason
    state: ProspectCaptureState
    prompt: str | None = None
    prospect: ProspectRecord | None = None
    interest: ProspectInterestRecord | None = None


class ProspectCaptureService:
    def __init__(self, prospect_repository: ProspectRepository) -> None:
        self.prospect_repository = prospect_repository

    def process(self, request: ProspectCaptureRequest) -> ProspectCaptureResult:
        prior = request.prior_state or ProspectCaptureState()
        extracted_name = _extract_name(request.user_text)
        extracted_phone = _extract_phone(request.user_text)
        extracted_email = _extract_email(request.user_text)

        name = extracted_name or prior.name
        phone = request.caller_phone or extracted_phone or prior.phone
        email = extracted_email or prior.email
        intent = prior.interest_intent or _has_interest_intent(request.user_text)
        low_confidence = _is_low_confidence(request.user_text, request.transcript_confidence)

        base_state = ProspectCaptureState(
            name=name,
            phone=phone,
            email=email,
            interest_intent=intent,
            pending_confirmation=None,
        )

        if request.resolution.write_ready is not True or request.resolution.property_id is None:
            return _blocked(
                state=base_state,
                reason="target_not_write_ready",
                prompt="Which property or unit should I record your interest in?",
            )

        if not _is_plausible_name(name):
            return _blocked(
                state=base_state,
                reason="missing_name",
                prompt="What name should I put on the prospect record?",
            )

        if not _is_plausible_phone(phone):
            return _blocked(
                state=base_state,
                reason="missing_phone",
                prompt="What phone number should the leasing team use?",
            )

        assert name is not None
        assert phone is not None
        confirmed_name = name.strip()
        confirmed_phone = phone.strip()
        notes = _notes_for(request.resolution)
        pending = PendingConfirmation(
            property_id=request.resolution.property_id,
            unit_id=request.resolution.unit_id,
            name=confirmed_name,
            phone=confirmed_phone,
            email=email.strip() if email else None,
            source=request.source,
            notes=notes,
        )

        if (
            _is_confirmation(request.user_text)
            and prior.pending_confirmation == pending
            and not low_confidence
        ):
            return self._write(pending)

        if not intent:
            state = ProspectCaptureState(
                name=name,
                phone=phone,
                email=email,
                interest_intent=False,
                pending_confirmation=pending,
            )
            return ProspectCaptureResult(
                outcome="needs_confirmation",
                reason="unclear_intent",
                state=state,
                prompt=_confirmation_prompt(pending),
            )

        if low_confidence:
            state = ProspectCaptureState(
                name=name,
                phone=phone,
                email=email,
                interest_intent=True,
                pending_confirmation=pending,
            )
            return ProspectCaptureResult(
                outcome="needs_confirmation",
                reason="low_transcript_confidence",
                state=state,
                prompt=_confirmation_prompt(pending),
            )

        return self._write(pending)

    def _write(self, pending: PendingConfirmation) -> ProspectCaptureResult:
        prospect = self.prospect_repository.upsert_prospect(
            name=pending.name,
            phone=pending.phone,
            email=pending.email,
        )
        interest = self.prospect_repository.record_interest(
            prospect_id=prospect.id,
            property_id=pending.property_id,
            unit_id=pending.unit_id,
            source=pending.source,
            notes=pending.notes,
        )
        state = ProspectCaptureState(
            name=prospect.name,
            phone=prospect.phone,
            email=prospect.email,
            interest_intent=True,
            pending_confirmation=None,
        )
        return ProspectCaptureResult(
            outcome="written",
            reason="none",
            state=state,
            prospect=prospect,
            interest=interest,
        )


def _blocked(
    *,
    state: ProspectCaptureState,
    reason: WriteGateReason,
    prompt: str,
) -> ProspectCaptureResult:
    return ProspectCaptureResult(
        outcome="blocked",
        reason=reason,
        state=state,
        prompt=prompt,
    )


def _extract_name(text: str) -> str | None:
    patterns = (
        r"\bmy name is\s+([a-z][a-z .'-]{1,60})",
        r"\bthis is\s+([a-z][a-z .'-]{1,60})",
        r"\bi am\s+([a-z][a-z .'-]{1,60})",
        r"\bi'm\s+([a-z][a-z .'-]{1,60})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_name(match.group(1))
    return None


def _clean_name(value: str) -> str | None:
    value = re.split(
        r"\b(?:and|phone|number|at|interested|calling|about|for|with)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = " ".join(value.replace(",", " ").split()).strip(" .'")
    if not cleaned:
        return None
    return cleaned.title()


def _extract_phone(text: str) -> str | None:
    match = re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", text)
    if not match:
        return None
    return match.group(0).strip()


def _extract_email(text: str) -> str | None:
    match = re.search(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _has_interest_intent(text: str) -> bool:
    normalized = " ".join(re.findall(r"[a-z0-9']+", text.casefold()))
    return any(phrase in normalized for phrase in _INTEREST_PHRASES)


def _is_confirmation(text: str) -> bool:
    normalized = " ".join(re.findall(r"[a-z']+", text.casefold()))
    return normalized in _YES_CONFIRMATIONS


def _is_low_confidence(text: str, confidence: float | None) -> bool:
    if confidence is not None and confidence < _LOW_CONFIDENCE_THRESHOLD:
        return True
    lowered = text.casefold()
    return any(marker in lowered for marker in _GARBLED_MARKERS)


def _is_plausible_name(name: str | None) -> bool:
    if name is None:
        return False
    parts = [part for part in re.findall(r"[A-Za-z][A-Za-z'-]*", name) if len(part) > 1]
    return len(parts) >= 1


def _is_plausible_phone(phone: str | None) -> bool:
    if phone is None:
        return False
    digits = re.sub(r"\D", "", phone)
    return 10 <= len(digits) <= 15


def _notes_for(resolution: PropertyResolutionState) -> str:
    target = resolution.property_name or resolution.property_id or "resolved property"
    if resolution.unit_label:
        return f"Confirmed interest in {target} unit {resolution.unit_label}."
    return f"Confirmed interest in {target}."


def _confirmation_prompt(pending: PendingConfirmation) -> str:
    target = "the selected unit" if pending.unit_id else "the property"
    return (
        f"Just to confirm, should I have the leasing team contact {pending.name} "
        f"at {pending.phone} about {target}?"
    )
