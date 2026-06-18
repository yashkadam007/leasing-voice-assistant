from leasing_voice_assistant.worker.prompts import initial_instructions


def test_prompt_uses_voice_safe_formatting_rules() -> None:
    instructions = initial_instructions()

    assert "phone audio only" in instructions
    assert "do not use markdown" in instructions
    assert "bullets" in instructions
    assert "bold text" in instructions
    assert "tables" in instructions


def test_prompt_answers_current_question_before_lead_capture() -> None:
    instructions = initial_instructions()

    assert "Answer the caller's current question before asking for lead details" in instructions
    assert "Only ask for name, email, phone, or other contact details after" in instructions
    assert "explicitly says they" in instructions
    assert "interested" in instructions
    assert "wants follow-up" in instructions


def test_prompt_handles_multi_fact_and_property_level_answers() -> None:
    instructions = initial_instructions()

    assert "asks for multiple facts" in instructions
    assert "answer every requested fact" in instructions
    assert "property-level instead of unit-specific" in instructions


def test_prompt_handles_incomplete_utterances() -> None:
    instructions = initial_instructions()

    assert "utterance seems incomplete" in instructions
    assert "ask a brief clarification" in instructions
