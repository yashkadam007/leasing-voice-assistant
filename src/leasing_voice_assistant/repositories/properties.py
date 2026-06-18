"""Property and unit repository."""

from dataclasses import dataclass

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from leasing_voice_assistant.db.models import Property, Unit


@dataclass(frozen=True)
class PropertySearchResult:
    """Search result containing a property and any directly matched units."""

    property: Property
    matched_units: tuple[Unit, ...]


class PropertiesRepository:
    """Read repository for property and unit facts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: str, *, limit: int = 5) -> list[PropertySearchResult]:
        """Search properties and units using caller-facing text."""
        normalized = query.strip().lower()
        if not normalized:
            return []

        like = f"%{normalized}%"
        statement: Select[tuple[Property]] = (
            select(Property)
            .options(selectinload(Property.units))
            .outerjoin(Unit)
            .where(
                or_(
                    Property.name.ilike(like),
                    Property.address.ilike(like),
                    Property.city.ilike(like),
                    Property.description.ilike(like),
                    Unit.unit_number.ilike(like),
                    Unit.status.ilike(like),
                    Unit.view.ilike(like),
                    Unit.notes.ilike(like),
                )
            )
            .distinct()
            .order_by(Property.name)
            .limit(limit)
        )
        properties = self.session.scalars(statement).all()

        return [
            PropertySearchResult(
                property=property_,
                matched_units=tuple(
                    unit for unit in property_.units if self._unit_matches(unit, normalized)
                ),
            )
            for property_ in properties
        ]

    def get_property(self, property_id: int) -> Property | None:
        """Return a property and its units by id."""
        statement = (
            select(Property).options(selectinload(Property.units)).where(Property.id == property_id)
        )
        return self.session.scalar(statement)

    def get_unit_details(self, unit_id: int) -> Unit | None:
        """Return exact unit facts by unit id."""
        statement = select(Unit).options(selectinload(Unit.property)).where(Unit.id == unit_id)
        return self.session.scalar(statement)

    def get_unit_by_number(self, property_id: int, unit_number: str) -> Unit | None:
        """Return exact unit facts by property and unit number."""
        statement = (
            select(Unit)
            .options(selectinload(Unit.property))
            .where(
                Unit.property_id == property_id,
                Unit.unit_number == unit_number.strip(),
            )
        )
        return self.session.scalar(statement)

    @staticmethod
    def _unit_matches(unit: Unit, normalized_query: str) -> bool:
        fields = (
            unit.unit_number,
            unit.status,
            unit.view,
            unit.notes,
            str(unit.bedroom_count),
        )
        return any(normalized_query in field.lower() for field in fields)
