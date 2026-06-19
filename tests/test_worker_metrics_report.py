from leasing_voice_assistant.worker.metrics_report import format_summary


def test_summary_separates_grounded_and_ordinary_turns() -> None:
    summary = format_summary(
        [
            {"record_type": "turn", "grounding_applied": True, "e2e_ms": 1000},
            {"record_type": "turn", "grounding_applied": False, "e2e_ms": 2000},
        ]
    )

    assert "read_grounded: count=1" in summary
    assert "non_tool: count=1" in summary
