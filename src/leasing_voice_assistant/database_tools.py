from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from leasing_voice_assistant.interfaces import PropertyRecord, PropertyRepository, UnitRecord

EvidenceValue = str | int | float | tuple[str, ...] | None
MatchConfidence = Literal["exact", "high", "possible"]
MatchStatus = Literal["exact", "ambiguous", "no_match"]

DEFAULT_PROPERTY_SEARCH_LIMIT = 5
DEFAULT_UNIT_LIST_LIMIT = 10
MAX_TOOL_LIMIT = 25


@dataclass(frozen=True)
class EvidenceItem:
    source: str
    record_id: str
    field: str
    value: EvidenceValue


@dataclass(frozen=True)
class SearchPropertiesRequest:
    query: str
    limit: int = DEFAULT_PROPERTY_SEARCH_LIMIT


@dataclass(frozen=True)
class ListPropertiesRequest:
    limit: int = DEFAULT_PROPERTY_SEARCH_LIMIT


@dataclass(frozen=True)
class PropertyCandidate:
    property: PropertyRecord
    confidence: MatchConfidence
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class PropertySearchResult:
    query: str
    limit: int
    total_matches: int
    returned_count: int
    match_status: MatchStatus
    candidates: tuple[PropertyCandidate, ...]


@dataclass(frozen=True)
class PropertyListResult:
    limit: int
    total_properties: int
    returned_count: int
    candidates: tuple[PropertyCandidate, ...]


@dataclass(frozen=True)
class ListUnitsRequest:
    property_id: str
    limit: int = DEFAULT_UNIT_LIST_LIMIT


@dataclass(frozen=True)
class UnitFacts:
    unit: UnitRecord
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class UnitListResult:
    property_id: str
    limit: int
    total_units: int
    returned_count: int
    units: tuple[UnitFacts, ...]


@dataclass(frozen=True)
class GetUnitFactsRequest:
    unit_id: str


@dataclass(frozen=True)
class UnitFactsResult:
    unit_id: str
    found: bool
    unit: UnitFacts | None


class DatabaseQueryTools:
    def __init__(self, property_repository: PropertyRepository) -> None:
        self.property_repository = property_repository

    def list_properties(self, request: ListPropertiesRequest) -> PropertyListResult:
        limit = _normalize_limit(request.limit)
        records = tuple(self.property_repository.list_properties())
        candidates = tuple(
            PropertyCandidate(
                property=record,
                confidence="exact",
                evidence=_property_evidence(record),
            )
            for record in records[:limit]
        )
        return PropertyListResult(
            limit=limit,
            total_properties=len(records),
            returned_count=len(candidates),
            candidates=candidates,
        )

    def search_properties(self, request: SearchPropertiesRequest) -> PropertySearchResult:
        query = request.query.strip()
        limit = _normalize_limit(request.limit)
        if not query:
            return PropertySearchResult(
                query=query,
                limit=limit,
                total_matches=0,
                returned_count=0,
                match_status="no_match",
                candidates=(),
            )

        records = tuple(self.property_repository.search_properties(query))
        candidates = tuple(
            PropertyCandidate(
                property=record,
                confidence=_property_confidence(record, query),
                evidence=_property_evidence(record),
            )
            for record in records[:limit]
        )
        return PropertySearchResult(
            query=query,
            limit=limit,
            total_matches=len(records),
            returned_count=len(candidates),
            match_status=_property_match_status(candidates, total_matches=len(records)),
            candidates=candidates,
        )

    def list_units(self, request: ListUnitsRequest) -> UnitListResult:
        property_id = request.property_id.strip()
        limit = _normalize_limit(request.limit)
        units = tuple(self.property_repository.list_units(property_id))
        unit_facts = tuple(_unit_facts(unit) for unit in units[:limit])
        return UnitListResult(
            property_id=property_id,
            limit=limit,
            total_units=len(units),
            returned_count=len(unit_facts),
            units=unit_facts,
        )

    def get_unit_facts(self, request: GetUnitFactsRequest) -> UnitFactsResult:
        unit_id = request.unit_id.strip()
        unit = self.property_repository.get_unit(unit_id)
        return UnitFactsResult(
            unit_id=unit_id,
            found=unit is not None,
            unit=_unit_facts(unit) if unit is not None else None,
        )


def _normalize_limit(limit: int) -> int:
    return min(max(limit, 1), MAX_TOOL_LIMIT)


def _property_match_status(
    candidates: tuple[PropertyCandidate, ...],
    *,
    total_matches: int,
) -> MatchStatus:
    if total_matches == 0:
        return "no_match"
    if total_matches == 1 and candidates[0].confidence == "exact":
        return "exact"
    return "ambiguous"


def _property_confidence(record: PropertyRecord, query: str) -> MatchConfidence:
    normalized_query = _normalize_text(query)
    searchable_values = (
        _normalize_text(record.id),
        _normalize_text(record.name),
        _normalize_text(record.address),
        _normalize_text(record.city),
    )
    if normalized_query in searchable_values:
        return "exact"
    if any(normalized_query in value for value in searchable_values):
        return "high"
    return "possible"


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _property_evidence(record: PropertyRecord) -> tuple[EvidenceItem, ...]:
    return (
        EvidenceItem("database.properties", record.id, "id", record.id),
        EvidenceItem("database.properties", record.id, "name", record.name),
        EvidenceItem("database.properties", record.id, "address", record.address),
        EvidenceItem("database.properties", record.id, "city", record.city),
    )


def _unit_facts(unit: UnitRecord) -> UnitFacts:
    return UnitFacts(
        unit=unit,
        evidence=(
            EvidenceItem("database.units", unit.id, "id", unit.id),
            EvidenceItem("database.units", unit.id, "property_id", unit.property_id),
            EvidenceItem("database.units", unit.id, "label", unit.label),
            EvidenceItem("database.units", unit.id, "bedrooms", unit.bedrooms),
            EvidenceItem("database.units", unit.id, "bathrooms", unit.bathrooms),
            EvidenceItem("database.units", unit.id, "sqft", unit.sqft),
            EvidenceItem("database.units", unit.id, "monthly_rent", unit.monthly_rent),
            EvidenceItem("database.units", unit.id, "available_from", unit.available_from),
            EvidenceItem("database.units", unit.id, "view", unit.view),
            EvidenceItem("database.units", unit.id, "parking", unit.parking),
            EvidenceItem("database.units", unit.id, "pet_policy", unit.pet_policy),
            EvidenceItem("database.units", unit.id, "amenities", unit.amenities),
            EvidenceItem("database.units", unit.id, "status", unit.status),
        ),
    )
