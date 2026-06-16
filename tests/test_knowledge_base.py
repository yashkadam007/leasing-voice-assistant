from pathlib import Path

from leasing_voice_assistant.knowledge_base import (
    MarkdownKnowledgeRetriever,
    load_markdown_sections,
)

KB_DIR = Path("data/kb")


def test_load_markdown_sections_assigns_stable_source_metadata() -> None:
    sections = load_markdown_sections(KB_DIR)

    source_ids = {section.source_id for section in sections}

    assert "general-leasing-faq#application-process" in source_ids
    assert "lakeview-flats#property-description" in source_ids
    application = next(
        section
        for section in sections
        if section.source_id == "general-leasing-faq#application-process"
    )
    assert application.title == "General Leasing FAQ"
    assert application.section_heading == "Application Process"
    assert application.path == "data/kb/general-leasing-faq.md"


def test_retriever_returns_known_faq_with_source_attribution() -> None:
    retriever = MarkdownKnowledgeRetriever.from_directory(KB_DIR)

    results = retriever.retrieve("How do I apply online?", limit=3)

    assert results
    top = results[0]
    assert top.source_id == "general-leasing-faq#application-process"
    assert top.title == "General Leasing FAQ"
    assert top.section_heading == "Application Process"
    assert "apply online" in top.text
    assert ("path", "data/kb/general-leasing-faq.md") in top.metadata


def test_retriever_returns_property_description() -> None:
    retriever = MarkdownKnowledgeRetriever.from_directory(KB_DIR)

    results = retriever.retrieve("Tell me about Lakeview waterfront trails", limit=2)

    assert results[0].source_id == "lakeview-flats#property-description"
    assert "waterfront" in results[0].text


def test_retriever_enforces_limits_and_snippet_bounds() -> None:
    retriever = MarkdownKnowledgeRetriever.from_directory(KB_DIR, snippet_chars=120)

    results = retriever.retrieve("leasing property unit pet parking application", limit=1)

    assert len(results) == 1
    assert len(results[0].text) <= 120


def test_retriever_returns_empty_for_unknown_or_empty_query() -> None:
    retriever = MarkdownKnowledgeRetriever.from_directory(KB_DIR)

    assert retriever.retrieve("quantum espresso compiler internals") == ()
    assert retriever.retrieve("   ") == ()


def test_missing_kb_directory_returns_no_sections(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"

    retriever = MarkdownKnowledgeRetriever.from_directory(missing_dir)

    assert retriever.retrieve("application") == ()
