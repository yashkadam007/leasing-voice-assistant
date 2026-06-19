"""Domain implementation behind leasing agent tools."""

from sqlalchemy.orm import Session

from leasing_voice_assistant.agent.resolution import (
    property_candidate_from_result,
    resolved_target_from_candidate,
    serialize_resolved_target,
    unit_facts,
)
from leasing_voice_assistant.agent.safety import evaluate_capture_safety
from leasing_voice_assistant.agent.state import CallState, ResolvedTarget
from leasing_voice_assistant.knowledge.retrieval import KnowledgeBase
from leasing_voice_assistant.repositories.properties import (
    PropertiesRepository,
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
            property_candidate_from_result(result, query=query, total_results=len(results))
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
            self.state.set_target(
                resolved_target_from_candidate(candidates[0], ambiguity_resolved=True)
            )
        elif status == "ambiguous":
            best_candidate = max(candidates, key=lambda candidate: candidate["confidence"])
            self.state.set_target(
                resolved_target_from_candidate(best_candidate, ambiguity_resolved=False)
            )
        else:
            self.state.set_target(None)

        return {
            "status": status,
            "query": query,
            "ambiguous": ambiguous,
            "candidates": candidates,
        }

    def get_unit_details(self, unit_number: str) -> dict:
        """Return authoritative facts for a caller-facing unit number."""
        units = self.properties.get_units_by_number(unit_number)
        if not units:
            return {
                "status": "not_found",
                "unit_number": unit_number,
            }

        property_id = (
            self.state.current_target.target_id
            if self.state.current_target is not None
            and self.state.current_target.target_type == "property"
            else None
        )
        if property_id is not None:
            matching_units = [unit for unit in units if unit.property_id == property_id]
            if matching_units:
                units = matching_units

        if len(units) > 1:
            return {
                "status": "ambiguous",
                "unit_number": unit_number,
                "candidates": [unit_facts(unit) for unit in units],
            }

        unit = units[0]
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
            "unit": unit_facts(unit),
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
                "target": serialize_resolved_target(self.state.current_target),
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
            "target": serialize_resolved_target(target),
        }
