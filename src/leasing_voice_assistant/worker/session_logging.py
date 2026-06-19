"""LiveKit session diagnostics and metrics event translation."""

from __future__ import annotations

import json
import logging
from typing import Any

from leasing_voice_assistant.worker.metrics import CallMetricsRecorder

logger = logging.getLogger(__name__)


def install_session_logging(
    session: Any,
    *,
    call_metrics: CallMetricsRecorder | None = None,
) -> None:
    """Attach realtime call diagnostics to a LiveKit agent session."""

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(event: Any) -> None:
        transcript = clean_log_text(getattr(event, "transcript", ""))
        if not transcript:
            return

        if getattr(event, "is_final", False):
            logger.info(
                "voice_session.stt_final transcript=%r speaker_id=%s language=%s",
                transcript,
                getattr(event, "speaker_id", None),
                getattr(event, "language", None),
            )
        else:
            logger.debug("voice_session.stt_partial transcript=%r", transcript)

    @session.on("conversation_item_added")
    def _on_conversation_item_added(event: Any) -> None:
        item = getattr(event, "item", None)
        if getattr(item, "type", None) != "message":
            return

        role = getattr(item, "role", "unknown")
        text = message_text(item)
        metrics = latency_metrics(getattr(item, "metrics", {}))
        if role == "user":
            if call_metrics is not None:
                call_metrics.record_user_message(getattr(item, "metrics", {}))
            logger.info(
                "voice_session.user_turn_committed text=%r metrics=%s",
                text,
                metrics,
            )
        elif role == "assistant":
            if call_metrics is not None:
                call_metrics.record_assistant_message(
                    getattr(item, "metrics", {}),
                    interrupted=bool(getattr(item, "interrupted", False)),
                )
            logger.info(
                "voice_session.assistant_response_committed text=%r interrupted=%s metrics=%s",
                text,
                getattr(item, "interrupted", False),
                metrics,
            )
        else:
            logger.debug("voice_session.message_committed role=%s text=%r", role, text)

    @session.on("speech_created")
    def _on_speech_created(event: Any) -> None:
        logger.info(
            "voice_session.speech_created source=%s user_initiated=%s",
            getattr(event, "source", None),
            getattr(event, "user_initiated", None),
        )

    @session.on("agent_state_changed")
    def _on_agent_state_changed(event: Any) -> None:
        if call_metrics is not None:
            call_metrics.record_agent_state(getattr(event, "new_state", None))
        logger.info(
            "voice_session.agent_state_changed old_state=%s new_state=%s",
            getattr(event, "old_state", None),
            getattr(event, "new_state", None),
        )

    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(event: Any) -> None:
        if call_metrics is not None:
            call_metrics.record_false_interruption()
        logger.info(
            "voice_session.false_interruption resumed=%s",
            getattr(event, "resumed", None),
        )

    @session.on("function_tools_executed")
    def _on_function_tools_executed(event: Any) -> None:
        tool_summaries = []
        for function_call, function_output in event.zipped():
            tool_summaries.append(
                {
                    "name": getattr(function_call, "name", None),
                    "call_id": getattr(function_call, "call_id", None),
                    "output": tool_output_summary(function_output),
                }
            )
        logger.info("voice_session.function_tools_executed tools=%s", tool_summaries)

    @session.on("metrics_collected")
    def _on_metrics_collected(event: Any) -> None:
        metrics = getattr(event, "metrics", None)
        if call_metrics is not None and getattr(metrics, "type", None) in {
            "llm_metrics",
            "realtime_model_metrics",
        }:
            call_metrics.record_llm_request(metrics)

    @session.on("error")
    def _on_error(event: Any) -> None:
        if call_metrics is not None:
            call_metrics.record_error()
        logger.error(
            "voice_session.error source=%r error=%r",
            getattr(event, "source", None),
            getattr(event, "error", None),
        )

    @session.on("close")
    def _on_close(event: Any) -> None:
        if call_metrics is not None:
            call_metrics.close(
                reason=getattr(event, "reason", None),
                has_error=getattr(event, "error", None) is not None,
            )
        logger.info(
            "voice_session.closed reason=%s error=%r",
            getattr(event, "reason", None),
            getattr(event, "error", None),
        )


def message_text(message: Any) -> str:
    text_content = getattr(message, "text_content", None)
    if text_content:
        return clean_log_text(text_content)

    content = getattr(message, "content", [])
    text_parts = [part for part in content if isinstance(part, str)]
    return clean_log_text(" ".join(text_parts))


def clean_log_text(value: str, *, max_length: int = 500) -> str:
    text = " ".join(value.split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def latency_metrics(metrics: Any) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        return {}
    keys = [
        "transcription_delay",
        "end_of_turn_delay",
        "llm_node_ttft",
        "tts_node_ttfb",
        "playback_latency",
        "e2e_latency",
    ]
    return {
        key: round(value, 3) for key in keys if isinstance((value := metrics.get(key)), int | float)
    }


def tool_output_summary(function_output: Any) -> dict[str, Any] | None:
    if function_output is None:
        return None

    summary: dict[str, Any] = {
        "is_error": getattr(function_output, "is_error", None),
    }
    output = getattr(function_output, "output", "")
    try:
        parsed = json.loads(output)
    except (TypeError, json.JSONDecodeError):
        summary["text"] = clean_log_text(str(output), max_length=200)
        return summary

    if isinstance(parsed, dict):
        for key in ("status", "reasons", "ambiguous"):
            if key in parsed:
                summary[key] = parsed[key]
        return summary

    summary["text"] = clean_log_text(str(parsed), max_length=200)
    return summary
