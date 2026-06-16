from leasing_voice_assistant.fakes import (
    FakeKnowledgeRetriever,
    FakeModelProvider,
    FakePropertyRepository,
    FakeProspectRepository,
    FakeSpeechToTextProvider,
    FakeTextToSpeechProvider,
    FakeVoiceSessionProvider,
)
from leasing_voice_assistant.interfaces import (
    KnowledgeSnippet,
    ModelMessage,
    PropertyRecord,
    Transcript,
    UnitRecord,
)


def test_fake_model_provider_returns_configured_response() -> None:
    provider = FakeModelProvider(response_text="hello")

    response = provider.generate([ModelMessage(role="user", content="Hi")])

    assert response.text == "hello"
    assert len(provider.requests) == 1


def test_fake_speech_providers_are_deterministic() -> None:
    stt = FakeSpeechToTextProvider(Transcript(text="I want the lake unit", confidence=0.95))
    tts = FakeTextToSpeechProvider()

    transcript = stt.transcribe(b"audio", content_type="audio/wav")
    speech = tts.synthesize("Sure", voice="demo")

    assert transcript == Transcript(text="I want the lake unit", confidence=0.95)
    assert speech.audio == b"fake audio: Sure"
    assert speech.content_type == "audio/wav"
    assert stt.requests == [(b"audio", "audio/wav")]
    assert tts.requests == [("Sure", "demo")]


def test_fake_voice_session_records_audio_and_closure() -> None:
    provider = FakeVoiceSessionProvider()

    session = provider.start_session("session-1", caller_phone="+15551234567")
    provider.send_audio("session-1", b"audio", content_type="audio/wav")
    provider.close_session("session-1")

    assert session.session_id == "session-1"
    assert provider.sent_audio == [("session-1", b"audio", "audio/wav")]
    assert provider.closed_sessions == ["session-1"]


def test_fake_property_repository_searches_and_lists_units() -> None:
    property_ = PropertyRecord(
        id="property-1",
        name="Lakeview Flats",
        address="1 Lake Street",
        city="Austin",
    )
    unit = UnitRecord(
        id="unit-1",
        property_id="property-1",
        label="2A",
        bedrooms=2,
        bathrooms=2.0,
        monthly_rent=2400,
        status="available",
        view="lake",
    )
    repository = FakePropertyRepository(properties=[property_], units=[unit])

    assert repository.search_properties("lake") == (property_,)
    assert repository.list_units("property-1") == (unit,)
    assert repository.get_unit("unit-1") == unit
    assert repository.get_unit("missing") is None


def test_fake_prospect_repository_upserts_by_phone_and_records_interest() -> None:
    repository = FakeProspectRepository()

    first = repository.upsert_prospect(name="Avery", phone="+15551234567")
    second = repository.upsert_prospect(name="Avery Lee", phone="+15551234567")
    interest = repository.record_interest(
        prospect_id=second.id,
        property_id="property-1",
        unit_id="unit-1",
        notes="Interested in lake view",
    )

    assert second.id == first.id
    assert second.name == "Avery Lee"
    assert interest.prospect_id == first.id
    assert interest.property_id == "property-1"
    assert interest.unit_id == "unit-1"
    assert len(repository.interests) == 1


def test_fake_knowledge_retriever_returns_limited_matches() -> None:
    retriever = FakeKnowledgeRetriever(
        [
            KnowledgeSnippet(source_id="faq-1", text="Pets are allowed with a deposit.", score=0.8),
            KnowledgeSnippet(
                source_id="faq-2",
                text="Applications are reviewed online.",
                score=0.7,
            ),
        ]
    )

    results = retriever.retrieve("pet policy application", limit=1)

    assert results == (
        KnowledgeSnippet(source_id="faq-1", text="Pets are allowed with a deposit.", score=0.8),
    )
    assert retriever.queries == [("pet policy application", 1)]
