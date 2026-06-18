"""Domain implementation behind leasing agent tools."""

from decimal import Decimal

from sqlalchemy.orm import Session

from leasing_voice_assistant.agent.safety import evaluate_capture_safety
from leasing_voice_assistant.agent.state import CallState, ResolvedTarget
from leasing_voice_assistant.db.models import Property, Unit
from leasing_voice_assistant.knowledge.retrieval import KnowledgeBase
from leasing_voice_assistant.repositories.properties import (
    PropertiesRepository,
    PropertySearchResult,
)
from leasing_voice_assistant.repositories.prospects import ProspectsRepository


class LeasingAgentTools:
    """Call-scoped leasing tools backed by repositories and retrieval."""

    def __init__(
        self,
        session: Session,
        state: CallState,
        *,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self.state = state
        self.properties = PropertiesRepository(session)
        self.prospects = ProspectsRepository(session)
        self.knowledge_base = knowledge_base if knowledge_base is not None else KnowledgeBase()

    def search_properties(self, query: str, *, limit: int = 5) -> dict:
        """Search property and unit records from caller wording."""
        results = self.properties.search(query, limit=limit)
        candidates = [
            _candidate_from_result(result, query=query, total_results=len(results))
            for result in results
        ]
        ambiguous = len(candidates) > 1
        for candidate in candidates:
            candidate["ambiguous"] = ambiguous

        status = "no_match"
        if len(candidates) == 1:
            status = "matched"
        elif len(candidates) > 1:
            status = "ambiguous"

        if status == "matched":
            self.state.set_target(_target_from_candidate(candidates[0], ambiguity_resolved=True))
        elif status == "ambiguous":
            best_candidate = max(candidates, key=lambda candidate: candidate["confidence"])
            self.state.set_target(_target_from_candidate(best_candidate, ambiguity_resolved=False))
        else:
            self.state.set_target(None)

        return {
            "status": status,
            "query": query,
            "ambiguous": ambiguous,
            "candidates": candidates,
        }

    def get_unit_details(self, unit_id: int) -> dict:
        """Return authoritative facts for a specific unit."""
        unit = self.properties.get_unit_details(unit_id)
        if unit is None:
            return {
                "status": "not_found",
                "unit_id": unit_id,
            }

        self.state.set_target(
            ResolvedTarget(
                target_type="unit",
                target_id=unit.id,
                label=f"{unit.property.name} unit {unit.unit_number}",
                confidence=1.0,
                ambiguous=False,
                ambiguity_resolved=True,
            )
        )
        return {
            "status": "found",
            "unit": _unit_details(unit),
        }

    def search_knowledge_base(
        self,
        query: str,
        *,
        limit: int = 3,
        property_identifier: str | None = None,
    ) -> dict:
        """Return source-backed policy or FAQ snippets from the local knowledge base."""
        results = self.knowledge_base.search(
            query,
            limit=limit,
            property_identifier=property_identifier,
        )
        return {
            "status": "matched" if results else "no_match",
            "query": query,
            "results": [
                {
                    "score": result.score,
                    "text": result.text,
                    "source": {
                        "path": result.metadata.source_path,
                        "document_title": result.metadata.document_title,
                        "section": result.metadata.section,
                        "chunk_id": result.metadata.chunk_id,
                        "property_identifier": result.metadata.property_identifier,
                    },
                }
                for result in results
            ],
        }

    def capture_prospect_interest(
        self,
        *,
        caller_name: str | None = None,
        caller_email: str | None = None,
        confirmed_interest: bool = False,
        notes: str | None = None,
    ) -> dict:
        """Create or update a prospect interest only after the safety gate passes."""
        self.state.set_caller_identity(name=caller_name, email=caller_email)
        if confirmed_interest:
            self.state.confirmed_interest = True

        safety = evaluate_capture_safety(self.state)
        if not safety.allowed:
            return {
                "status": "rejected",
                "reasons": list(safety.reasons),
                "target": _target_dict(self.state.current_target),
            }

        target = self.state.current_target
        if target is None:
            raise RuntimeError("capture safety allowed a missing target")

        prospect = self.prospects.upsert_by_phone(
            self.state.caller_phone_number or "",
            name=self.state.caller_name,
            email=self.state.caller_email,
        )
        interest, created = self.prospects.create_interest(
            prospect_id=prospect.id,
            property_id=target.target_id if target.target_type == "property" else None,
            unit_id=target.target_id if target.target_type == "unit" else None,
            notes=notes,
        )

        return {
            "status": "captured",
            "created": created,
            "prospect": {
                "id": prospect.id,
                "phone_number": prospect.phone_number,
                "name": prospect.name,
                "email": prospect.email,
            },
            "interest": {
                "id": interest.id,
                "property_id": interest.property_id,
                "unit_id": interest.unit_id,
            },
            "target": _target_dict(target),
        }


def _candidate_from_result(
    result: PropertySearchResult,
    *,
    query: str,
    total_results: int,
) -> dict:
    property_ = result.property
    matched_unit = _best_matched_unit(result)
    match_type, confidence = _score_result(result, query=query, total_results=total_results)
    target_type = "unit" if matched_unit is not None and match_type == "unit_exact" else "property"
    target_id = (
        matched_unit.id if target_type == "unit" and matched_unit is not None else property_.id
    )
    label = (
        f"{property_.name} unit {matched_unit.unit_number}"
        if target_type == "unit" and matched_unit is not None
        else property_.name
    )

    return {
        "target_type": target_type,
        "target_id": target_id,
        "label": label,
        "confidence": confidence,
        "match_type": match_type,
        "ambiguous": False,
        "property": _property_summary(property_),
        "matched_units": [_unit_summary(unit) for unit in result.matched_units],
    }


def _score_result(
    result: PropertySearchResult,
    *,
    query: str,
    total_results: int,
) -> tuple[str, float]:
    normalized_query = _normalize(query)
    property_ = result.property

    if _normalize(property_.name) == normalized_query:
        return "property_exact", 0.98
    if any(_normalize(unit.unit_number) == normalized_query for unit in result.matched_units):
        return "unit_exact", 0.98
    if _normalize(property_.name) in normalized_query:
        return "property_name", 0.92
    if any(_normalize(unit.unit_number) in normalized_query for unit in result.matched_units):
        return "unit_exact", 0.9
    if total_results == 1:
        return "single_candidate", 0.82
    return "lexical", 0.62


def _best_matched_unit(result: PropertySearchResult) -> Unit | None:
    if len(result.matched_units) == 1:
        return result.matched_units[0]
    return None


def _target_from_candidate(candidate: dict, *, ambiguity_resolved: bool) -> ResolvedTarget:
    return ResolvedTarget(
        target_type=candidate["target_type"],
        target_id=candidate["target_id"],
        label=candidate["label"],
        confidence=candidate["confidence"],
        ambiguous=candidate["ambiguous"],
        ambiguity_resolved=ambiguity_resolved,
    )


def _property_summary(property_: Property) -> dict:
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


def _unit_summary(unit: Unit) -> dict:
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


def _unit_details(unit: Unit) -> dict:
    details = _unit_summary(unit)
    details["notes"] = unit.notes
    details["property"] = _property_summary(unit.property)
    return details


def _target_dict(target: ResolvedTarget | None) -> dict | None:
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


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
