import json
from types import SimpleNamespace

from leasing_voice_assistant.agent.grounding import GroundingOutcome
from leasing_voice_assistant.worker.metrics import (
    CallMetricsRecorder,
    JsonlMetricsWriter,
)


def test_grounding_metrics_are_content_free_and_count_llm_requests(tmp_path) -> None:
    path = tmp_path / "metrics.jsonl"
    recorder = CallMetricsRecorder(call_id="call-1", writer=JsonlMetricsWriter(path))
    outcome = GroundingOutcome(
        payload={
            "statuses": ["matched"],
            "results": [
                {
                    "status": "matched",
                    "source_type": "unit_database",
                    "private_text": "caller and retrieved content",
                }
            ],
        }
    )

    recorder.record_grounding(outcome, duration_ms=12.4)
    recorder.record_llm_request(SimpleNamespace(duration=0.8, ttft=0.2, cancelled=False))
    recorder.record_assistant_message({}, interrupted=False)

    raw = path.read_text()
    record = json.loads(raw)
    assert "caller and retrieved content" not in raw
    assert record["grounding_applied"] is True
    assert record["grounding_statuses"] == ["matched"]
    assert record["grounding_source_types"] == ["unit_database"]
    assert record["grounding_result_count"] == 1
    assert record["llm_request_count"] == 1
    assert record["llm_requests"][0]["duration_ms"] == 800
