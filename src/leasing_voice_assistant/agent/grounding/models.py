"""Transport-neutral data models for deterministic grounding."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Literal

from leasing_voice_assistant.agent.state import CallState, ResolvedTarget

GroundingStatus = Literal["matched", "ambiguous", "no_match", "needs_clarification", "unavailable"]


@dataclass(frozen=True)
class CallStateSnapshot:
    """Immutable read view used while assembling a turn."""

    current_target: ResolvedTarget | None

    @classmethod
    def from_state(cls, state: CallState) -> CallStateSnapshot:
        target = state.current_target
        return cls(current_target=None if target is None else ResolvedTarget(**asdict(target)))


@dataclass(frozen=True)
class GroundingQuery:
    """Supported deterministic concepts extracted from one caller turn."""

    property_terms: tuple[str, ...] = ()
    location_terms: tuple[str, ...] = ()
    unit_numbers: tuple[str, ...] = ()
    bedroom_count: int | None = None
    minimum_rent_cents: int | None = None
    maximum_rent_cents: int | None = None
    availability_requested: bool = False
    policy_topics: tuple[str, ...] = ()
    comparison_requested: bool = False
    compound_question: bool = False
    unsupported_constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundingOutcome:
    """Pure grounding payload plus an optional state transition."""

    payload: dict[str, Any]
    target_transition: ResolvedTarget | None = None
    should_apply_transition: bool = False
    deadline_exceeded: bool = False

    def serialized(self) -> str:
        return json.dumps(self.payload, separators=(",", ":"), sort_keys=True)


class GroundingCancelled(Exception):
    """Raised when a newer caller turn makes retrieval stale."""
