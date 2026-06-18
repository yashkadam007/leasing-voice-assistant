"""Call metadata extraction for LiveKit SIP jobs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from json import JSONDecodeError, loads
from typing import Any

from leasing_voice_assistant.agent import CallState


@dataclass(frozen=True)
class CallContext:
    """Normalized call metadata used to seed call-scoped agent state."""

    room_name: str | None = None
    participant_identity: str | None = None
    caller_phone_number: str | None = None
    call_sid: str | None = None
    sip_trunk_id: str | None = None
    sip_trunk_name: str | None = None

    def to_call_state(self) -> CallState:
        """Return agent state seeded from trustworthy transport metadata."""
        return CallState(caller_phone_number=self.caller_phone_number)


PHONE_KEYS = (
    "sip.phoneNumber",
    "sip.phone_number",
    "sip.from",
    "sip.from_user",
    "sip.caller",
    "twilio.from",
    "caller_phone_number",
    "callerPhoneNumber",
    "from",
)
CALL_ID_KEYS = (
    "sip.callID",
    "sip.call_id",
    "sip.callSid",
    "sip.call_sid",
    "twilio.callSid",
    "twilio.call_sid",
    "call_sid",
    "callSid",
)
TRUNK_ID_KEYS = ("sip.trunkID", "sip.trunk_id", "sipTrunkId", "trunk_id")
TRUNK_NAME_KEYS = ("sip.trunkName", "sip.trunk_name", "sipTrunkName", "trunk_name")


def build_call_context(
    *,
    room: Any | None = None,
    participant: Any | None = None,
    room_name: str | None = None,
    participant_identity: str | None = None,
    attributes: Mapping[str, Any] | None = None,
    metadata: str | Mapping[str, Any] | None = None,
) -> CallContext:
    """Extract normalized call metadata from LiveKit-like room and participant objects."""
    room_name = _clean_text(room_name) or _clean_text(_get_attr(room, "name"))
    participant_identity = _clean_text(participant_identity) or _clean_text(
        _get_attr(participant, "identity")
    )

    merged = _metadata_mapping(_get_attr(room, "metadata"))
    merged.update(_metadata_mapping(metadata))
    merged.update(_metadata_mapping(_get_attr(participant, "metadata")))
    merged.update(_mapping_or_empty(_get_attr(participant, "attributes")))
    merged.update(_mapping_or_empty(attributes))

    return CallContext(
        room_name=room_name,
        participant_identity=participant_identity,
        caller_phone_number=_first_present(merged, PHONE_KEYS),
        call_sid=_first_present(merged, CALL_ID_KEYS),
        sip_trunk_id=_first_present(merged, TRUNK_ID_KEYS),
        sip_trunk_name=_first_present(merged, TRUNK_NAME_KEYS),
    )


def _first_present(values: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        clean = _clean_text(values.get(key))
        if clean is not None:
            return clean
    return None


def _metadata_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        clean = value.strip()
        if not clean:
            return {}
        try:
            decoded = loads(clean)
        except JSONDecodeError:
            return {}
        return _mapping_or_empty(decoded)
    return _mapping_or_empty(value)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _get_attr(value: Any, name: str) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None
