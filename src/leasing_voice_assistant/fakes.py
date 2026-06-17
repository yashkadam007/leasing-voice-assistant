from collections.abc import Sequence

from leasing_voice_assistant.interfaces import (
    KnowledgeSnippet,
    ModelMessage,
    ModelResponse,
    PropertyRecord,
    ProspectInterestRecord,
    ProspectRecord,
    StreamingTranscriptEvent,
    SynthesizedSpeech,
    Transcript,
    UnitRecord,
    VoiceSession,
)


class FakeModelProvider:
    def __init__(
        self,
        response_text: str = "fake model response",
        *,
        fail: bool = False,
    ) -> None:
        self.response_text = response_text
        self.fail = fail
        self.requests: list[Sequence[ModelMessage]] = []

    def generate(self, messages: Sequence[ModelMessage]) -> ModelResponse:
        self.requests.append(tuple(messages))
        if self.fail:
            raise RuntimeError("fake model failure")
        return ModelResponse(text=self.response_text)


class FakeSpeechToTextProvider:
    def __init__(
        self,
        transcript: Transcript | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self.transcript = transcript or Transcript(text="fake transcript", confidence=1.0)
        self.fail = fail
        self.requests: list[tuple[bytes, str]] = []

    def transcribe(self, audio: bytes, *, content_type: str) -> Transcript:
        self.requests.append((audio, content_type))
        if self.fail:
            raise RuntimeError("fake STT failure")
        return self.transcript


class FakeStreamingSpeechToTextSession:
    def __init__(
        self,
        scripted_events: Sequence[Sequence[StreamingTranscriptEvent]],
        *,
        fail_on_audio: bool = False,
    ) -> None:
        self.scripted_events = [tuple(events) for events in scripted_events]
        self.fail_on_audio = fail_on_audio
        self.sent_audio: list[bytes] = []
        self.closed = False

    def send_audio(self, audio: bytes) -> Sequence[StreamingTranscriptEvent]:
        self.sent_audio.append(audio)
        if self.fail_on_audio:
            raise RuntimeError("fake streaming STT failure")
        if not self.scripted_events:
            return ()
        return self.scripted_events.pop(0)

    def poll_events(self) -> Sequence[StreamingTranscriptEvent]:
        if not self.scripted_events:
            return ()
        return self.scripted_events.pop(0)

    def close(self) -> Sequence[StreamingTranscriptEvent]:
        self.closed = True
        return (StreamingTranscriptEvent(type="session_close"),)


class FakeStreamingSpeechToTextProvider:
    def __init__(
        self,
        scripted_events: Sequence[Sequence[StreamingTranscriptEvent]] = (),
        *,
        fail_on_audio: bool = False,
    ) -> None:
        self.scripted_events = tuple(tuple(events) for events in scripted_events)
        self.fail_on_audio = fail_on_audio
        self.sessions: list[FakeStreamingSpeechToTextSession] = []

    def start_stream(self) -> FakeStreamingSpeechToTextSession:
        session = FakeStreamingSpeechToTextSession(
            self.scripted_events,
            fail_on_audio=self.fail_on_audio,
        )
        self.sessions.append(session)
        return session


class FakeTextToSpeechProvider:
    def __init__(self, content_type: str = "audio/wav", *, fail: bool = False) -> None:
        self.content_type = content_type
        self.fail = fail
        self.requests: list[tuple[str, str | None]] = []

    def synthesize(self, text: str, *, voice: str | None = None) -> SynthesizedSpeech:
        self.requests.append((text, voice))
        if self.fail:
            raise RuntimeError("fake TTS failure")
        return SynthesizedSpeech(
            audio=f"fake audio: {text}".encode(),
            content_type=self.content_type,
        )


class FakeVoiceSessionProvider:
    def __init__(self) -> None:
        self.sessions: dict[str, VoiceSession] = {}
        self.sent_audio: list[tuple[str, bytes, str]] = []
        self.closed_sessions: list[str] = []

    def start_session(self, session_id: str, *, caller_phone: str | None = None) -> VoiceSession:
        session = VoiceSession(session_id=session_id, caller_phone=caller_phone)
        self.sessions[session_id] = session
        return session

    def send_audio(self, session_id: str, audio: bytes, *, content_type: str) -> None:
        if session_id not in self.sessions:
            raise KeyError(f"Unknown voice session: {session_id}")
        self.sent_audio.append((session_id, audio, content_type))

    def close_session(self, session_id: str) -> None:
        if session_id not in self.sessions:
            raise KeyError(f"Unknown voice session: {session_id}")
        self.closed_sessions.append(session_id)


class FakePropertyRepository:
    def __init__(
        self,
        *,
        properties: Sequence[PropertyRecord] = (),
        units: Sequence[UnitRecord] = (),
    ) -> None:
        self.properties = tuple(properties)
        self.units = tuple(units)

    def list_properties(self) -> Sequence[PropertyRecord]:
        return self.properties

    def search_properties(self, query: str) -> Sequence[PropertyRecord]:
        normalized_query = query.casefold()
        return tuple(
            property_
            for property_ in self.properties
            if normalized_query in property_.name.casefold()
            or normalized_query in property_.address.casefold()
            or normalized_query in property_.city.casefold()
        )

    def list_units(self, property_id: str) -> Sequence[UnitRecord]:
        return tuple(unit for unit in self.units if unit.property_id == property_id)

    def get_unit(self, unit_id: str) -> UnitRecord | None:
        return next((unit for unit in self.units if unit.id == unit_id), None)


class FakeProspectRepository:
    def __init__(self) -> None:
        self.prospects_by_phone: dict[str, ProspectRecord] = {}
        self.interests: list[ProspectInterestRecord] = []

    def upsert_prospect(self, *, name: str, phone: str, email: str | None = None) -> ProspectRecord:
        phone_key = _phone_key(phone)
        existing = self.prospects_by_phone.get(phone_key)
        prospect_id = existing.id if existing else f"prospect-{len(self.prospects_by_phone) + 1}"
        prospect = ProspectRecord(id=prospect_id, name=name, phone=phone, email=email)
        self.prospects_by_phone[phone_key] = prospect
        return prospect

    def record_interest(
        self,
        *,
        prospect_id: str,
        property_id: str | None = None,
        unit_id: str | None = None,
        source: str = "voice_call",
        notes: str | None = None,
    ) -> ProspectInterestRecord:
        target_key = unit_id or property_id
        existing = next(
            (
                interest
                for interest in self.interests
                if interest.prospect_id == prospect_id
                and interest.source == source
                and (interest.unit_id or interest.property_id) == target_key
            ),
            None,
        )
        if existing is not None:
            updated = ProspectInterestRecord(
                id=existing.id,
                prospect_id=existing.prospect_id,
                property_id=property_id,
                unit_id=unit_id,
                source=source,
                status=existing.status,
                notes=notes or existing.notes,
            )
            self.interests[self.interests.index(existing)] = updated
            return updated
        interest = ProspectInterestRecord(
            id=f"interest-{len(self.interests) + 1}",
            prospect_id=prospect_id,
            property_id=property_id,
            unit_id=unit_id,
            source=source,
            notes=notes,
        )
        self.interests.append(interest)
        return interest


class FakeKnowledgeRetriever:
    def __init__(self, snippets: Sequence[KnowledgeSnippet] = ()) -> None:
        self.snippets = tuple(snippets)
        self.queries: list[tuple[str, int]] = []

    def retrieve(self, query: str, *, limit: int = 5) -> Sequence[KnowledgeSnippet]:
        self.queries.append((query, limit))
        query_terms = query.casefold().split()
        matches = tuple(
            snippet
            for snippet in self.snippets
            if any(term in snippet.text.casefold() for term in query_terms)
        )
        return matches[:limit]


def _phone_key(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    return digits[-10:] if len(digits) == 11 and digits.startswith("1") else digits
