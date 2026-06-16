from leasing_voice_assistant.fakes import FakeProspectRepository
from leasing_voice_assistant.interfaces import ProspectRecord
from leasing_voice_assistant.property_resolution import PropertyResolutionState
from leasing_voice_assistant.prospect_capture import (
    ProspectCaptureRequest,
    ProspectCaptureService,
    ProspectCaptureState,
)


def resolved_property_state() -> PropertyResolutionState:
    return PropertyResolutionState(
        confidence="resolved",
        property_id="property-lakeview-flats",
        property_name="Lakeview Flats",
        write_ready=True,
        clarification_needed=False,
        clarification_reason="none",
    )


def resolved_unit_state() -> PropertyResolutionState:
    return PropertyResolutionState(
        confidence="resolved",
        property_id="property-lakeview-flats",
        property_name="Lakeview Flats",
        unit_id="unit-lakeview-2b",
        unit_label="2B",
        write_ready=True,
        clarification_needed=False,
        clarification_reason="none",
    )


def ambiguous_state() -> PropertyResolutionState:
    return PropertyResolutionState(
        confidence="ambiguous",
        write_ready=False,
        clarification_needed=True,
        clarification_reason="ambiguous_property",
    )


def test_blocks_write_when_name_is_missing() -> None:
    service = ProspectCaptureService(FakeProspectRepository())

    result = service.process(
        ProspectCaptureRequest(
            user_text="I am interested in Lakeview Flats. My phone is 555-123-4567.",
            resolution=resolved_property_state(),
        )
    )

    assert result.outcome == "blocked"
    assert result.reason == "missing_name"
    assert result.prompt == "What name should I put on the prospect record?"


def test_blocks_write_when_phone_is_missing() -> None:
    service = ProspectCaptureService(FakeProspectRepository())

    result = service.process(
        ProspectCaptureRequest(
            user_text="My name is Avery Lee and I am interested in Lakeview Flats.",
            resolution=resolved_property_state(),
        )
    )

    assert result.outcome == "blocked"
    assert result.reason == "missing_phone"
    assert result.prompt == "What phone number should the leasing team use?"


def test_blocks_write_when_property_is_ambiguous() -> None:
    service = ProspectCaptureService(FakeProspectRepository())

    result = service.process(
        ProspectCaptureRequest(
            user_text=("My name is Avery Lee, my phone is 555-123-4567, and I am interested."),
            resolution=ambiguous_state(),
        )
    )

    assert result.outcome == "blocked"
    assert result.reason == "target_not_write_ready"


def test_unclear_intent_requires_confirmation_without_writing() -> None:
    repository = FakeProspectRepository()
    service = ProspectCaptureService(repository)

    result = service.process(
        ProspectCaptureRequest(
            user_text="My name is Avery Lee and my phone is 555-123-4567.",
            resolution=resolved_property_state(),
        )
    )

    assert result.outcome == "needs_confirmation"
    assert result.reason == "unclear_intent"
    assert result.state.pending_confirmation is not None
    assert repository.interests == []


def test_garbled_or_low_confidence_turn_requires_confirmation_without_writing() -> None:
    repository = FakeProspectRepository()
    service = ProspectCaptureService(repository)

    result = service.process(
        ProspectCaptureRequest(
            user_text=(
                "My name is Avery Lee, my phone is 555-123-4567, "
                "and I am interested in this. [inaudible]"
            ),
            resolution=resolved_property_state(),
            transcript_confidence=0.42,
        )
    )

    assert result.outcome == "needs_confirmation"
    assert result.reason == "low_transcript_confidence"
    assert result.state.pending_confirmation is not None
    assert repository.interests == []


def test_explicit_confirmation_writes_pending_interest() -> None:
    repository = FakeProspectRepository()
    service = ProspectCaptureService(repository)

    first = service.process(
        ProspectCaptureRequest(
            user_text="My name is Avery Lee and my phone is 555-123-4567.",
            resolution=resolved_property_state(),
        )
    )
    second = service.process(
        ProspectCaptureRequest(
            user_text="yes",
            resolution=resolved_property_state(),
            prior_state=first.state,
        )
    )

    assert second.outcome == "written"
    assert second.reason == "none"
    assert second.prospect is not None
    assert second.prospect.name == "Avery Lee"
    assert second.interest is not None
    assert second.interest.property_id == "property-lakeview-flats"
    assert second.interest.unit_id is None


def test_clear_intent_writes_unit_level_interest() -> None:
    repository = FakeProspectRepository()
    service = ProspectCaptureService(repository)

    result = service.process(
        ProspectCaptureRequest(
            user_text=(
                "My name is Avery Lee, my phone is 555-123-4567, and I am interested in this unit."
            ),
            resolution=resolved_unit_state(),
        )
    )

    assert result.outcome == "written"
    assert result.interest is not None
    assert result.interest.property_id == "property-lakeview-flats"
    assert result.interest.unit_id == "unit-lakeview-2b"
    assert result.interest.notes == "Confirmed interest in Lakeview Flats unit 2B."


def test_caller_phone_metadata_is_used_for_upsert_and_duplicate_interest() -> None:
    repository = FakeProspectRepository()
    repository.prospects_by_phone["5551234567"] = ProspectRecord(
        id="prospect-existing",
        name="Avery Old",
        phone="5551234567",
    )
    service = ProspectCaptureService(repository)

    first = service.process(
        ProspectCaptureRequest(
            user_text="My name is Avery Lee and I am interested in this property.",
            resolution=resolved_property_state(),
            caller_phone="+1 (555) 123-4567",
        )
    )
    second = service.process(
        ProspectCaptureRequest(
            user_text="My name is Avery Lee and I am interested in this property.",
            resolution=resolved_property_state(),
            caller_phone="+1 (555) 123-4567",
            prior_state=first.state,
        )
    )

    assert first.outcome == "written"
    assert second.outcome == "written"
    assert first.prospect is not None
    assert first.prospect.id == "prospect-existing"
    assert len(repository.prospects_by_phone) == 1
    assert len(repository.interests) == 1


def test_changed_details_invalidate_pending_confirmation() -> None:
    repository = FakeProspectRepository()
    service = ProspectCaptureService(repository)

    first = service.process(
        ProspectCaptureRequest(
            user_text="My name is Avery Lee and my phone is 555-123-4567.",
            resolution=resolved_property_state(),
        )
    )
    changed_resolution = PropertyResolutionState(
        confidence="resolved",
        property_id="property-cedar-park-townhomes",
        property_name="Cedar Park Townhomes",
        write_ready=True,
        clarification_needed=False,
        clarification_reason="none",
    )
    second = service.process(
        ProspectCaptureRequest(
            user_text="yes",
            resolution=changed_resolution,
            prior_state=ProspectCaptureState(
                name=first.state.name,
                phone=first.state.phone,
                pending_confirmation=first.state.pending_confirmation,
            ),
        )
    )

    assert second.outcome == "needs_confirmation"
    assert second.reason == "unclear_intent"
    assert repository.interests == []
