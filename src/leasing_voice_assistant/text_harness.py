from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
from collections.abc import Sequence

from leasing_voice_assistant.answer_orchestration import AnswerOrchestrator
from leasing_voice_assistant.conversation_session import (
    ConversationSessionService,
    ConversationSessionState,
    ConversationTurnRequest,
)
from leasing_voice_assistant.database_tools import DatabaseQueryTools
from leasing_voice_assistant.knowledge_base import MarkdownKnowledgeRetriever
from leasing_voice_assistant.persistence import (
    SQLitePropertyRepository,
    SQLiteProspectRepository,
    initialize_database,
)
from leasing_voice_assistant.prospect_capture import ProspectCaptureService


def build_text_harness(connection: sqlite3.Connection) -> ConversationSessionService:
    property_repository = SQLitePropertyRepository(connection)
    prospect_repository = SQLiteProspectRepository(connection)
    database_tools = DatabaseQueryTools(property_repository)
    answer_orchestrator = AnswerOrchestrator(
        database_tools=database_tools,
        knowledge_retriever=MarkdownKnowledgeRetriever.from_directory(),
    )
    return ConversationSessionService(
        answer_orchestrator=answer_orchestrator,
        prospect_capture_service=ProspectCaptureService(prospect_repository),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a local text leasing conversation.")
    parser.add_argument("--caller-phone", help="Optional caller phone metadata for the session.")
    parser.add_argument("--debug", action="store_true", help="Print safe per-turn debug traces.")
    args = parser.parse_args(argv)

    connection = initialize_database()
    try:
        service = build_text_harness(connection)
        state = ConversationSessionState()
        print("Text leasing assistant. Type 'exit' or 'quit' to stop.")
        while True:
            try:
                user_text = input("You: ").strip()
            except EOFError:
                print()
                break
            if user_text.casefold() in {"exit", "quit"}:
                break
            if not user_text:
                continue

            result = service.handle_turn(
                ConversationTurnRequest(
                    user_text=user_text,
                    state=state,
                    caller_phone=args.caller_phone,
                    include_debug_trace=args.debug,
                )
            )
            state = result.state
            print(f"Assistant: {result.assistant_text}")
            if result.debug_trace is not None:
                debug_json = json.dumps(dataclasses.asdict(result.debug_trace), sort_keys=True)
                print(f"Debug: {debug_json}")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
