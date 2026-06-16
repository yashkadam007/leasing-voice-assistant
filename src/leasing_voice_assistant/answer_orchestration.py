from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from leasing_voice_assistant.database_tools import (
    DatabaseQueryTools,
    EvidenceItem,
    GetUnitFactsRequest,
    ListUnitsRequest,
    UnitFacts,
)
from leasing_voice_assistant.interfaces import KnowledgeRetriever, KnowledgeSnippet, UnitRecord
from leasing_voice_assistant.property_resolution import PropertyResolutionState, PropertyResolver

AnswerRoute = Literal["database", "knowledge_base", "combined", "clarification", "unknown"]
FallbackReason = Literal[
    "none",
    "ambiguous_property",
    "ambiguous_unit",
    "missing_property",
    "missing_evidence",
    "unsupported_question",
]
DatabaseField = Literal[
    "rent",
    "bedrooms",
    "bathrooms",
    "sqft",
    "availability",
    "view",
    "parking",
    "pet_policy",
    "amenities",
]

_DB_FIELD_KEYWORDS: tuple[tuple[DatabaseField, tuple[str, ...]], ...] = (
    ("rent", ("rent", "price", "cost", "monthly", "expensive", "how much")),
    ("bedrooms", ("bedroom", "bedrooms", "beds", "bed")),
    ("bathrooms", ("bathroom", "bathrooms", "baths", "bath")),
    ("sqft", ("sqft", "square feet", "square footage", "size")),
    ("availability", ("available", "availability", "open", "move in", "move-in", "when")),
    ("view", ("view", "lake-facing", "courtyard", "tree-lined")),
    ("parking", ("parking", "garage", "space", "car")),
    ("pet_policy", ("pet", "pets", "cat", "cats", "dog", "dogs")),
    ("amenities", ("amenity", "amenities", "balcony", "laundry", "fitness", "pool")),
)
_KB_KEYWORDS = frozenset(
    {
        "apply",
        "application",
        "deposit",
        "fee",
        "fees",
        "lease",
        "term",
        "terms",
        "tour",
        "tours",
        "maintenance",
        "description",
        "about",
        "community",
        "neighborhood",
        "policy",
        "process",
    }
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class AnswerTurnRequest:
    user_text: str
    prior_resolution: PropertyResolutionState | None = None


@dataclass(frozen=True)
class AnswerTurnResult:
    answer_text: str
    route: AnswerRoute
    resolution: PropertyResolutionState
    database_fields: tuple[DatabaseField, ...] = ()
    database_evidence: tuple[EvidenceItem, ...] = ()
    knowledge_snippets: tuple[KnowledgeSnippet, ...] = ()
    fallback_reason: FallbackReason = "none"


class AnswerOrchestrator:
    def __init__(
        self,
        *,
        database_tools: DatabaseQueryTools,
        knowledge_retriever: KnowledgeRetriever,
        property_resolver: PropertyResolver | None = None,
    ) -> None:
        self.database_tools = database_tools
        self.knowledge_retriever = knowledge_retriever
        self.property_resolver = property_resolver or PropertyResolver(database_tools)

    def answer_turn(self, request: AnswerTurnRequest) -> AnswerTurnResult:
        user_text = request.user_text.strip()
        resolution = self.property_resolver.resolve(
            user_text,
            prior_state=request.prior_resolution,
        )
        database_fields = _database_fields(user_text)
        wants_kb = _wants_knowledge(user_text)

        if (
            resolution.confidence == "ambiguous"
            and resolution.clarification_reason == "ambiguous_property"
            and not wants_kb
        ):
            return AnswerTurnResult(
                answer_text=_property_clarification(resolution),
                route="clarification",
                resolution=resolution,
                database_fields=database_fields,
                database_evidence=resolution.evidence,
                fallback_reason="ambiguous_property",
            )

        if database_fields:
            database_result = self._answer_from_database(
                user_text,
                resolution=resolution,
                fields=database_fields,
            )
            if database_result.fallback_reason in {"none", "ambiguous_unit"}:
                return database_result
            if wants_kb:
                snippets = tuple(self.knowledge_retriever.retrieve(user_text, limit=3))
                if snippets:
                    return _kb_result(resolution, snippets, route="knowledge_base")
            return database_result

        if wants_kb or resolution.property_id is not None:
            snippets = tuple(self.knowledge_retriever.retrieve(user_text, limit=3))
            if snippets:
                return _kb_result(resolution, snippets, route="knowledge_base")

        return AnswerTurnResult(
            answer_text=(
                "I don't have that information in the property database or knowledge base. "
                "I can have the leasing team follow up if you'd like."
            ),
            route="unknown",
            resolution=resolution,
            fallback_reason="unsupported_question",
        )

    def _answer_from_database(
        self,
        user_text: str,
        *,
        resolution: PropertyResolutionState,
        fields: tuple[DatabaseField, ...],
    ) -> AnswerTurnResult:
        if (
            resolution.confidence == "ambiguous"
            and resolution.clarification_reason == "ambiguous_property"
        ):
            return AnswerTurnResult(
                answer_text=_property_clarification(resolution),
                route="clarification",
                resolution=resolution,
                database_fields=fields,
                database_evidence=resolution.evidence,
                fallback_reason="ambiguous_property",
            )

        if resolution.property_id is None:
            return AnswerTurnResult(
                answer_text="Which property should I check for that?",
                route="clarification",
                resolution=resolution,
                database_fields=fields,
                fallback_reason="missing_property",
            )

        if (
            resolution.confidence == "ambiguous"
            and resolution.clarification_reason == "ambiguous_unit"
        ):
            return AnswerTurnResult(
                answer_text=_unit_clarification(resolution),
                route="clarification",
                resolution=resolution,
                database_fields=fields,
                database_evidence=resolution.evidence,
                fallback_reason="ambiguous_unit",
            )

        unit_facts = self._candidate_units(resolution)
        if not unit_facts:
            return AnswerTurnResult(
                answer_text="I found the property, but I don't have unit facts for that question.",
                route="unknown",
                resolution=resolution,
                database_fields=fields,
                fallback_reason="missing_evidence",
            )

        answer = _compose_database_answer(
            property_name=resolution.property_name or resolution.property_id,
            units=unit_facts,
            fields=fields,
        )
        evidence_fields = _evidence_fields(fields)
        evidence = tuple(
            item for unit in unit_facts for item in unit.evidence if item.field in evidence_fields
        )
        return AnswerTurnResult(
            answer_text=answer,
            route="database",
            resolution=resolution,
            database_fields=fields,
            database_evidence=evidence,
        )

    def _candidate_units(self, resolution: PropertyResolutionState) -> tuple[UnitFacts, ...]:
        if resolution.unit_id is not None:
            unit_result = self.database_tools.get_unit_facts(
                GetUnitFactsRequest(unit_id=resolution.unit_id)
            )
            return (unit_result.unit,) if unit_result.unit is not None else ()

        if resolution.property_id is None:
            return ()

        list_result = self.database_tools.list_units(
            ListUnitsRequest(property_id=resolution.property_id)
        )
        return list_result.units


def _kb_result(
    resolution: PropertyResolutionState,
    snippets: tuple[KnowledgeSnippet, ...],
    *,
    route: AnswerRoute,
) -> AnswerTurnResult:
    top = snippets[0]
    heading = f"{top.section_heading}: " if top.section_heading else ""
    return AnswerTurnResult(
        answer_text=f"{heading}{top.text}",
        route=route,
        resolution=resolution,
        knowledge_snippets=snippets,
        fallback_reason="none",
    )


def _database_fields(text: str) -> tuple[DatabaseField, ...]:
    normalized = text.casefold()
    fields: list[DatabaseField] = []
    for field, keywords in _DB_FIELD_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            fields.append(field)
    return tuple(dict.fromkeys(fields))


def _wants_knowledge(text: str) -> bool:
    tokens = set(_TOKEN_PATTERN.findall(text.casefold()))
    return bool(tokens & _KB_KEYWORDS)


def _property_clarification(resolution: PropertyResolutionState) -> str:
    names = [candidate.property.name for candidate in resolution.candidates]
    if names:
        return f"Which property do you mean: {_join_or(names)}?"
    return "Which property do you mean?"


def _unit_clarification(resolution: PropertyResolutionState) -> str:
    labels = [candidate.unit.label for candidate in resolution.unit_candidates]
    if labels:
        return f"I found more than one matching unit. Do you mean unit {_join_or(labels)}?"
    return "I found more than one matching unit. Which unit do you mean?"


def _compose_database_answer(
    *,
    property_name: str,
    units: tuple[UnitFacts, ...],
    fields: tuple[DatabaseField, ...],
) -> str:
    if len(units) == 1:
        unit = units[0].unit
        facts = _unit_fact_phrases(unit, fields)
        if facts:
            return f"For {property_name} unit {unit.label}, " + ", ".join(facts) + "."
        return f"I found {property_name} unit {unit.label}, but not the requested fact."

    unit_summaries = []
    for unit_facts in units:
        unit = unit_facts.unit
        facts = _unit_fact_phrases(unit, fields)
        if facts:
            unit_summaries.append(f"unit {unit.label}: " + ", ".join(facts))
    if unit_summaries:
        return f"For {property_name}, " + "; ".join(unit_summaries) + "."
    return f"I found units at {property_name}, but not the requested fact."


def _unit_fact_phrases(unit: UnitRecord, fields: tuple[DatabaseField, ...]) -> list[str]:
    phrases: list[str] = []
    for field in fields:
        if field == "rent":
            phrases.append(f"rent is ${unit.monthly_rent:,} per month")
        elif field == "bedrooms":
            phrases.append(f"it has {unit.bedrooms} bedroom{'' if unit.bedrooms == 1 else 's'}")
        elif field == "bathrooms":
            suffix = "" if unit.bathrooms == 1 else "s"
            phrases.append(f"it has {unit.bathrooms:g} bathroom{suffix}")
        elif field == "sqft" and unit.sqft is not None:
            phrases.append(f"it is {unit.sqft:,} square feet")
        elif field == "availability":
            if unit.available_from:
                phrases.append(f"it is {unit.status} from {unit.available_from}")
            else:
                phrases.append(f"it is {unit.status}")
        elif field == "view" and unit.view:
            phrases.append(f"the view is {unit.view}")
        elif field == "parking" and unit.parking:
            phrases.append(f"parking is {unit.parking}")
        elif field == "pet_policy" and unit.pet_policy:
            phrases.append(f"the pet policy is {unit.pet_policy}")
        elif field == "amenities" and unit.amenities:
            phrases.append(f"amenities include {_join_and(list(unit.amenities))}")
    return phrases


def _evidence_fields(fields: tuple[DatabaseField, ...]) -> set[str]:
    mapping = {
        "rent": "monthly_rent",
        "bedrooms": "bedrooms",
        "bathrooms": "bathrooms",
        "sqft": "sqft",
        "availability": "available_from",
        "view": "view",
        "parking": "parking",
        "pet_policy": "pet_policy",
        "amenities": "amenities",
    }
    return {mapping[field] for field in fields}


def _join_or(values: list[str]) -> str:
    if len(values) <= 1:
        return "".join(values)
    return ", ".join(values[:-1]) + f", or {values[-1]}"


def _join_and(values: list[str]) -> str:
    if len(values) <= 1:
        return "".join(values)
    return ", ".join(values[:-1]) + f", and {values[-1]}"
