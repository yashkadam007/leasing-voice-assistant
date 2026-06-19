"""Local structured metrics capture for voice calls."""

from __future__ import annotations

import json
import math
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TURN_LATENCY_FIELDS = (
    "grounding_duration_ms",
    "tool_duration_ms",
    "transcription_ms",
    "end_of_turn_ms",
    "llm_ttft_ms",
    "tts_ttfb_ms",
    "playback_ms",
    "e2e_ms",
    "assistant_duration_ms",
    "acknowledgment_start_ms",
    "acknowledgment_duration_ms",
    "substantive_audio_ready_ms",
    "substantive_audio_start_ms",
    "acknowledgment_to_substantive_gap_ms",
    "perceived_response_ms",
)
SUMMARY_LATENCY_FIELDS = ("connected_to_greeting_ms", "call_duration_ms")
ACKNOWLEDGMENT_DEFAULTS = {
    "acknowledgment_eligible": False,
    "acknowledgment_class": None,
    "acknowledgment_scheduled": False,
    "acknowledgment_started": False,
    "acknowledgment_outcome": "suppressed",
    "acknowledgment_start_ms": None,
    "acknowledgment_duration_ms": None,
    "substantive_audio_ready_ms": None,
    "substantive_audio_start_ms": None,
    "acknowledgment_to_substantive_gap_ms": None,
    "acknowledgment_phrase_id": None,
    "perceived_response_ms": None,
}


def utc_timestamp() -> str:
    """Return an RFC 3339 UTC timestamp."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class JsonlMetricsWriter:
    """Append metrics records to a process-local JSONL file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def write(self, record: Mapping[str, Any]) -> None:
        """Append one complete JSON object without retaining call content."""
        line = json.dumps(record, separators=(",", ":"), sort_keys=True)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as output:
                output.write(line + "\n")


class CallMetricsRecorder:
    """Collect LiveKit and local timings for one call."""

    def __init__(
        self,
        *,
        call_id: str,
        writer: JsonlMetricsWriter,
        connected_at: float | None = None,
    ) -> None:
        self.call_id = call_id
        self.writer = writer
        self._connected_at = connected_at if connected_at is not None else time.monotonic()
        self._pending_user_metrics: dict[str, Any] = {}
        self._pending_tools: list[dict[str, Any]] = []
        self._pending_grounding: dict[str, Any] = {}
        self._pending_acknowledgment: dict[str, Any] = {}
        self._pending_llm_requests: list[dict[str, Any]] = []
        self._turn_id = 0
        self._connected_to_greeting_ms: int | None = None
        self._interruption_count = 0
        self._false_interruption_count = 0
        self._error_count = 0
        self._closed = False

    def record_tool(self, name: str, duration_ms: float, *, is_error: bool = False) -> None:
        """Queue a completed tool timing for the assistant turn that consumes it."""
        self._pending_tools.append(
            {"name": name, "duration_ms": round(duration_ms), "is_error": is_error}
        )
        if is_error:
            self._error_count += 1

    def record_user_message(self, metrics: Any) -> None:
        """Retain only the timing fields from the latest committed user message."""
        self._pending_user_metrics = _metrics_mapping(metrics)

    def record_grounding(
        self,
        outcome: Any | None,
        *,
        duration_ms: float,
        cancelled: bool = False,
    ) -> None:
        """Queue content-free grounding metadata for the current turn."""
        payload = getattr(outcome, "payload", {}) if outcome is not None else {}
        results = payload.get("results", []) if isinstance(payload, dict) else []
        previously_cancelled = bool(self._pending_grounding.get("grounding_cancelled"))
        self._pending_grounding = {
            "grounding_applied": outcome is not None and not cancelled,
            "grounding_duration_ms": round(duration_ms),
            "grounding_statuses": list(payload.get("statuses", [])),
            "grounding_source_types": list(
                dict.fromkeys(
                    str(item.get("source_type"))
                    for item in results
                    if isinstance(item, dict) and item.get("source_type")
                )
            ),
            "grounding_result_count": len(results),
            "grounding_cancelled": cancelled or previously_cancelled,
            "grounding_deadline_exceeded": bool(getattr(outcome, "deadline_exceeded", False)),
            "grounding_needs_clarification": "needs_clarification" in payload.get("statuses", []),
        }

    def record_llm_request(self, metrics: Any) -> None:
        """Queue one content-free LLM phase timing for the current assistant turn."""
        self._pending_llm_requests.append(
            {
                "duration_ms": _seconds_to_ms(getattr(metrics, "duration", None)),
                "ttft_ms": _seconds_to_ms(getattr(metrics, "ttft", None)),
                "cancelled": bool(getattr(metrics, "cancelled", False)),
            }
        )

    def record_acknowledgment(self, turn_epoch: int, **values: Any) -> None:
        """Queue content-free acknowledgment lifecycle fields for a turn."""
        if self._pending_acknowledgment.get("_turn_epoch") not in (None, turn_epoch):
            self._pending_acknowledgment = {}
        self._pending_acknowledgment["_turn_epoch"] = turn_epoch
        self._pending_acknowledgment.update(values)

    def record_assistant_message(self, metrics: Any, *, interrupted: bool) -> None:
        """Write a completed assistant turn using its paired user and tool metrics."""
        assistant_metrics = _metrics_mapping(metrics)
        self._turn_id += 1
        if interrupted:
            self._interruption_count += 1

        tool_names = [str(tool["name"]) for tool in self._pending_tools]
        tool_duration_ms = sum(int(tool["duration_ms"]) for tool in self._pending_tools)
        record: dict[str, Any] = {
            "record_type": "turn",
            "timestamp": utc_timestamp(),
            "call_id": self.call_id,
            "turn_id": self._turn_id,
            "has_tool_call": bool(self._pending_tools),
            "tool_name": tool_names[0] if len(tool_names) == 1 else None,
            "tool_names": tool_names,
            "tool_duration_ms": tool_duration_ms if tool_names else None,
            "tool_calls": list(self._pending_tools),
            "transcription_ms": _seconds_to_ms(
                self._pending_user_metrics.get("transcription_delay")
            ),
            "end_of_turn_ms": _seconds_to_ms(self._pending_user_metrics.get("end_of_turn_delay")),
            "llm_ttft_ms": _seconds_to_ms(assistant_metrics.get("llm_node_ttft")),
            "tts_ttfb_ms": _seconds_to_ms(assistant_metrics.get("tts_node_ttfb")),
            "playback_ms": _seconds_to_ms(assistant_metrics.get("playback_latency")),
            "e2e_ms": _seconds_to_ms(assistant_metrics.get("e2e_latency")),
            "assistant_duration_ms": _duration_ms(assistant_metrics),
            "interrupted": interrupted,
            "llm_request_count": len(self._pending_llm_requests) or None,
            "llm_requests": list(self._pending_llm_requests),
            **self._pending_grounding,
            **ACKNOWLEDGMENT_DEFAULTS,
            **{
                key: value
                for key, value in self._pending_acknowledgment.items()
                if not key.startswith("_")
            },
        }
        self.writer.write(record)
        self._pending_user_metrics = {}
        self._pending_tools = []
        self._pending_grounding = {}
        self._pending_acknowledgment = {}
        self._pending_llm_requests = []

    def record_agent_state(self, new_state: Any) -> None:
        """Capture the first transition to speaking as greeting playback start."""
        if str(new_state) == "speaking" and self._connected_to_greeting_ms is None:
            self._connected_to_greeting_ms = round((time.monotonic() - self._connected_at) * 1000)

    def record_false_interruption(self) -> None:
        self._false_interruption_count += 1

    def record_error(self) -> None:
        self._error_count += 1

    def close(self, *, reason: Any = None, has_error: bool = False) -> None:
        """Write the single call summary record."""
        if self._closed:
            return
        self._closed = True
        if has_error and self._error_count == 0:
            self._error_count += 1
        self.writer.write(
            {
                "record_type": "call_summary",
                "timestamp": utc_timestamp(),
                "call_id": self.call_id,
                "call_duration_ms": round((time.monotonic() - self._connected_at) * 1000),
                "connected_to_greeting_ms": self._connected_to_greeting_ms,
                "turn_count": self._turn_id,
                "interruption_count": self._interruption_count,
                "false_interruption_count": self._false_interruption_count,
                "error_count": self._error_count,
                "close_reason": str(reason) if reason is not None else None,
                "naturalness_score": None,
                "voice_prosody_score": None,
                "pacing_score": None,
            }
        )


def _metrics_mapping(metrics: Any) -> dict[str, Any]:
    return dict(metrics) if isinstance(metrics, Mapping) else {}


def _seconds_to_ms(value: Any) -> int | None:
    return round(float(value) * 1000) if _is_number(value) else None


def _duration_ms(metrics: Mapping[str, Any]) -> int | None:
    started = metrics.get("started_speaking_at")
    stopped = metrics.get("stopped_speaking_at")
    if not (_is_number(started) and _is_number(stopped)):
        return None
    return max(round((float(stopped) - float(started)) * 1000), 0)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
