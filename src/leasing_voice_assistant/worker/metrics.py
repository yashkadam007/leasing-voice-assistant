"""Local structured metrics capture and reporting for voice calls."""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TURN_LATENCY_FIELDS = (
    "tool_duration_ms",
    "transcription_ms",
    "end_of_turn_ms",
    "llm_ttft_ms",
    "tts_ttfb_ms",
    "playback_ms",
    "e2e_ms",
    "assistant_duration_ms",
)
SUMMARY_LATENCY_FIELDS = ("connected_to_greeting_ms", "call_duration_ms")


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
        }
        self.writer.write(record)
        self._pending_user_metrics = {}
        self._pending_tools = []

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


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Read valid JSON objects from a local metrics file."""
    records = []
    with Path(path).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}: {exc.msg}") from exc
            if isinstance(record, dict):
                records.append(record)
    return records


def format_summary(records: Iterable[Mapping[str, Any]]) -> str:
    """Build the local baseline report described in the improvement plan."""
    all_records = list(records)
    turns = [record for record in all_records if record.get("record_type") == "turn"]
    calls = [record for record in all_records if record.get("record_type") == "call_summary"]
    lines = [f"Calls: {len(calls)}", f"Turns: {len(turns)}", "", "Latency (ms)"]

    for field in (*TURN_LATENCY_FIELDS, *SUMMARY_LATENCY_FIELDS):
        source = calls if field in SUMMARY_LATENCY_FIELDS else turns
        lines.append(_format_distribution(field, _numeric_values(source, field)))

    tool_turns = [turn for turn in turns if turn.get("has_tool_call")]
    non_tool_turns = [turn for turn in turns if not turn.get("has_tool_call")]
    lines.extend(
        [
            "",
            "End-to-end latency by turn type (ms)",
            _format_distribution("tool", _numeric_values(tool_turns, "e2e_ms")),
            _format_distribution("non_tool", _numeric_values(non_tool_turns, "e2e_ms")),
            "",
            "Tool duration by name (ms)",
        ]
    )
    grouped_tools: dict[str, list[float]] = defaultdict(list)
    for turn in turns:
        for tool in turn.get("tool_calls") or []:
            if isinstance(tool, dict) and _is_number(tool.get("duration_ms")):
                grouped_tools[str(tool.get("name") or "unknown")].append(tool["duration_ms"])
    if grouped_tools:
        for name in sorted(grouped_tools):
            lines.append(_format_distribution(name, grouped_tools[name]))
    else:
        lines.append("no samples")

    interruptions = sum(int(bool(turn.get("interrupted"))) for turn in turns)
    errors = sum(int(call.get("error_count") or 0) for call in calls)
    lines.extend(["", f"Interruptions: {interruptions}", f"Errors: {errors}", "", "Slowest turns"])
    slowest = sorted(
        (turn for turn in turns if _is_number(turn.get("e2e_ms"))),
        key=lambda turn: float(turn["e2e_ms"]),
        reverse=True,
    )[:5]
    if not slowest:
        lines.append("no samples")
    for turn in slowest:
        lines.append(
            f"{turn.get('call_id')} turn={turn.get('turn_id')} "
            f"e2e_ms={_display_number(turn['e2e_ms'])}"
        )
    return "\n".join(lines)


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


def _numeric_values(records: Iterable[Mapping[str, Any]], field: str) -> list[float]:
    return [float(record[field]) for record in records if _is_number(record.get(field))]


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _format_distribution(label: str, values: list[float]) -> str:
    if not values:
        return f"{label}: count=0"
    return (
        f"{label}: count={len(values)} p50={_display_number(_percentile(values, 0.50))} "
        f"p90={_display_number(_percentile(values, 0.90))} "
        f"p95={_display_number(_percentile(values, 0.95))} "
        f"max={_display_number(max(values))}"
    )


def _display_number(value: float) -> str:
    return str(round(value))


def main() -> None:
    """Console entrypoint for summarizing a local JSONL metrics file."""
    parser = argparse.ArgumentParser(description="Summarize local voice-call metrics")
    parser.add_argument("path", nargs="?", default="metrics/voice_metrics.jsonl")
    args = parser.parse_args()
    try:
        print(format_summary(load_records(args.path)))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
