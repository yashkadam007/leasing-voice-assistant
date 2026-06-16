from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from leasing_voice_assistant.database_tools import (
    DatabaseQueryTools,
    EvidenceItem,
    ListUnitsRequest,
    MatchConfidence,
    PropertyCandidate,
    SearchPropertiesRequest,
    UnitFacts,
)
from leasing_voice_assistant.interfaces import PropertyRecord, UnitRecord

ResolutionConfidence = Literal["resolved", "probable", "ambiguous", "unresolved"]
ClarificationReason = Literal[
    "none",
    "ambiguous_property",
    "ambiguous_unit",
    "no_match",
]

_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "am",
        "an",
        "and",
        "any",
        "are",
        "at",
        "available",
        "do",
        "for",
        "have",
        "i",
        "in",
        "is",
        "it",
        "me",
        "of",
        "one",
        "or",
        "that",
        "the",
        "there",
        "this",
        "to",
        "want",
        "what",
        "with",
    }
)
_CONTEXT_REFERENCES = frozenset({"it", "that", "this", "one", "there", "place", "property"})
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4}


@dataclass(frozen=True)
class PropertyResolutionCandidate:
    property: PropertyRecord
    confidence: MatchConfidence
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class UnitResolutionCandidate:
    unit: UnitRecord
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class PropertyResolutionState:
    confidence: ResolutionConfidence = "unresolved"
    property_id: str | None = None
    property_name: str | None = None
    unit_id: str | None = None
    unit_label: str | None = None
    write_ready: bool = False
    clarification_needed: bool = True
    clarification_reason: ClarificationReason = "no_match"
    candidates: tuple[PropertyResolutionCandidate, ...] = ()
    unit_candidates: tuple[UnitResolutionCandidate, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()


class PropertyResolver:
    def __init__(self, database_tools: DatabaseQueryTools) -> None:
        self.database_tools = database_tools

    def resolve(
        self,
        user_text: str,
        *,
        prior_state: PropertyResolutionState | None = None,
    ) -> PropertyResolutionState:
        text = user_text.strip()
        prior = prior_state or PropertyResolutionState()
        property_candidates = self._find_property_candidates(text)

        if len(property_candidates) > 1:
            return PropertyResolutionState(
                confidence="ambiguous",
                property_id=prior.property_id,
                property_name=prior.property_name,
                write_ready=False,
                clarification_needed=True,
                clarification_reason="ambiguous_property",
                candidates=property_candidates,
                evidence=_candidate_evidence(property_candidates),
            )

        if len(property_candidates) == 1:
            candidate = property_candidates[0]
            confidence: ResolutionConfidence = (
                "resolved" if candidate.confidence in {"exact", "high"} else "probable"
            )
            return self._resolve_unit_hints(
                text,
                property_=candidate.property,
                property_confidence=confidence,
                property_candidates=property_candidates,
            )

        if prior.property_id is not None and prior.confidence in {"resolved", "probable"}:
            property_ = PropertyRecord(
                id=prior.property_id,
                name=prior.property_name or prior.property_id,
                address="",
                city="",
            )
            return self._resolve_unit_hints(
                text,
                property_=property_,
                property_confidence=prior.confidence,
                property_candidates=prior.candidates,
                prior_state=prior,
            )

        return PropertyResolutionState(
            confidence="unresolved",
            write_ready=False,
            clarification_needed=True,
            clarification_reason="no_match",
        )

    def _find_property_candidates(self, text: str) -> tuple[PropertyResolutionCandidate, ...]:
        phrases = _search_phrases(text)
        candidates_by_id: dict[str, PropertyResolutionCandidate] = {}
        score_by_id: dict[str, tuple[int, int]] = {}

        for phrase in phrases:
            result = self.database_tools.search_properties(SearchPropertiesRequest(query=phrase))
            for candidate in result.candidates:
                score = (_confidence_score(candidate.confidence), len(phrase))
                existing_score = score_by_id.get(candidate.property.id)
                if existing_score is None or score > existing_score:
                    candidates_by_id[candidate.property.id] = _resolution_candidate(candidate)
                    score_by_id[candidate.property.id] = score

        ordered = sorted(
            candidates_by_id.values(),
            key=lambda candidate: (
                _confidence_score(candidate.confidence),
                len(candidate.property.name),
            ),
            reverse=True,
        )
        if not ordered:
            return ()

        top_score = _confidence_score(ordered[0].confidence)
        return tuple(
            candidate
            for candidate in ordered
            if _confidence_score(candidate.confidence) == top_score
        )

    def _resolve_unit_hints(
        self,
        text: str,
        *,
        property_: PropertyRecord,
        property_confidence: ResolutionConfidence,
        property_candidates: tuple[PropertyResolutionCandidate, ...],
        prior_state: PropertyResolutionState | None = None,
    ) -> PropertyResolutionState:
        unit_matches = self._find_unit_matches(text, property_id=property_.id)
        evidence = _candidate_evidence(property_candidates)
        if not unit_matches:
            prior_unit = prior_state if prior_state and _has_context_reference(text) else None
            return PropertyResolutionState(
                confidence=property_confidence,
                property_id=property_.id,
                property_name=property_.name,
                unit_id=prior_unit.unit_id if prior_unit else None,
                unit_label=prior_unit.unit_label if prior_unit else None,
                write_ready=property_confidence == "resolved",
                clarification_needed=property_confidence != "resolved",
                clarification_reason="none" if property_confidence == "resolved" else "no_match",
                candidates=property_candidates,
                evidence=evidence,
            )

        if len(unit_matches) > 1:
            return PropertyResolutionState(
                confidence="ambiguous",
                property_id=property_.id,
                property_name=property_.name,
                write_ready=False,
                clarification_needed=True,
                clarification_reason="ambiguous_unit",
                candidates=property_candidates,
                unit_candidates=unit_matches,
                evidence=evidence + _unit_candidate_evidence(unit_matches),
            )

        unit = unit_matches[0].unit
        return PropertyResolutionState(
            confidence="resolved",
            property_id=property_.id,
            property_name=property_.name,
            unit_id=unit.id,
            unit_label=unit.label,
            write_ready=True,
            clarification_needed=False,
            clarification_reason="none",
            candidates=property_candidates,
            unit_candidates=unit_matches,
            evidence=evidence + unit_matches[0].evidence,
        )

    def _find_unit_matches(
        self,
        text: str,
        *,
        property_id: str,
    ) -> tuple[UnitResolutionCandidate, ...]:
        hints = _unit_hints(text)
        if not hints.has_any:
            return ()

        result = self.database_tools.list_units(ListUnitsRequest(property_id=property_id))
        matches: list[UnitResolutionCandidate] = []
        for unit_facts in result.units:
            if hints.matches(unit_facts.unit):
                matches.append(_unit_resolution_candidate(unit_facts))
        return tuple(matches)


@dataclass(frozen=True)
class _UnitHints:
    bedrooms: int | None = None
    view_terms: tuple[str, ...] = ()
    label: str | None = None
    available: bool = False

    @property
    def has_any(self) -> bool:
        return (
            self.bedrooms is not None
            or bool(self.view_terms)
            or self.label is not None
            or self.available
        )

    def matches(self, unit: UnitRecord) -> bool:
        if self.bedrooms is not None and unit.bedrooms != self.bedrooms:
            return False
        if self.label is not None and unit.label.casefold() != self.label:
            return False
        if self.available and unit.status != "available":
            return False
        if self.view_terms:
            view = (unit.view or "").casefold().replace("-", " ")
            if not all(term in view for term in self.view_terms):
                return False
        return True


def _search_phrases(text: str) -> tuple[str, ...]:
    tokens = _tokens(text)
    if len(tokens) == 1:
        return tokens

    phrases: list[str] = []
    for size in range(min(4, len(tokens)), 0, -1):
        for index in range(0, len(tokens) - size + 1):
            phrase_tokens = tokens[index : index + size]
            if size == 1 and (phrase_tokens[0] in _STOPWORDS or len(phrase_tokens[0]) < 4):
                continue
            phrase = " ".join(phrase_tokens)
            if phrase not in phrases:
                phrases.append(phrase)
    return tuple(phrases)


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", text.casefold()))


def _unit_hints(text: str) -> _UnitHints:
    normalized = " ".join(_tokens(text))
    bedrooms = _bedroom_hint(normalized)
    view_terms = _view_terms(normalized)
    label = _unit_label(normalized)
    available = "available" in normalized
    return _UnitHints(
        bedrooms=bedrooms,
        view_terms=view_terms,
        label=label,
        available=available,
    )


def _bedroom_hint(normalized_text: str) -> int | None:
    digit_match = re.search(r"\b([1-4])\s*(?:bed|bedroom|br)\b", normalized_text)
    if digit_match:
        return int(digit_match.group(1))

    word_match = re.search(r"\b(one|two|three|four)\s*(?:bed|bedroom)\b", normalized_text)
    if word_match:
        return _NUMBER_WORDS[word_match.group(1)]
    return None


def _view_terms(normalized_text: str) -> tuple[str, ...]:
    if "lake facing" in normalized_text or "lake view" in normalized_text:
        return ("lake",)
    if "courtyard" in normalized_text:
        return ("courtyard",)
    if "tree lined" in normalized_text:
        return ("tree", "lined")
    return ()


def _unit_label(normalized_text: str) -> str | None:
    label_match = re.search(r"\bunit\s+([0-9][a-z])\b", normalized_text)
    return label_match.group(1).upper() if label_match else None


def _has_context_reference(text: str) -> bool:
    return bool(set(_tokens(text)) & _CONTEXT_REFERENCES)


def _resolution_candidate(candidate: PropertyCandidate) -> PropertyResolutionCandidate:
    return PropertyResolutionCandidate(
        property=candidate.property,
        confidence=candidate.confidence,
        evidence=candidate.evidence,
    )


def _unit_resolution_candidate(unit_facts: UnitFacts) -> UnitResolutionCandidate:
    return UnitResolutionCandidate(unit=unit_facts.unit, evidence=unit_facts.evidence)


def _candidate_evidence(
    candidates: tuple[PropertyResolutionCandidate, ...],
) -> tuple[EvidenceItem, ...]:
    return tuple(evidence for candidate in candidates for evidence in candidate.evidence)


def _unit_candidate_evidence(
    candidates: tuple[UnitResolutionCandidate, ...],
) -> tuple[EvidenceItem, ...]:
    return tuple(evidence for candidate in candidates for evidence in candidate.evidence)


def _confidence_score(confidence: MatchConfidence) -> int:
    return {"exact": 3, "high": 2, "possible": 1}[confidence]
