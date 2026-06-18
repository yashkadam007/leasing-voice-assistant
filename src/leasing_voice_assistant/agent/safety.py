"""Safety gate for prospect interest capture."""

from dataclasses import dataclass

from leasing_voice_assistant.agent.state import CallState

CAPTURE_CONFIDENCE_THRESHOLD = 0.8


@dataclass(frozen=True)
class CaptureSafetyResult:
    """Result of evaluating whether prospect capture is allowed."""

    allowed: bool
    reasons: tuple[str, ...]


def evaluate_capture_safety(
    state: CallState,
    *,
    confidence_threshold: float = CAPTURE_CONFIDENCE_THRESHOLD,
) -> CaptureSafetyResult:
    """Return machine-readable rejection reasons before any prospect write."""
    reasons: list[str] = []
    target = state.current_target

    if not _has_text(state.caller_phone_number):
        reasons.append("missing_phone")
    if not _has_text(state.caller_name):
        reasons.append("missing_name")
    if target is None:
        reasons.append("missing_target")
    else:
        if target.confidence < confidence_threshold:
            reasons.append("low_confidence")
        if target.ambiguous and not target.ambiguity_resolved:
            reasons.append("ambiguous_property")
    if not state.confirmed_interest:
        reasons.append("needs_confirmation")

    return CaptureSafetyResult(allowed=not reasons, reasons=tuple(reasons))


def _has_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())
