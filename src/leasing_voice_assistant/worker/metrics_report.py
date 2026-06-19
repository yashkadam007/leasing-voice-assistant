"""Offline reporting for locally captured voice-call metrics."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from leasing_voice_assistant.worker.metrics import SUMMARY_LATENCY_FIELDS, TURN_LATENCY_FIELDS


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
    grounded_turns = [turn for turn in turns if turn.get("grounding_applied")]
    non_tool_turns = [
        turn
        for turn in turns
        if not turn.get("has_tool_call") and not turn.get("grounding_applied")
    ]
    lines.extend(
        [
            "",
            "End-to-end latency by turn type (ms)",
            _format_distribution("tool", _numeric_values(tool_turns, "e2e_ms")),
            _format_distribution("read_grounded", _numeric_values(grounded_turns, "e2e_ms")),
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
