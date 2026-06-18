from pathlib import Path

from leasing_voice_assistant.knowledge.ingest import ingest_knowledge_base
from leasing_voice_assistant.knowledge.retrieval import KnowledgeBase

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1] / "data" / "knowledge"


def test_ingestion_preserves_stable_source_metadata() -> None:
    chunks = ingest_knowledge_base(KNOWLEDGE_ROOT)

    aurora_pet = next(
        chunk
        for chunk in chunks
        if chunk.metadata.chunk_id == "properties/aurora-heights.md#pet-policy"
    )

    assert aurora_pet.metadata.source_path == "properties/aurora-heights.md"
    assert aurora_pet.metadata.document_title == "Aurora Heights"
    assert aurora_pet.metadata.section == "Pet Policy"
    assert aurora_pet.metadata.property_identifier == "aurora-heights"
    assert "cats and dogs" in aurora_pet.text


def test_retrieval_answers_application_process_questions() -> None:
    knowledge = KnowledgeBase(ingest_knowledge_base(KNOWLEDGE_ROOT))

    results = knowledge.search("How do I apply for an apartment?")

    assert results
    assert results[0].metadata.source_path == "general_faq.md"
    assert results[0].metadata.section == "Application Process"
    assert "rental history" in results[0].text
    assert results[0].score > 0


def test_retrieval_returns_property_specific_policy_with_metadata() -> None:
    knowledge = KnowledgeBase(ingest_knowledge_base(KNOWLEDGE_ROOT))

    results = knowledge.search("Does Aurora Heights have garage parking?")

    assert results
    assert results[0].metadata.property_identifier == "aurora-heights"
    assert results[0].metadata.section == "Parking"
    assert "$275 per month" in results[0].text


def test_retrieval_can_be_scoped_to_one_property() -> None:
    knowledge = KnowledgeBase(ingest_knowledge_base(KNOWLEDGE_ROOT))

    results = knowledge.search("pet policy", property_identifier="pine-garden-flats")

    assert results
    assert results[0].metadata.property_identifier == "pine-garden-flats"
    assert "one cat or dog" in results[0].text


def test_retrieval_returns_empty_for_unsupported_questions() -> None:
    knowledge = KnowledgeBase(ingest_knowledge_base(KNOWLEDGE_ROOT))

    results = knowledge.search("Do you offer furnished corporate housing in Tokyo?")

    assert results == []
