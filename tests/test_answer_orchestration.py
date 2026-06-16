from pathlib import Path

from leasing_voice_assistant.answer_orchestration import AnswerOrchestrator, AnswerTurnRequest
from leasing_voice_assistant.database_tools import DatabaseQueryTools
from leasing_voice_assistant.knowledge_base import MarkdownKnowledgeRetriever
from leasing_voice_assistant.persistence import SQLitePropertyRepository, initialize_database

KB_DIR = Path("data/kb")


def create_orchestrator(tmp_path: Path) -> AnswerOrchestrator:
    connection = initialize_database(tmp_path / "test.sqlite3")
    database_tools = DatabaseQueryTools(SQLitePropertyRepository(connection))
    return AnswerOrchestrator(
        database_tools=database_tools,
        knowledge_retriever=MarkdownKnowledgeRetriever.from_directory(KB_DIR),
    )


def test_answers_single_unit_rent_from_database(tmp_path: Path) -> None:
    orchestrator = create_orchestrator(tmp_path)

    result = orchestrator.answer_turn(
        AnswerTurnRequest(user_text="What is the rent at Cedar Park Townhomes?")
    )

    assert result.route == "database"
    assert result.database_fields == ("rent",)
    assert result.resolution.property_id == "property-cedar-park-townhomes"
    assert "$3,100 per month" in result.answer_text
    assert any(
        evidence.source == "database.units"
        and evidence.record_id == "unit-cedar-3c"
        and evidence.field == "monthly_rent"
        and evidence.value == 3100
        for evidence in result.database_evidence
    )


def test_answers_unit_specific_fact_from_prior_context(tmp_path: Path) -> None:
    orchestrator = create_orchestrator(tmp_path)
    first = orchestrator.answer_turn(AnswerTurnRequest(user_text="Tell me about Lakeview Flats"))

    result = orchestrator.answer_turn(
        AnswerTurnRequest(
            user_text="How much is the lake-facing one?",
            prior_resolution=first.resolution,
        )
    )

    assert result.route == "database"
    assert result.resolution.unit_id == "unit-lakeview-2b"
    assert "unit 2B" in result.answer_text
    assert "$2,450 per month" in result.answer_text


def test_answers_application_process_from_knowledge_base(tmp_path: Path) -> None:
    orchestrator = create_orchestrator(tmp_path)

    result = orchestrator.answer_turn(AnswerTurnRequest(user_text="How do I apply online?"))

    assert result.route == "knowledge_base"
    assert result.knowledge_snippets
    assert result.knowledge_snippets[0].source_id == "general-leasing-faq#application-process"
    assert "Application Process" in result.answer_text
    assert "apply online" in result.answer_text


def test_returns_unknown_fallback_without_evidence(tmp_path: Path) -> None:
    orchestrator = create_orchestrator(tmp_path)

    result = orchestrator.answer_turn(
        AnswerTurnRequest(user_text="Do you support quantum espresso compiler internships?")
    )

    assert result.route == "unknown"
    assert result.fallback_reason == "unsupported_question"
    assert "don't have that information" in result.answer_text
    assert result.database_evidence == ()
    assert result.knowledge_snippets == ()


def test_asks_for_property_when_database_fact_has_no_context(tmp_path: Path) -> None:
    orchestrator = create_orchestrator(tmp_path)

    result = orchestrator.answer_turn(AnswerTurnRequest(user_text="What is the rent?"))

    assert result.route == "clarification"
    assert result.fallback_reason == "missing_property"
    assert result.answer_text == "Which property should I check for that?"


def test_ambiguous_property_reference_asks_for_clarification(tmp_path: Path) -> None:
    orchestrator = create_orchestrator(tmp_path)

    result = orchestrator.answer_turn(AnswerTurnRequest(user_text="a"))

    assert result.route == "clarification"
    assert result.fallback_reason == "ambiguous_property"
    assert "Lakeview Flats" in result.answer_text
    assert "Cedar Park Townhomes" in result.answer_text


def test_database_pet_policy_takes_precedence_over_kb_guidance_for_structured_unit_fact(
    tmp_path: Path,
) -> None:
    orchestrator = create_orchestrator(tmp_path)

    result = orchestrator.answer_turn(
        AnswerTurnRequest(user_text="What is the pet policy for Cedar Park Townhomes?")
    )

    assert result.route == "database"
    assert result.database_fields == ("pet_policy",)
    assert result.knowledge_snippets == ()
    assert "dogs and cats allowed with breed restrictions" in result.answer_text
    assert "must be confirmed before move-in" not in result.answer_text
