# ADR 0005: Leasing Agent Tools and Safety Gate

## Issue

Milestone 5 needs the tool layer that the realtime leasing agent will use during calls. The project already has structured SQLite data for exact property and unit facts, local knowledge retrieval for policy and narrative answers, and provider adapters for the voice stack. The next boundary is the agent-facing tool surface and the safety gate that prevents unsafe prospect writes.

The tool layer must support four core behaviors:

- find relevant properties or units from caller wording
- return authoritative unit facts from SQLite
- retrieve broader policy and FAQ content from the knowledge base
- capture prospect interest only after confidence, identity, and confirmation checks pass

The key decision is where to place prospect capture safety. The agent prompt can guide the conversation, but the write path must enforce its own rules so an LLM cannot create or update a prospect from ambiguous or unconfirmed context.

## Decision

Create a narrow leasing tool package under the shared application package and expose it to the realtime agent through LiveKit Agents function tools. The local package will contain the domain implementation that composes existing repositories, knowledge retrieval, and a per-call state model. LiveKit will provide the LLM-facing tool-calling runtime, argument schema exposure, and call context. The write tool will own the prospect capture safety gate and return structured rejection reasons instead of writing partial or ambiguous records.

The initial package layout will add the domain layer behind the LiveKit tool definitions:

```text
src/
  leasing_voice_assistant/
    agent/
      __init__.py
      state.py
      tools.py
      safety.py
tests/
  test_agent_tools.py
```

The initial LiveKit function tool surface will be:

- `search_properties`: search property and unit records from caller wording and return candidates with confidence, match type, and ambiguity metadata.
- `get_unit_details`: return authoritative unit facts for a specific unit.
- `search_knowledge_base`: call the existing retrieval service and return source-backed policy or FAQ snippets.
- `capture_prospect_interest`: create or update a prospect and interest only when the safety gate passes.

The optional `end_conversation` tool is deferred until the LiveKit SIP call pipeline proves it maps to real call control. Ending a conversation can remain prompt behavior until there is a concrete LiveKit action to invoke.

Per-call state should track only information needed for safe tool behavior:

- caller phone number from SIP metadata or equivalent call context
- caller name and optional email when provided
- the current resolved property or unit candidate
- the resolution confidence and whether ambiguity was resolved
- whether the caller explicitly confirmed interest in the resolved property or unit

The safety gate for `capture_prospect_interest` must reject writes unless:

- caller phone number is present
- caller name is present or explicitly confirmed
- property or unit resolution confidence meets the threshold
- the target is unambiguous
- the caller has explicitly confirmed interest in that target

Tool responses should be structured dictionaries or typed result objects with stable status fields. The LiveKit-decorated functions can return those results to the LLM, while the underlying domain functions remain directly unit-testable. Rejected writes should include machine-readable reasons such as `missing_phone`, `missing_name`, `ambiguous_property`, `low_confidence`, and `needs_confirmation`.

## Status

Accepted for implementation.

## Group

Milestone 5: Leasing Agent Tools and Safety Gate.

## Assumptions

- The LiveKit worker will register these tools with the agent using LiveKit Agents function-tool support in a later milestone.
- Exact property and unit facts remain in SQLite repositories.
- Broader leasing policies and narrative answers remain in the local knowledge retrieval service.
- Caller phone number will usually come from SIP metadata, but tests can provide it through per-call state.
- The first implementation can use deterministic confidence scoring based on repository matches and ambiguity rather than an LLM judge.
- Local tests must not require LiveKit, telephony, provider credentials, or network access.

## Constraints

- Keep the API and worker as separate runtime entrypoints.
- Do not let provider SDK details leak into tools or safety logic.
- Do not require provider or telephony credentials for linting, tests, imports, or `/health`.
- Do not let the prompt be the only enforcement layer for prospect writes.
- Keep the tool surface small enough to support the voice agent rather than becoming a general CRM API.
- Tool responses must make unknown, ambiguous, or unsafe states explicit so the agent can ask a clarification question.
- Prospect writes must remain idempotent through the existing repository and database constraints.

## Positions

### Position 1: LiveKit function tools backed by a domain tool package and deterministic safety gate

Implement LiveKit function tools for the worker, backed by tool functions or classes under an `agent` package. The domain functions use repositories and retrieval services directly, maintain a small per-call state object, compute deterministic confidence and ambiguity, and enforce prospect write rules inside `capture_prospect_interest`.

### Position 2: Prompt-only safety with direct repository writes

Let the system prompt instruct the LLM when it is safe to call repository write methods, and rely on conversation wording to avoid ambiguous or unconfirmed captures.

### Position 3: Expose prospect capture through FastAPI and have the worker call the API

Move prospect capture behind an HTTP endpoint in the FastAPI control plane and have the worker call that endpoint during conversations.

## Argument

Position 1 is the project decision. LiveKit Agents should provide the agent-facing tool-calling mechanism because it already supports Python function tools, tool schemas, run context, and the realtime agent loop. The local tool package is still needed as the domain boundary behind those decorators because it sits exactly where agent intent becomes application behavior. It can return useful structured context for answers, enforce write safety before touching the database, and stay testable without running a LiveKit room or model provider.

Prompt-only safety is not enough for prospect capture. The prompt should still tell the agent to clarify, confirm, and avoid guessing, but prompts are advisory. A dedicated safety gate makes the write contract explicit and gives tests a concrete place to prove that ambiguous property names, missing caller names, missing phone numbers, low confidence, and unconfirmed interest do not create records.

Putting capture behind FastAPI would add an unnecessary network boundary inside the same repository. The API is a control plane for health and reviewer verification, not the primary domain boundary for the voice loop. The worker and API already share the same package, repositories, and configuration, so direct tool-to-repository calls are simpler and easier to test.

Confidence scoring should be deterministic at this stage. A high-confidence result can come from an exact property match, exact unit lookup, or single clear candidate. Ambiguous or weak lexical matches should require clarification before capture. This keeps the first safety gate explainable and leaves room for later improvements without changing the tool contract.

The tool return schema matters because the LLM needs concise operational signals. A search tool should distinguish "no match" from "multiple candidates"; a capture tool should distinguish "needs confirmation" from "missing phone" or "missing name." Those statuses let the agent ask the next natural question instead of guessing or silently failing.

## Implications

- The worker can register a small, stable LiveKit function-tool surface in the LiveKit milestone.
- Tests can exercise grounded answer inputs and write rejections without provider credentials.
- The agent prompt remains important for conversation flow, but database writes are protected by code.
- Per-call state must be passed explicitly to tools, wrapped in a call-scoped tool context, or attached to LiveKit `RunContext` userdata.
- Repository and retrieval code remain reusable and do not need to know about LiveKit.
- The first confidence heuristic may be conservative; the agent may ask clarification questions rather than risking false captures.
- Adding transcript or tool-event persistence remains optional and can be deferred unless needed for demo debugging.

## Related decisions

- Use SQLite for authoritative property, unit, prospect, and interest data.
- Use local knowledge retrieval for broader policy and FAQ answers.
- Use provider adapters for STT, TTS, and LLM construction.
- Keep the FastAPI control plane minimal.
- Keep the LiveKit worker as the realtime conversation owner.
- Gate prospect writes behind confidence, caller identity, and explicit confirmation.

## Related requirements

- Factual property answers come from SQLite tools.
- Broader policy answers come from the knowledge-base tool.
- Capture tool rejects ambiguous or unsafe writes.
- Capture tool creates or updates the prospect when safety passes.
- Tests cover ambiguous property, missing name, missing phone, low confidence or missing confirmation, and valid capture.
- Tool responses include structured statuses and rejection reasons.

## Related artifacts

- `brief.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/STATUS.md`
- `docs/project/adr/0001-project-foundation-and-runtime.md`
- `docs/project/adr/0002-sqlite-domain-model-and-seed-data.md`
- `docs/project/adr/0003-knowledge-base-retrieval.md`
- `docs/project/adr/0004-provider-adapter-layer.md`
- Future `src/leasing_voice_assistant/agent/state.py`
- Future `src/leasing_voice_assistant/agent/tools.py`
- Future `src/leasing_voice_assistant/agent/safety.py`
- Future `tests/test_agent_tools.py`
- Future LiveKit worker function-tool registration

## Related principles

- Keep the voice agent as the center of the project.
- Ground exact facts in structured data.
- Ground policy and narrative answers in retrievable source content.
- Keep write paths safe, explicit, and testable.
- Ask clarification questions when confidence is low or identity is ambiguous.
- Prefer small milestone-scoped changes over broad infrastructure.
- Make local setup and reviewer verification straightforward.

## Notes

This ADR intentionally does not decide the final LiveKit SIP call flow, exact decorator or dynamic-registration code, realtime turn detection, final system prompt, or demo evaluation script. Those decisions belong to later milestones after the domain tool and safety boundary exists.
