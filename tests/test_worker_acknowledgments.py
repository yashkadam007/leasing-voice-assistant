import asyncio
import json
from types import SimpleNamespace

import pytest

from leasing_voice_assistant.agent.grounding import GroundingOutcome
from leasing_voice_assistant.worker.acknowledgments import (
    AcknowledgmentCoordinator,
    classify_grounding,
)
from leasing_voice_assistant.worker.metrics import CallMetricsRecorder, JsonlMetricsWriter


def _outcome(**query):
    return GroundingOutcome(
        payload={
            "statuses": ["matched"],
            "results": [{"status": "matched"}],
            "query": query,
        }
    )


@pytest.mark.parametrize(
    ("query", "capture", "expected"),
    [
        ({"policy_topics": ["fees"], "availability_requested": True}, False, "policy"),
        (
            {"comparison_requested": True, "policy_topics": ["fees"]},
            False,
            "comparison",
        ),
        (
            {"comparison_requested": True, "availability_requested": True},
            False,
            "comparison",
        ),
        ({"comparison_requested": True}, True, "capture"),
        ({"policy_topics": ["fees"]}, True, "capture"),
        ({"availability_requested": True}, True, "capture"),
        (
            {
                "comparison_requested": True,
                "compound_question": True,
                "policy_topics": ["fees"],
                "property_terms": ["Aurora Heights"],
                "location_terms": ["Austin"],
                "unit_numbers": ["101A"],
                "bedroom_count": 1,
                "minimum_rent_cents": 100_000,
                "maximum_rent_cents": 200_000,
                "availability_requested": True,
            },
            False,
            "comparison",
        ),
    ],
)
def test_class_precedence_covers_pairwise_and_all_read_overlaps(query, capture, expected) -> None:
    assert classify_grounding(_outcome(**query), capture_intent=capture) == expected


@pytest.mark.parametrize("status", ["ambiguous", "no_match", "needs_clarification", "unavailable"])
def test_non_authoritative_grounding_is_ineligible(status) -> None:
    outcome = _outcome(availability_requested=True)
    outcome.payload["statuses"] = [status]
    assert classify_grounding(outcome) is None


def test_studio_search_is_eligible() -> None:
    assert classify_grounding(_outcome(bedroom_count=0)) == "property_search"


def test_fast_substantive_audio_cancels_acknowledgment_without_synthesis() -> None:
    async def scenario():
        synthesis_started = False

        async def synthesize(_text):
            nonlocal synthesis_started
            synthesis_started = True
            yield SimpleNamespace(label="ack", duration=0.1)

        async def substantive():
            yield SimpleNamespace(label="substantive", duration=0.1)

        coordinator = AcknowledgmentCoordinator(synthesize=synthesize, delay_seconds=0.05)
        epoch = coordinator.begin_turn()
        coordinator.set_grounding(epoch, _outcome(availability_requested=True))
        frames = [frame async for frame in coordinator.wrap_substantive(substantive())]
        return synthesis_started, [frame.label for frame in frames]

    assert asyncio.run(scenario()) == (False, ["substantive"])


def test_ack_and_substantive_synthesize_concurrently_but_play_in_order() -> None:
    async def scenario():
        substantive_started = asyncio.Event()
        acknowledgment_started = asyncio.Event()

        async def synthesize(_text):
            acknowledgment_started.set()
            assert substantive_started.is_set()
            yield SimpleNamespace(label="ack-1", duration=0.1)
            await asyncio.sleep(0)
            yield SimpleNamespace(label="ack-2", duration=0.1)

        async def substantive():
            substantive_started.set()
            await acknowledgment_started.wait()
            await asyncio.sleep(0.02)
            yield SimpleNamespace(label="substantive", duration=0.1)

        coordinator = AcknowledgmentCoordinator(synthesize=synthesize, delay_seconds=0)
        epoch = coordinator.begin_turn()
        coordinator.set_grounding(epoch, _outcome(availability_requested=True))
        return [frame.label async for frame in coordinator.wrap_substantive(substantive())]

    assert asyncio.run(scenario()) == ["ack-1", "ack-2", "substantive"]


def test_tool_only_phase_preserves_capture_acknowledgment_for_followup_audio() -> None:
    async def scenario():
        spoken = []

        async def synthesize(text):
            spoken.append(text)
            yield SimpleNamespace(label="ack", duration=0.01)

        async def no_audio():
            if False:
                yield None

        async def followup():
            await asyncio.sleep(0.01)
            yield SimpleNamespace(label="substantive", duration=0.01)

        coordinator = AcknowledgmentCoordinator(synthesize=synthesize, delay_seconds=0)
        epoch = coordinator.begin_turn()
        coordinator.set_grounding(epoch, _outcome())
        async for _frame in coordinator.wrap_substantive(no_audio()):
            pass
        coordinator.set_capture_intent()
        labels = [frame.label async for frame in coordinator.wrap_substantive(followup())]
        return spoken, labels

    assert asyncio.run(scenario()) == (
        ["One moment while I note that."],
        ["ack", "substantive"],
    )


def test_cooldown_limit_phrase_rotation_and_capture_override() -> None:
    async def scenario():
        spoken = []

        async def synthesize(text):
            spoken.append(text)
            yield SimpleNamespace(label="ack", duration=0.01)

        async def slow_substantive():
            await asyncio.sleep(0.01)
            yield SimpleNamespace(label="substantive", duration=0.01)

        coordinator = AcknowledgmentCoordinator(
            synthesize=synthesize, delay_seconds=0, call_limit=2
        )
        for index in range(5):
            epoch = coordinator.begin_turn()
            if index == 2:
                coordinator.set_grounding(epoch, _outcome(policy_topics=["fees"]))
                coordinator.set_capture_intent()
            else:
                coordinator.set_grounding(epoch, _outcome(availability_requested=True))
            async for _frame in coordinator.wrap_substantive(slow_substantive()):
                pass
        return spoken

    spoken = asyncio.run(scenario())
    assert spoken == [
        "Let me check the available options.",
        "One moment while I note that.",
    ]


def test_acknowledgment_metrics_are_content_free(tmp_path) -> None:
    async def scenario(recorder):
        async def synthesize(_text):
            yield SimpleNamespace(duration=0.01)

        async def substantive():
            await asyncio.sleep(0.01)
            yield SimpleNamespace(duration=0.01)

        coordinator = AcknowledgmentCoordinator(
            synthesize=synthesize, metrics=recorder, delay_seconds=0
        )
        epoch = coordinator.begin_turn()
        coordinator.set_grounding(epoch, _outcome(policy_topics=["fees"]))
        async for _frame in coordinator.wrap_substantive(substantive()):
            pass

    path = tmp_path / "metrics.jsonl"
    recorder = CallMetricsRecorder(call_id="call-1", writer=JsonlMetricsWriter(path))
    asyncio.run(scenario(recorder))
    recorder.record_assistant_message({}, interrupted=False)

    record = json.loads(path.read_text())
    assert record["acknowledgment_class"] == "policy"
    assert record["acknowledgment_outcome"] == "completed"
    assert record["acknowledgment_phrase_id"] == "policy-1"
    assert record["acknowledgment_started"] is True
    assert "property policy" not in path.read_text()
