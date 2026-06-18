"""Local knowledge-base ingestion and retrieval."""

from leasing_voice_assistant.knowledge.ingest import ingest_knowledge_base
from leasing_voice_assistant.knowledge.models import (
    KnowledgeChunk,
    KnowledgeMetadata,
    RetrievalResult,
)
from leasing_voice_assistant.knowledge.retrieval import KnowledgeBase

__all__ = [
    "KnowledgeBase",
    "KnowledgeChunk",
    "KnowledgeMetadata",
    "RetrievalResult",
    "ingest_knowledge_base",
]
