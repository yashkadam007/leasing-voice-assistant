from dataclasses import dataclass

from leasing_voice_assistant.worker.call_context import build_call_context


@dataclass
class FakeRoom:
    name: str
    metadata: str = ""


@dataclass
class FakeParticipant:
    identity: str
    attributes: dict
    metadata: str = ""


def test_build_call_context_prefers_participant_attributes() -> None:
    room = FakeRoom(name="inbound-room", metadata='{"caller_phone_number":"+10000000000"}')
    participant = FakeParticipant(
        identity="sip-caller",
        attributes={
            "sip.phoneNumber": "+14155551212",
            "sip.callSid": "CA123",
            "sip.trunkID": "trunk-1",
            "sip.trunkName": "twilio-main",
        },
    )

    context = build_call_context(room=room, participant=participant)

    assert context.room_name == "inbound-room"
    assert context.participant_identity == "sip-caller"
    assert context.caller_phone_number == "+14155551212"
    assert context.call_sid == "CA123"
    assert context.sip_trunk_id == "trunk-1"
    assert context.sip_trunk_name == "twilio-main"
    assert context.to_call_state().caller_phone_number == "+14155551212"


def test_build_call_context_reads_json_metadata_when_attributes_missing() -> None:
    context = build_call_context(
        room_name="room-a",
        participant_identity="participant-a",
        metadata={
            "twilio.from": "(415) 555-1212",
            "twilio.callSid": "CA456",
        },
    )

    assert context.room_name == "room-a"
    assert context.participant_identity == "participant-a"
    assert context.caller_phone_number == "(415) 555-1212"
    assert context.call_sid == "CA456"


def test_build_call_context_tolerates_missing_or_invalid_metadata() -> None:
    context = build_call_context(metadata="not-json")

    assert context.room_name is None
    assert context.participant_identity is None
    assert context.caller_phone_number is None
    assert context.call_sid is None
    assert context.to_call_state().caller_phone_number is None
