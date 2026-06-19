from leasing_voice_assistant.agent.prompts import initial_greeting, initial_instructions


def test_prompt_uses_voice_safe_formatting_rules() -> None:
    instructions = initial_instructions()

    assert "warm, friendly, calm leasing-office tone" in instructions
    assert "not scripted or salesy" in instructions
    assert "Do not over-apologize" in instructions
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


def test_prompt_keeps_grounded_answers_brief() -> None:
    instructions = initial_instructions()

    assert "requested fact plus at most one useful detail" in instructions
    assert "ask one short follow-up question" in instructions
    assert "Give more detail only when the caller asks for it" in instructions


def test_prompt_handles_incomplete_utterances() -> None:
    instructions = initial_instructions()

    assert "utterance seems incomplete" in instructions
    assert "ask a brief clarification" in instructions


def test_initial_greeting_is_short_and_human() -> None:
    greeting = initial_greeting()

    assert greeting == "Hi, this is Kiara from the leasing team. How can I help you today?"
    assert "interested" not in greeting.lower()
