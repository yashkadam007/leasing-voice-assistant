"""Property and unit repository."""

from dataclasses import dataclass

from sqlalchemy import Select, and_, or_, select
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

        normalized_unit_number = normalize_unit_number(query)
        terms = [
            normalized,
            *(
                token
                for token in normalized.split()
                if len(token) > 2 and token not in _QUERY_STOPWORDS
            ),
        ]
        if normalized_unit_number is not None:
            terms.append(normalized_unit_number.lower())

        search_filters = []
        for term in terms:
            like = f"%{term}%"
            search_filters.extend(
                [
                    Property.name.ilike(like),
                    Property.address.ilike(like),
                    Property.city.ilike(like),
                    Property.description.ilike(like),
                    Unit.unit_number.ilike(like),
                    Unit.status.ilike(like),
                    Unit.view.ilike(like),
                    Unit.notes.ilike(like),
                ]
            )

        statement: Select[tuple[Property]] = (
            select(Property)
            .options(selectinload(Property.units))
            .outerjoin(Unit)
            .where(or_(*search_filters))
            .distinct()
            .order_by(Property.name)
            .limit(limit)
        )
        properties = self.session.scalars(statement).all()
        named_properties = [
            property_ for property_ in properties if property_.name.strip().lower() in normalized
        ]
        if named_properties:
            properties = named_properties

        return [
            PropertySearchResult(
                property=property_,
                matched_units=tuple(
                    unit
                    for unit in property_.units
                    if self._unit_matches(unit, normalized, normalized_unit_number)
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

    def get_unit(self, unit_id: int) -> Unit | None:
        """Return an authoritative unit and its property by database id."""
        return self.session.scalar(
            select(Unit).options(selectinload(Unit.property)).where(Unit.id == unit_id)
        )

    def list_property_identifiers(self) -> list[tuple[int, str, str, str]]:
        """Return stable property names and locations for deterministic parsing."""
        return list(
            self.session.execute(
                select(Property.id, Property.name, Property.city, Property.state).order_by(
                    Property.name
                )
            ).all()
        )

    def search_constraints(
        self,
        query: str,
        *,
        property_names: tuple[str, ...] = (),
        locations: tuple[str, ...] = (),
        bedroom_count: int | None = None,
        minimum_rent_cents: int | None = None,
        maximum_rent_cents: int | None = None,
        available_only: bool = False,
        limit: int = 3,
    ) -> list[PropertySearchResult]:
        """Search and enforce supported structured unit constraints."""
        structured = any(
            (
                property_names,
                locations,
                bedroom_count is not None,
                minimum_rent_cents is not None,
                maximum_rent_cents is not None,
                available_only,
            )
        )
        if not structured:
            return self.search(query, limit=limit)

        filters = []
        if property_names:
            filters.append(or_(*(Property.name.ilike(name) for name in property_names)))
        if locations:
            filters.append(
                or_(
                    *(
                        or_(Property.city.ilike(location), Property.state.ilike(location))
                        for location in locations
                    )
                )
            )
        unit_filters = []
        if bedroom_count is not None:
            unit_filters.append(Unit.bedroom_count == bedroom_count)
        if minimum_rent_cents is not None:
            unit_filters.append(Unit.rent_cents >= minimum_rent_cents)
        if maximum_rent_cents is not None:
            unit_filters.append(Unit.rent_cents <= maximum_rent_cents)
        if available_only:
            unit_filters.append(Unit.status == "available")
        if unit_filters:
            filters.append(and_(*unit_filters))
        statement = (
            select(Property)
            .options(selectinload(Property.units))
            .join(Unit)
            .where(and_(*filters))
            .distinct()
            .order_by(Property.name)
            .limit(limit)
        )
        properties = self.session.scalars(statement).all()
        return [
            PropertySearchResult(
                property=item,
                matched_units=tuple(
                    unit
                    for unit in item.units
                    if (bedroom_count is None or unit.bedroom_count == bedroom_count)
                    and (minimum_rent_cents is None or unit.rent_cents >= minimum_rent_cents)
                    and (maximum_rent_cents is None or unit.rent_cents <= maximum_rent_cents)
                    and (not available_only or unit.status == "available")
                ),
            )
            for item in properties
        ]

    def get_units_by_number(self, unit_number: str) -> list[Unit]:
        """Return exact unit facts by caller-facing unit number."""
        normalized_unit_number = normalize_unit_number(unit_number)
        if not normalized_unit_number:
            return []

        statement = (
            select(Unit)
            .options(selectinload(Unit.property))
            .where(Unit.unit_number == normalized_unit_number)
            .order_by(Unit.unit_number)
        )
        return list(self.session.scalars(statement).all())

    def get_unit_by_number(self, property_id: int, unit_number: str) -> Unit | None:
        """Return exact unit facts by property and unit number."""
        normalized_unit_number = normalize_unit_number(unit_number)
        if not normalized_unit_number:
            return None

        statement = (
            select(Unit)
            .options(selectinload(Unit.property))
            .where(
                Unit.property_id == property_id,
                Unit.unit_number == normalized_unit_number,
            )
        )
        return self.session.scalar(statement)

    @staticmethod
    def _unit_matches(
        unit: Unit,
        normalized_query: str,
        normalized_unit_number: str | None = None,
    ) -> bool:
        fields = (
            unit.unit_number,
            unit.status,
            unit.view,
            unit.notes,
            str(unit.bedroom_count),
        )
        return any(normalized_query in field.lower() for field in fields) or (
            normalized_unit_number is not None
            and normalized_unit_number.lower() in unit.unit_number.lower()
        )


_NUMBER_WORDS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "to": "2",
    "too": "2",
    "three": "3",
    "four": "4",
    "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
}

_UNIT_MARKERS = {
    "apartment",
    "apartments",
    "apt",
    "apts",
    "home",
    "homes",
    "unit",
    "units",
    "number",
    "no",
}
_QUERY_STOPWORDS = _UNIT_MARKERS | {"about", "and", "are", "available", "for", "the", "with"}


def normalize_unit_number(value: str) -> str | None:
    """Normalize caller-facing unit phrases like 'unit eight a' to '8A'."""
    tokens = _unit_tokens(value)
    if not tokens:
        return None

    normalized_parts: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        number = _NUMBER_WORDS.get(token)
        if (
            number is not None
            and int(number) >= 20
            and index + 1 < len(tokens)
            and (ones := _NUMBER_WORDS.get(tokens[index + 1])) is not None
            and int(ones) < 10
        ):
            normalized_parts.append(str(int(number) + int(ones)))
            index += 2
            continue
        normalized_parts.append(number if number is not None else token)
        index += 1
    normalized = "".join(normalized_parts).upper()
    return normalized if any(character.isdigit() for character in normalized) else None


def _unit_tokens(value: str) -> list[str]:
    clean_text = "".join(
        character.lower() if character.isalnum() else " " for character in value.strip()
    )
    tokens = clean_text.split()
    if not tokens:
        return []

    for index, token in enumerate(tokens):
        if token in _UNIT_MARKERS:
            return [part for part in tokens[index + 1 :] if part not in _UNIT_MARKERS]

    return tokens
