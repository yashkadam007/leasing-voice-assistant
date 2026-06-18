"""Deterministic lexical retrieval for the local knowledge base."""

import re
from collections import Counter
from math import sqrt

from leasing_voice_assistant.knowledge.ingest import ingest_knowledge_base
from leasing_voice_assistant.knowledge.models import KnowledgeChunk, RetrievalResult

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "can",
    "do",
    "does",
    "for",
    "how",
    "i",
    "is",
    "me",
    "of",
    "or",
    "the",
    "there",
    "to",
    "what",
    "with",
    "you",
}
SYNONYMS = {
    "apartment": "home",
    "apartments": "home",
    "apply": "application",
    "applying": "application",
}


class KnowledgeBase:
    """Small local retrieval service for policy, process, and narrative answers."""

    def __init__(self, chunks: list[KnowledgeChunk] | None = None) -> None:
        self.chunks = chunks if chunks is not None else ingest_knowledge_base()
        self._indexed_chunks = [
            (chunk, _token_counts(_searchable_text(chunk))) for chunk in self.chunks
        ]

    def search(
        self,
        query: str,
        *,
        limit: int = 3,
        min_score: float = 0.18,
        property_identifier: str | None = None,
    ) -> list[RetrievalResult]:
        """Return source-backed matches, or an empty list for unsupported questions."""
        query_counts = _token_counts(query)
        if not query_counts:
            return []

        ranked: list[RetrievalResult] = []
        normalized_property = property_identifier.strip().lower() if property_identifier else None

        for chunk, chunk_counts in self._indexed_chunks:
            if (
                normalized_property is not None
                and chunk.metadata.property_identifier is not None
                and chunk.metadata.property_identifier != normalized_property
            ):
                continue

            score = _score(query_counts, chunk_counts)
            score += _phrase_bonus(query, chunk)
            if (
                normalized_property is not None
                and chunk.metadata.property_identifier == normalized_property
            ):
                score += 0.25
            if score >= min_score:
                ranked.append(
                    RetrievalResult(
                        score=round(score, 4),
                        text=chunk.text,
                        metadata=chunk.metadata,
                    )
                )

        return sorted(
            ranked,
            key=lambda result: (
                -result.score,
                result.metadata.source_path,
                result.metadata.section,
            ),
        )[:limit]


def _searchable_text(chunk: KnowledgeChunk) -> str:
    metadata = chunk.metadata
    parts = [
        metadata.document_title,
        metadata.section,
        metadata.property_identifier or "",
        chunk.text,
    ]
    return " ".join(parts)


def _token_counts(value: str) -> Counter[str]:
    tokens = (_normalize_token(match.group(0)) for match in TOKEN_PATTERN.finditer(value.lower()))
    return Counter(token for token in tokens if token and token not in STOP_WORDS)


def _normalize_token(token: str) -> str:
    if token in SYNONYMS:
        return SYNONYMS[token]
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _score(query_counts: Counter[str], chunk_counts: Counter[str]) -> float:
    shared = set(query_counts) & set(chunk_counts)
    if not shared:
        return 0.0

    dot_product = sum(query_counts[token] * chunk_counts[token] for token in shared)
    query_length = sqrt(sum(count * count for count in query_counts.values()))
    chunk_length = sqrt(sum(count * count for count in chunk_counts.values()))
    if query_length == 0 or chunk_length == 0:
        return 0.0
    return dot_product / (query_length * chunk_length)


def _phrase_bonus(query: str, chunk: KnowledgeChunk) -> float:
    normalized_query = " ".join(TOKEN_PATTERN.findall(query.lower()))
    if not normalized_query:
        return 0.0

    section = " ".join(TOKEN_PATTERN.findall(chunk.metadata.section.lower()))
    document_title = " ".join(TOKEN_PATTERN.findall(chunk.metadata.document_title.lower()))

    bonus = 0.0
    if section and section in normalized_query:
        bonus += 0.2
    if document_title and document_title in normalized_query:
        bonus += 0.08
    return bonus
