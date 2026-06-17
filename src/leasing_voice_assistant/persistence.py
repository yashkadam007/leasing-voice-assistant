from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Sequence
from pathlib import Path

from leasing_voice_assistant.interfaces import (
    PropertyRecord,
    ProspectInterestRecord,
    ProspectRecord,
    UnitRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MIGRATIONS_DIR = PROJECT_ROOT / "data" / "migrations"
DEFAULT_SEED_PATH = PROJECT_ROOT / "data" / "seeds" / "properties.json"
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "runtime" / "leasing_voice_assistant.sqlite3"


def connect_database(database_path: Path | str = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    path = Path(database_path)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def apply_migrations(
    connection: sqlite3.Connection,
    migrations_dir: Path | str = DEFAULT_MIGRATIONS_DIR,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    applied = {
        row["version"]
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for migration_path in sorted(Path(migrations_dir).glob("*.sql")):
        version = migration_path.stem
        if version in applied:
            continue
        with connection:
            connection.executescript(migration_path.read_text())
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )


def load_seed_data(
    connection: sqlite3.Connection,
    seed_path: Path | str = DEFAULT_SEED_PATH,
) -> None:
    payload = json.loads(Path(seed_path).read_text())
    with connection:
        for property_payload in payload["properties"]:
            connection.execute(
                """
                INSERT INTO properties (id, name, address, city)
                VALUES (:id, :name, :address, :city)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    address = excluded.address,
                    city = excluded.city
                """,
                property_payload,
            )
            for unit_payload in property_payload["units"]:
                unit_values = dict(unit_payload)
                unit_values["property_id"] = property_payload["id"]
                unit_values["amenities_json"] = json.dumps(unit_values.pop("amenities"))
                connection.execute(
                    """
                    INSERT INTO units (
                        id,
                        property_id,
                        label,
                        bedrooms,
                        bathrooms,
                        sqft,
                        monthly_rent,
                        available_from,
                        view,
                        parking,
                        pet_policy,
                        amenities_json,
                        status
                    )
                    VALUES (
                        :id,
                        :property_id,
                        :label,
                        :bedrooms,
                        :bathrooms,
                        :sqft,
                        :monthly_rent,
                        :available_from,
                        :view,
                        :parking,
                        :pet_policy,
                        :amenities_json,
                        :status
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        property_id = excluded.property_id,
                        label = excluded.label,
                        bedrooms = excluded.bedrooms,
                        bathrooms = excluded.bathrooms,
                        sqft = excluded.sqft,
                        monthly_rent = excluded.monthly_rent,
                        available_from = excluded.available_from,
                        view = excluded.view,
                        parking = excluded.parking,
                        pet_policy = excluded.pet_policy,
                        amenities_json = excluded.amenities_json,
                        status = excluded.status
                    """,
                    unit_values,
                )


def initialize_database(
    database_path: Path | str = DEFAULT_DATABASE_PATH,
    *,
    migrations_dir: Path | str = DEFAULT_MIGRATIONS_DIR,
    seed_path: Path | str = DEFAULT_SEED_PATH,
) -> sqlite3.Connection:
    connection = connect_database(database_path)
    apply_migrations(connection, migrations_dir)
    load_seed_data(connection, seed_path)
    return connection


class SQLitePropertyRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_properties(self) -> Sequence[PropertyRecord]:
        rows = self.connection.execute(
            """
            SELECT id, name, address, city
            FROM properties
            ORDER BY name
            """
        ).fetchall()
        return tuple(_property_from_row(row) for row in rows)

    def search_properties(self, query: str) -> Sequence[PropertyRecord]:
        pattern = f"%{query.strip()}%"
        rows = self.connection.execute(
            """
            SELECT id, name, address, city
            FROM properties
            WHERE name LIKE ? OR address LIKE ? OR city LIKE ?
            ORDER BY name
            """,
            (pattern, pattern, pattern),
        ).fetchall()
        return tuple(_property_from_row(row) for row in rows)

    def list_units(self, property_id: str) -> Sequence[UnitRecord]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM units
            WHERE property_id = ?
            ORDER BY status = 'available' DESC, monthly_rent, label
            """,
            (property_id,),
        ).fetchall()
        return tuple(_unit_from_row(row) for row in rows)

    def get_unit(self, unit_id: str) -> UnitRecord | None:
        row = self.connection.execute(
            "SELECT * FROM units WHERE id = ?",
            (unit_id,),
        ).fetchone()
        return _unit_from_row(row) if row is not None else None


class SQLiteProspectRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert_prospect(self, *, name: str, phone: str, email: str | None = None) -> ProspectRecord:
        normalized_phone = normalize_phone(phone)
        prospect_id = f"prospect-{uuid.uuid4()}"
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO prospects (id, name, phone, normalized_phone, email)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(normalized_phone) DO UPDATE SET
                    name = excluded.name,
                    phone = excluded.phone,
                    email = COALESCE(excluded.email, prospects.email),
                    updated_at = datetime('now')
                """,
                (prospect_id, name.strip(), phone.strip(), normalized_phone, email),
            )
        row = self.connection.execute(
            "SELECT id, name, phone, email FROM prospects WHERE normalized_phone = ?",
            (normalized_phone,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Prospect upsert did not return a row")
        return _prospect_from_row(row)

    def record_interest(
        self,
        *,
        prospect_id: str,
        property_id: str | None = None,
        unit_id: str | None = None,
        source: str = "voice_call",
        notes: str | None = None,
    ) -> ProspectInterestRecord:
        target_key = _target_key(property_id=property_id, unit_id=unit_id)
        interest_id = f"interest-{uuid.uuid4()}"
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO prospect_interests (
                    id,
                    prospect_id,
                    property_id,
                    unit_id,
                    target_key,
                    source,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(prospect_id, source, target_key) DO UPDATE SET
                    notes = COALESCE(excluded.notes, prospect_interests.notes)
                """,
                (interest_id, prospect_id, property_id, unit_id, target_key, source, notes),
            )
        row = self.connection.execute(
            """
            SELECT id, prospect_id, property_id, unit_id, source, status, notes
            FROM prospect_interests
            WHERE prospect_id = ? AND source = ? AND target_key = ?
            """,
            (prospect_id, source, target_key),
        ).fetchone()
        if row is None:
            raise RuntimeError("Interest insert did not return a row")
        return _interest_from_row(row)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if not digits:
        raise ValueError("Phone number must contain at least one digit")
    if len(digits) == 10:
        return f"+1{digits}"
    return f"+{digits}"


def _target_key(*, property_id: str | None, unit_id: str | None) -> str:
    if unit_id is not None:
        return f"unit:{unit_id}"
    if property_id is not None:
        return f"property:{property_id}"
    raise ValueError("Interest must target a property or unit")


def _property_from_row(row: sqlite3.Row) -> PropertyRecord:
    return PropertyRecord(
        id=row["id"],
        name=row["name"],
        address=row["address"],
        city=row["city"],
    )


def _unit_from_row(row: sqlite3.Row) -> UnitRecord:
    amenities = json.loads(row["amenities_json"])
    return UnitRecord(
        id=row["id"],
        property_id=row["property_id"],
        label=row["label"],
        bedrooms=row["bedrooms"],
        bathrooms=row["bathrooms"],
        sqft=row["sqft"],
        monthly_rent=row["monthly_rent"],
        available_from=row["available_from"],
        view=row["view"],
        parking=row["parking"],
        pet_policy=row["pet_policy"],
        amenities=tuple(str(amenity) for amenity in amenities),
        status=row["status"],
    )


def _prospect_from_row(row: sqlite3.Row) -> ProspectRecord:
    return ProspectRecord(
        id=row["id"],
        name=row["name"],
        phone=row["phone"],
        email=row["email"],
    )


def _interest_from_row(row: sqlite3.Row) -> ProspectInterestRecord:
    return ProspectInterestRecord(
        id=row["id"],
        prospect_id=row["prospect_id"],
        property_id=row["property_id"],
        unit_id=row["unit_id"],
        source=row["source"],
        status=row["status"],
        notes=row["notes"],
    )
