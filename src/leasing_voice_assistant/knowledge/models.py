"""Structured knowledge-base records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeMetadata:
    """Stable metadata attached to a source-backed knowledge chunk."""

    source_path: str
    document_title: str
    section: str
    chunk_id: str
    property_identifier: str | None = None


@dataclass(frozen=True)
class KnowledgeChunk:
    """Searchable chunk of local knowledge-base source text."""

    text: str
    metadata: KnowledgeMetadata


@dataclass(frozen=True)
class RetrievalResult:
    """Ranked knowledge-base result with grounding metadata."""

    score: float
    text: str
    metadata: KnowledgeMetadata
