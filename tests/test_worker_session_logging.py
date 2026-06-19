from types import SimpleNamespace

from leasing_voice_assistant.worker.session_logging import (
    clean_log_text,
    latency_metrics,
    message_text,
    tool_output_summary,
)


def test_clean_log_text_normalizes_and_bounds_text() -> None:
    assert clean_log_text("  hello\n  there  ") == "hello there"
    assert clean_log_text("abcdefgh", max_length=6) == "abc..."


def test_message_text_prefers_text_content_and_filters_other_content() -> None:
    assert message_text(SimpleNamespace(text_content=" primary\ntext ")) == "primary text"
    assert message_text(SimpleNamespace(text_content=None, content=["one", 2, "two"])) == "one two"


def test_latency_metrics_selects_and_rounds_known_numeric_values() -> None:
    assert latency_metrics(
        {
            "transcription_delay": 0.1236,
            "e2e_latency": 1,
            "ignored": 4.2,
            "llm_node_ttft": "unknown",
        }
    ) == {"transcription_delay": 0.124, "e2e_latency": 1}
    assert latency_metrics(None) == {}


def test_tool_output_summary_extracts_safe_structured_fields() -> None:
    output = SimpleNamespace(
        is_error=False,
        output='{"status":"captured","reasons":[],"private":"ignored"}',
    )

    assert tool_output_summary(output) == {
        "is_error": False,
        "status": "captured",
        "reasons": [],
    }


def test_tool_output_summary_bounds_non_json_text() -> None:
    output = SimpleNamespace(is_error=True, output="x" * 205)

    assert tool_output_summary(output) == {
        "is_error": True,
        "text": "x" * 197 + "...",
    }
