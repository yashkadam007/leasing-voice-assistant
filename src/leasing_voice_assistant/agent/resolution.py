"""Shared property and unit resolution transformations."""

from decimal import Decimal
from typing import Literal, TypedDict

from leasing_voice_assistant.agent.state import ResolvedTarget
from leasing_voice_assistant.db.models import Property, Unit
from leasing_voice_assistant.repositories.properties import (
    PropertySearchResult,
    normalize_unit_number,
)

MatchType = Literal[
    "property_exact",
    "unit_exact",
    "property_name",
    "single_candidate",
    "lexical",
]


class PropertyFacts(TypedDict):
    id: int
    name: str
    address: str
    city: str
    state: str
    phone: str
    description: str
    pet_policy: str
    parking_policy: str
    application_fee_cents: int
    security_deposit_cents: int
    lease_terms: str


class UnitSummary(TypedDict):
    id: int
    unit_number: str
    bedroom_count: int
    bathroom_count: float
    rent_cents: int
    square_feet: int
    availability_date: str
    status: str
    floor: int
    view: str


class UnitFacts(UnitSummary):
    notes: str
    property: PropertyFacts


class PropertyCandidate(TypedDict):
    target_type: Literal["property", "unit"]
    target_id: int
    label: str
    confidence: float
    match_type: MatchType
    ambiguous: bool
    property: PropertyFacts
    available_units: list[UnitSummary]
    matched_units: list[UnitSummary]


class ResolvedTargetData(TypedDict):
    target_type: Literal["property", "unit"]
    target_id: int
    label: str
    confidence: float
    ambiguous: bool
    ambiguity_resolved: bool


def property_candidate_from_result(
    result: PropertySearchResult,
    *,
    query: str,
    total_results: int,
) -> PropertyCandidate:
    """Translate a repository search result into a caller-facing candidate."""
    property_ = result.property
    matched_unit = _best_matched_unit(result)
    match_type, confidence = score_property_result(result, query=query, total_results=total_results)
    target_type: Literal["property", "unit"] = (
        "unit" if matched_unit is not None and match_type == "unit_exact" else "property"
    )
    target_id = matched_unit.id if target_type == "unit" and matched_unit else property_.id
    label = (
        f"{property_.name} unit {matched_unit.unit_number}"
        if target_type == "unit" and matched_unit
        else property_.name
    )

    return {
        "target_type": target_type,
        "target_id": target_id,
        "label": label,
        "confidence": confidence,
        "match_type": match_type,
        "ambiguous": False,
        "property": property_facts(property_),
        "available_units": [
            unit_summary(unit) for unit in property_.units if unit.status == "available"
        ],
        "matched_units": [unit_summary(unit) for unit in result.matched_units],
    }


def score_property_result(
    result: PropertySearchResult,
    *,
    query: str,
    total_results: int,
) -> tuple[MatchType, float]:
    """Classify a property search result and assign its resolution confidence."""
    normalized_query = _normalize(query)
    normalized_unit_number = normalize_unit_number(query)
    property_ = result.property

    if _normalize(property_.name) == normalized_query:
        return "property_exact", 0.98
    if any(_normalize(unit.unit_number) == normalized_query for unit in result.matched_units):
        return "unit_exact", 0.98
    if any(unit.unit_number == normalized_unit_number for unit in result.matched_units):
        return "unit_exact", 0.98
    if _normalize(property_.name) in normalized_query:
        return "property_name", 0.92
    if any(_normalize(unit.unit_number) in normalized_query for unit in result.matched_units):
        return "unit_exact", 0.9
    if total_results == 1:
        return "single_candidate", 0.82
    return "lexical", 0.62


def resolved_target_from_candidate(
    candidate: PropertyCandidate, *, ambiguity_resolved: bool
) -> ResolvedTarget:
    """Convert a caller-facing property candidate into call state."""
    return ResolvedTarget(
        target_type=candidate["target_type"],
        target_id=candidate["target_id"],
        label=candidate["label"],
        confidence=candidate["confidence"],
        ambiguous=candidate["ambiguous"],
        ambiguity_resolved=ambiguity_resolved,
    )


def property_facts(property_: Property) -> PropertyFacts:
    """Serialize authoritative property facts for agent-facing payloads."""
    return {
        "id": property_.id,
        "name": property_.name,
        "address": property_.address,
        "city": property_.city,
        "state": property_.state,
        "phone": property_.phone,
        "description": property_.description,
        "pet_policy": property_.pet_policy,
        "parking_policy": property_.parking_policy,
        "application_fee_cents": property_.application_fee_cents,
        "security_deposit_cents": property_.security_deposit_cents,
        "lease_terms": property_.lease_terms,
    }


def unit_summary(unit: Unit) -> UnitSummary:
    """Serialize compact authoritative unit facts for candidate lists."""
    return {
        "id": unit.id,
        "unit_number": unit.unit_number,
        "bedroom_count": unit.bedroom_count,
        "bathroom_count": _decimal_to_float(unit.bathroom_count),
        "rent_cents": unit.rent_cents,
        "square_feet": unit.square_feet,
        "availability_date": unit.availability_date.isoformat(),
        "status": unit.status,
        "floor": unit.floor,
        "view": unit.view,
    }


def unit_facts(unit: Unit) -> UnitFacts:
    """Serialize complete authoritative unit and property facts."""
    return {
        **unit_summary(unit),
        "notes": unit.notes,
        "property": property_facts(unit.property),
    }


def serialize_resolved_target(target: ResolvedTarget | None) -> ResolvedTargetData | None:
    """Serialize optional call-state target data for tool responses."""
    if target is None:
        return None
    return {
        "target_type": target.target_type,
        "target_id": target.target_id,
        "label": target.label,
        "confidence": target.confidence,
        "ambiguous": target.ambiguous,
        "ambiguity_resolved": target.ambiguity_resolved,
    }


def _best_matched_unit(result: PropertySearchResult) -> Unit | None:
    if len(result.matched_units) == 1:
        return result.matched_units[0]
    return None


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
