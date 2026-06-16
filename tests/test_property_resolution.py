from pathlib import Path

from leasing_voice_assistant.database_tools import DatabaseQueryTools
from leasing_voice_assistant.persistence import SQLitePropertyRepository, initialize_database
from leasing_voice_assistant.property_resolution import PropertyResolutionState, PropertyResolver


def create_resolver(tmp_path: Path) -> PropertyResolver:
    connection = initialize_database(tmp_path / "test.sqlite3")
    return PropertyResolver(DatabaseQueryTools(SQLitePropertyRepository(connection)))


def test_resolves_exact_property_reference(tmp_path: Path) -> None:
    resolver = create_resolver(tmp_path)

    state = resolver.resolve("I want to know about Lakeview Flats")

    assert state.confidence == "resolved"
    assert state.property_id == "property-lakeview-flats"
    assert state.property_name == "Lakeview Flats"
    assert state.unit_id is None
    assert state.write_ready is True
    assert state.clarification_needed is False


def test_reuses_resolved_context_for_pronoun_reference(tmp_path: Path) -> None:
    resolver = create_resolver(tmp_path)
    prior = resolver.resolve("Lakeview Flats")

    state = resolver.resolve("Is that one available?", prior_state=prior)

    assert state.confidence == "ambiguous"
    assert state.property_id == "property-lakeview-flats"
    assert state.clarification_needed is True
    assert state.clarification_reason == "ambiguous_unit"
    assert {candidate.unit.id for candidate in state.unit_candidates} == {
        "unit-lakeview-1a",
        "unit-lakeview-2b",
    }


def test_narrows_lake_facing_unit_from_resolved_property_context(tmp_path: Path) -> None:
    resolver = create_resolver(tmp_path)
    prior = resolver.resolve("Tell me about Lakeview Flats")

    state = resolver.resolve("What about the lake-facing one?", prior_state=prior)

    assert state.confidence == "resolved"
    assert state.property_id == "property-lakeview-flats"
    assert state.unit_id == "unit-lakeview-2b"
    assert state.unit_label == "2B"
    assert state.write_ready is True
    assert state.clarification_needed is False


def test_marks_multiple_property_matches_ambiguous(tmp_path: Path) -> None:
    resolver = create_resolver(tmp_path)

    state = resolver.resolve("a")

    assert state.confidence == "ambiguous"
    assert state.property_id is None
    assert state.write_ready is False
    assert state.clarification_needed is True
    assert state.clarification_reason == "ambiguous_property"
    assert {candidate.property.id for candidate in state.candidates} == {
        "property-lakeview-flats",
        "property-cedar-park-townhomes",
    }


def test_returns_unresolved_for_no_match(tmp_path: Path) -> None:
    resolver = create_resolver(tmp_path)

    state = resolver.resolve("Do you have anything in Seattle?")

    assert state == PropertyResolutionState()


def test_downgrades_to_ambiguous_when_unit_hint_matches_multiple_units(tmp_path: Path) -> None:
    resolver = create_resolver(tmp_path)
    prior = resolver.resolve("Lakeview Flats")

    state = resolver.resolve("Is an available one open?", prior_state=prior)

    assert state.confidence == "ambiguous"
    assert state.property_id == "property-lakeview-flats"
    assert state.unit_id is None
    assert state.write_ready is False
    assert state.clarification_reason == "ambiguous_unit"


def test_new_explicit_property_replaces_prior_context(tmp_path: Path) -> None:
    resolver = create_resolver(tmp_path)
    prior = resolver.resolve("Lakeview Flats")

    state = resolver.resolve("Actually Cedar Park Townhomes", prior_state=prior)

    assert state.confidence == "resolved"
    assert state.property_id == "property-cedar-park-townhomes"
    assert state.property_name == "Cedar Park Townhomes"
    assert state.unit_id is None
