"""Deterministic parsing for supported grounding constraints."""

from __future__ import annotations

import re
from collections.abc import Sequence

from leasing_voice_assistant.agent.grounding.models import GroundingQuery
from leasing_voice_assistant.repositories.properties import normalize_unit_number

POLICY_TERMS = {
    "pets": ("pet", "pets", "dog", "dogs", "cat", "cats", "breed"),
    "parking": ("parking", "garage", "car", "vehicle"),
    "fees": ("fee", "fees", "application fee", "cost to apply"),
    "deposits": ("deposit", "deposits", "security deposit"),
    "lease_terms": ("lease", "term", "terms", "month lease"),
}
_BEDROOM_PATTERN = re.compile(
    r"\b(studio|zero|one|two|three|four|five|[0-5])(?:[ -]?bed(?:room)?s?|\s+bedrooms?)\b",
    re.IGNORECASE,
)
_PRICE_PATTERN = re.compile(
    r"\b(under|below|less than|at most|up to|over|above|more than|at least|from)\s*"
    r"\$?([\d,]+)(?:\s*(k|thousand))?\b",
    re.IGNORECASE,
)
_ALNUM_UNIT_PATTERN = re.compile(r"\b\d+[a-z]\b", re.IGNORECASE)
_UNIT_SEGMENT_PATTERN = re.compile(
    r"\b(?:units?|apartments?|apts?|homes?)\s+(.+?)(?=[?.!,;]|\b(?:at|in|with|that)\b|$)",
    re.IGNORECASE,
)
_COMPARISON_UNITS_PATTERN = re.compile(
    r"\b(?:compare|difference between)\s+(.+?)\s+(?:and|versus|vs)\s+"
    r"(.+?)(?=\s+(?:at|in|for|with)\b|[?.!,;]|$)",
    re.IGNORECASE,
)
_NUMBER_WORD_VALUES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_UNSUPPORTED_TERMS = {
    "cheap": "subjective_price",
    "cheapest": "subjective_price",
    "affordable": "subjective_price",
    "soon": "relative_availability_date",
    "nearby": "relative_location",
    "close to": "relative_location",
    "walking distance": "travel_distance",
    "commute": "travel_distance",
}


class GroundingQueryParser:
    """Extract only constraints that local data can enforce deterministically."""

    def parse(
        self,
        text: str,
        *,
        property_names: Sequence[str] = (),
        locations: Sequence[str] = (),
    ) -> GroundingQuery:
        normalized = " ".join(text.lower().split())
        properties = tuple(name for name in property_names if name.lower() in normalized)
        location_terms = tuple(location for location in locations if location.lower() in normalized)
        units = self._unit_numbers(text)

        bedroom_match = _BEDROOM_PATTERN.search(normalized)
        bedroom_count = None
        if bedroom_match:
            value = bedroom_match.group(1).lower()
            bedroom_count = (
                0
                if value == "studio"
                else _NUMBER_WORD_VALUES.get(value, int(value) if value.isdigit() else None)
            )

        minimum_rent = None
        maximum_rent = None
        for direction, amount, scale in _PRICE_PATTERN.findall(normalized):
            cents = int(amount.replace(",", "")) * (100_000 if scale else 100)
            if direction in {"under", "below", "less than", "at most", "up to"}:
                maximum_rent = cents
            else:
                minimum_rent = cents

        topics = tuple(
            topic
            for topic, terms in POLICY_TERMS.items()
            if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms)
        )
        unsupported = tuple(
            reason for term, reason in _UNSUPPORTED_TERMS.items() if term in normalized
        )
        unsupported = tuple(dict.fromkeys(unsupported))
        availability = any(
            term in normalized
            for term in (
                "available",
                "availability",
                "vacancy",
                "move in",
                "do you have",
                "are there",
            )
        )
        comparison = len(units) > 1 or any(
            term in normalized for term in ("compare", "difference", "versus", " vs ", "both")
        )
        supported_groups = sum(
            bool(value)
            for value in (
                properties or location_terms,
                units,
                bedroom_count is not None or minimum_rent is not None or maximum_rent is not None,
                topics,
                availability,
            )
        )
        return GroundingQuery(
            property_terms=properties,
            location_terms=location_terms,
            unit_numbers=units,
            bedroom_count=bedroom_count,
            minimum_rent_cents=minimum_rent,
            maximum_rent_cents=maximum_rent,
            availability_requested=availability,
            policy_topics=topics,
            comparison_requested=comparison,
            compound_question=supported_groups > 1
            or " and " in normalized
            and supported_groups > 0,
            unsupported_constraints=unsupported,
        )

    @staticmethod
    def _unit_numbers(text: str) -> tuple[str, ...]:
        found = [match.group(0).upper() for match in _ALNUM_UNIT_PATTERN.finditer(text)]
        for segment in _UNIT_SEGMENT_PATTERN.findall(text):
            for phrase in re.split(r"\s*(?:,|\band\b|\bversus\b|\bvs\b)\s*", segment):
                normalized = normalize_unit_number(phrase)
                if normalized:
                    found.append(normalized)
        for left, right in _COMPARISON_UNITS_PATTERN.findall(text):
            for phrase in (left, right):
                normalized = normalize_unit_number(phrase)
                if normalized:
                    found.append(normalized)
        return tuple(dict.fromkeys(found))
