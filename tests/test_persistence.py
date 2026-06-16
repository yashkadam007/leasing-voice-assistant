import sqlite3
from pathlib import Path

import pytest

from leasing_voice_assistant.persistence import (
    DEFAULT_MIGRATIONS_DIR,
    DEFAULT_SEED_PATH,
    SQLitePropertyRepository,
    SQLiteProspectRepository,
    apply_migrations,
    connect_database,
    initialize_database,
    load_seed_data,
    normalize_phone,
)

TABLE_NAMES = frozenset({"properties", "units", "prospects", "prospect_interests"})


def count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    if table_name not in TABLE_NAMES:
        raise ValueError(f"Unexpected table name: {table_name}")
    row = connection.execute(f"SELECT COUNT(*) AS row_count FROM {table_name}").fetchone()
    return int(row["row_count"])


def test_migrations_create_schema(tmp_path: Path) -> None:
    connection = connect_database(tmp_path / "test.sqlite3")

    apply_migrations(connection)

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {
        "schema_migrations",
        "properties",
        "units",
        "prospects",
        "prospect_interests",
    }.issubset(tables)


def test_seed_loading_is_idempotent(tmp_path: Path) -> None:
    connection = connect_database(tmp_path / "test.sqlite3")
    apply_migrations(connection, DEFAULT_MIGRATIONS_DIR)

    load_seed_data(connection, DEFAULT_SEED_PATH)
    load_seed_data(connection, DEFAULT_SEED_PATH)

    assert count_rows(connection, "properties") == 2
    assert count_rows(connection, "units") == 3


def test_property_repository_reads_seeded_property_and_units(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "test.sqlite3")
    repository = SQLitePropertyRepository(connection)

    properties = repository.search_properties("lake")
    units = repository.list_units("property-lakeview-flats")
    unit = repository.get_unit("unit-lakeview-2b")

    assert [property_.name for property_ in properties] == ["Lakeview Flats"]
    assert [unit.label for unit in units] == ["1A", "2B"]
    assert unit is not None
    assert unit.monthly_rent == 2450
    assert unit.bedrooms == 2
    assert unit.sqft == 1040
    assert unit.available_from == "2026-07-01"
    assert unit.view == "lake-facing"
    assert unit.parking == "one reserved garage space included"
    assert unit.pet_policy == "cats and dogs allowed with deposit"
    assert unit.amenities == ("balcony", "in-unit laundry", "fitness center")
    assert unit.status == "available"


def test_prospect_repository_upserts_by_normalized_phone(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "test.sqlite3")
    repository = SQLiteProspectRepository(connection)

    first = repository.upsert_prospect(name="Avery Lee", phone="(555) 123-4567")
    second = repository.upsert_prospect(
        name="Avery Morgan",
        phone="+1 555 123 4567",
        email="avery@example.test",
    )

    assert second.id == first.id
    assert second.name == "Avery Morgan"
    assert second.phone == "+1 555 123 4567"
    assert second.email == "avery@example.test"
    assert count_rows(connection, "prospects") == 1


def test_record_interest_is_idempotent_for_same_prospect_source_and_unit(
    tmp_path: Path,
) -> None:
    connection = initialize_database(tmp_path / "test.sqlite3")
    repository = SQLiteProspectRepository(connection)
    prospect = repository.upsert_prospect(name="Avery Lee", phone="5551234567")

    first = repository.record_interest(
        prospect_id=prospect.id,
        property_id="property-lakeview-flats",
        unit_id="unit-lakeview-2b",
        notes="Interested in the lake-facing two bedroom.",
    )
    second = repository.record_interest(
        prospect_id=prospect.id,
        property_id="property-lakeview-flats",
        unit_id="unit-lakeview-2b",
        notes="Confirmed interest.",
    )

    assert second.id == first.id
    assert second.prospect_id == prospect.id
    assert second.property_id == "property-lakeview-flats"
    assert second.unit_id == "unit-lakeview-2b"
    assert second.notes == "Confirmed interest."
    assert count_rows(connection, "prospect_interests") == 1


def test_record_interest_requires_property_or_unit(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "test.sqlite3")
    repository = SQLiteProspectRepository(connection)
    prospect = repository.upsert_prospect(name="Avery Lee", phone="5551234567")

    with pytest.raises(ValueError, match="property or unit"):
        repository.record_interest(prospect_id=prospect.id)


@pytest.mark.parametrize(
    ("raw_phone", "normalized_phone"),
    [
        ("555-123-4567", "+15551234567"),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_normalize_phone(raw_phone: str, normalized_phone: str) -> None:
    assert normalize_phone(raw_phone) == normalized_phone


def test_normalize_phone_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="at least one digit"):
        normalize_phone("not a phone")
