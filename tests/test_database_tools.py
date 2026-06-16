from pathlib import Path

from leasing_voice_assistant.database_tools import (
    DatabaseQueryTools,
    EvidenceItem,
    GetUnitFactsRequest,
    ListUnitsRequest,
    SearchPropertiesRequest,
)
from leasing_voice_assistant.persistence import SQLitePropertyRepository, initialize_database


def create_tools(tmp_path: Path) -> DatabaseQueryTools:
    connection = initialize_database(tmp_path / "test.sqlite3")
    return DatabaseQueryTools(SQLitePropertyRepository(connection))


def test_search_properties_returns_exact_match_with_evidence(tmp_path: Path) -> None:
    tools = create_tools(tmp_path)

    result = tools.search_properties(SearchPropertiesRequest(query="Lakeview Flats"))

    assert result.match_status == "exact"
    assert result.total_matches == 1
    assert result.returned_count == 1
    candidate = result.candidates[0]
    assert candidate.property.id == "property-lakeview-flats"
    assert candidate.confidence == "exact"
    assert (
        EvidenceItem(
            source="database.properties",
            record_id="property-lakeview-flats",
            field="name",
            value="Lakeview Flats",
        )
        in candidate.evidence
    )


def test_search_properties_marks_multiple_matches_ambiguous_and_enforces_limit(
    tmp_path: Path,
) -> None:
    tools = create_tools(tmp_path)

    result = tools.search_properties(SearchPropertiesRequest(query="a", limit=1))

    assert result.match_status == "ambiguous"
    assert result.total_matches == 2
    assert result.returned_count == 1
    assert result.limit == 1


def test_search_properties_returns_explicit_no_match(tmp_path: Path) -> None:
    tools = create_tools(tmp_path)

    result = tools.search_properties(SearchPropertiesRequest(query="does not exist"))

    assert result.match_status == "no_match"
    assert result.total_matches == 0
    assert result.returned_count == 0
    assert result.candidates == ()


def test_search_properties_empty_query_does_not_return_everything(tmp_path: Path) -> None:
    tools = create_tools(tmp_path)

    result = tools.search_properties(SearchPropertiesRequest(query="   "))

    assert result.match_status == "no_match"
    assert result.total_matches == 0
    assert result.candidates == ()


def test_list_units_returns_limited_structured_unit_facts(tmp_path: Path) -> None:
    tools = create_tools(tmp_path)

    result = tools.list_units(ListUnitsRequest(property_id="property-lakeview-flats", limit=1))

    assert result.property_id == "property-lakeview-flats"
    assert result.total_units == 2
    assert result.returned_count == 1
    unit = result.units[0].unit
    assert unit.id == "unit-lakeview-1a"
    assert unit.monthly_rent == 1825
    assert (
        EvidenceItem(
            source="database.units",
            record_id="unit-lakeview-1a",
            field="monthly_rent",
            value=1825,
        )
        in result.units[0].evidence
    )


def test_get_unit_facts_returns_complete_evidence(tmp_path: Path) -> None:
    tools = create_tools(tmp_path)

    result = tools.get_unit_facts(GetUnitFactsRequest(unit_id="unit-lakeview-2b"))

    assert result.found is True
    assert result.unit is not None
    assert result.unit.unit.label == "2B"
    assert {
        evidence.field: evidence.value
        for evidence in result.unit.evidence
        if evidence.field in {"monthly_rent", "view", "pet_policy", "amenities", "status"}
    } == {
        "monthly_rent": 2450,
        "view": "lake-facing",
        "pet_policy": "cats and dogs allowed with deposit",
        "amenities": ("balcony", "in-unit laundry", "fitness center"),
        "status": "available",
    }


def test_get_unit_facts_returns_not_found_without_fallback_facts(tmp_path: Path) -> None:
    tools = create_tools(tmp_path)

    result = tools.get_unit_facts(GetUnitFactsRequest(unit_id="missing-unit"))

    assert result.found is False
    assert result.unit is None
