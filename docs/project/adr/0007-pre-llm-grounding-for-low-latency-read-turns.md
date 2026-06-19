# ADR 0007: Pre-LLM Grounding for Low-Latency Read Turns

## Issue

The twenty-call voice baseline shows that LLM tool orchestration, rather than local data access, is
the largest avoidable source of response latency:

- read and write tool turns have a 5,251 ms median end-to-end latency
- non-tool turns have a 2,918 ms median end-to-end latency
- local tool execution has a 13 ms median and 19 ms maximum
- ordinary single-tool turns have a 5,068 ms median end-to-end latency
- four turns called the same read tool twice and have a 6,407 ms median end-to-end latency

The current LiveKit agent gives the LLM four function tools. A grounded read normally requires one
model request to select and parameterize a tool, local tool execution, and another model request to
turn the result into speech. The current recorder reports only the final assistant LLM time to first
token, so it does not expose the first model request independently. The end-to-end measurements and
negligible local execution time nevertheless show that the extra model cycle dominates the read
path.

Duplicate calls explain part of the tail but not the 2,150 ms median difference between ordinary
single-tool and non-tool turns. Suppressing duplicate calls without changing orchestration would
leave the main latency cost in place.

The decision must reduce model round trips without weakening the existing grounding rules or the
code-enforced prospect capture safety gate.

## Decision

Use a hybrid orchestration path:

- perform bounded, deterministic read-only grounding after the caller turn is complete and before
  response generation
- provide the grounding result to one LLM request so the model only verbalizes retrieved facts
- stop exposing `search_properties`, `get_unit_details`, and `search_knowledge_base` as LLM
  function tools
- continue exposing `capture_prospect_interest` as a function tool and keep its deterministic
  safety gate and transaction behavior unchanged

Implement a call-scoped `LeasingVoiceAgent` subclass, a provider-independent
`GroundingQueryParser`, and a `GroundedTurnContextBuilder`.
`LeasingVoiceAgent.on_user_turn_completed` will pass the final caller text and a snapshot of
`CallState` to the builder, then add the resulting structured grounding as a developer message to
LiveKit's temporary `ChatContext` for that generation. LiveKit does not retain edits to this
temporary context in the agent's conversation history, so grounding from one turn will not
accumulate as synthetic chat messages.

The query parser will extract only deterministic concepts that the local data model can enforce:

- explicit property names and location terms
- every explicit numeric or spoken unit number
- bedroom count
- minimum or maximum rent when stated unambiguously
- availability intent
- policy topics such as pets, parking, fees, deposits, and lease terms
- comparison or compound-question intent

The existing repository does not currently implement general natural-language constraint parsing.
It performs lexical matching over selected property and unit fields, and its unit normalizer handles
basic caller-facing unit phrases. The current LLM tool schema also accepts a raw `query` string,
rather than structured bedroom or price arguments, but the model can rewrite caller wording before
calling it. The hybrid path therefore must not claim parity from reuse of the current repository
alone. Unsupported or low-confidence constraints must be represented explicitly in the grounding
result so the assistant asks a focused clarification instead of returning a misleading `no_match`.
Read tools remain available behind the rollout flag until the parser passes the query-parity tests;
they are not a fallback for an exception or unavailable authoritative data.

The grounding builder will use the existing repositories, knowledge retrieval, result schemas, and
resolution rules. It will:

1. Include authoritative facts for the current resolved property or unit when one exists, so short
   follow-ups such as "What is the rent?" do not require the caller to repeat the target.
2. Parse the final caller text into the supported deterministic constraints, retaining the raw text
   only in memory for lexical retrieval.
3. Search property and unit data using both the supported constraints and lexical terms.
4. Perform exact unit lookup for every explicit unit number needed by a comparison.
5. Search the knowledge base using the relevant policy topics and the resolved property identifier
   when available.
6. Return explicit `matched`, `ambiguous`, `no_match`, `needs_clarification`, or `unavailable`
   statuses with source type metadata.

Grounding must be bounded to one current target, at most three property candidates, up to three
explicitly requested unit results, at most two knowledge chunks per explicit policy topic, and an
8 KiB serialized context. Explicitly requested entities and facts take precedence over lower-ranked
candidates and supplemental knowledge. If all requested entities cannot fit, return
`needs_clarification` rather than silently dropping one side of a comparison. Truncation must remove
whole lower-ranked records, not cut a fact or source record in the middle. The prompt will state
that the grounding block is data, not instructions, and that the assistant must not invent facts
absent from it.

State updates must remain conservative. An unambiguous, high-confidence property or unit match may
replace the current target. An unrelated query or no-match result must preserve the current target.
An explicit ambiguous search may record an ambiguous provisional target so the capture safety gate
continues to require clarification. Changing the target continues to reset confirmed interest.

### Interruption and cancellation

LiveKit Agents 1.6.1 deliberately does not cancel user code running in
`on_user_turn_completed`. When a later caller turn completes, LiveKit waits for the previous hook,
then interrupts the stale speech handle before it can become a second active response. This avoids
two committed responses, but an unbounded grounding hook would delay the newer turn and waste work.
The hybrid path cannot rely on LiveKit cancellation alone.

Add a call-scoped grounding coordinator that observes LiveKit's `user_state_changed` and
`user_input_transcribed` events. A `new_state == "speaking"` event starts a possible cancellation;
the turn epoch advances when that activity produces non-empty transcript evidence or satisfies the
configured interruption duration and word policy. Raw VAD activity alone must not discard a turn,
because a false interruption could otherwise leave the caller in silence. Each grounding operation
receives the originating epoch and a cooperative cancellation signal. It must check that signal
between bounded lookups, before applying any `CallState` transition, and before injecting context.
A stale operation raises `StopResponse` without generating speech or committing state. A lookup
already executing may finish, but its pure result must be discarded. The complete grounding
operation also has a 75 ms deadline, after which it returns an `unavailable` result rather than
blocking the next turn.

The read path remains idempotent within a caller turn. A turn-scoped cache keyed by the LiveKit
message ID prevents repeated hook execution from repeating retrieval. State transitions are applied
once, only after the epoch and deadline checks pass. Results will not be cached across turns,
because target state and authoritative data may change during a call.

After the hook returns, normal LLM generation, TTS, and playback remain under LiveKit's existing
interruptible speech handling. Tests must verify both phases: barge-in during grounding produces no
stale state or reply, and barge-in during generation interrupts the old speech before the newer
turn's response is scheduled.

### Lookup scheduling

The current repositories use synchronous SQLAlchemy calls on one call-scoped session, and
`KnowledgeBase.search` is synchronous local work. Wrapping these calls directly in
`asyncio.gather` would not make them concurrent; sharing one SQLAlchemy session across threads would
also be unsafe. The initial builder will execute the bounded lookups sequentially and enforce the
75 ms total deadline and 50 ms p95 acceptance target.

The builder must keep retrieval pure and apply `CallState` changes only after result assembly. If
the total budget stops passing as the corpus grows, introduce async adapters or separate
session-scoped read tasks before adding parallelism. Parallel execution is allowed only when each
lookup has an isolated database session, cancellation results can be discarded safely, and tests
show a latency benefit.

If grounding raises an exception, the hook will add an `unavailable` result instructing the model
to say it cannot verify the requested fact and to ask a short clarification or offer follow-up. It
must not silently continue with an ungrounded answer. The worker will log the exception without
including caller text or retrieved content in metrics.

The metrics recorder will add, without storing transcripts or personal data:

- `grounding_applied`
- `grounding_duration_ms`
- `grounding_statuses`
- `grounding_source_types`
- `grounding_result_count`
- `grounding_cancelled`
- `grounding_deadline_exceeded`
- `grounding_needs_clarification`
- `llm_request_count` when exposed by the LiveKit event lifecycle
- capture-tool selection and post-tool generation timings

The existing `tool_calls` fields remain for capture turns and compatibility with the baseline
report. Read-grounded turns will be reported separately from ungrounded conversational turns and
capture-tool turns.

Roll out the change behind a typed setting that defaults to the hybrid path after acceptance. The
legacy read-tool path remains available only during the matched-call validation period and should
be removed after the acceptance criteria pass; it is not an automatic runtime fallback.

## Status

Accepted for implementation.

## Group

Voice latency tuning: Issue 1, tool orchestration latency.

## Assumptions

- The baseline in `docs/project/VOICE_EXPERIENCE_IMPROVEMENT_PLAN.md` is representative enough to
  choose the first orchestration experiment.
- SQLite and local lexical retrieval remain below 25 ms at the current corpus size.
- One LLM generation can produce a natural grounded answer when it receives bounded structured
  facts before generation.
- The current non-realtime LiveKit LLM pipeline continues to support
  `Agent.on_user_turn_completed` and a temporary mutable `ChatContext`.
- LiveKit preserves its current stale-speech interruption behavior, but application code remains
  responsible for bounding and cooperatively abandoning stale grounding work.
- Prospect capture remains infrequent and can retain a second model step until it is measured and
  optimized independently.

## Constraints

- Exact property and unit claims must still originate from SQLite.
- Policy and narrative claims must still originate from source-backed knowledge retrieval.
- Unknown and unavailable results must be stated explicitly rather than filled from model memory.
- Prospect writes must continue through `capture_prospect_interest` and its code-enforced safety
  gate.
- The FastAPI control plane must stay outside the realtime audio path.
- Provider and telephony credentials must not be required for imports, linting, tests, or
  `/health`.
- Grounding must not persist caller text, names, phone numbers, email addresses, or retrieved
  content in the metrics file.
- The change must remain compatible with both configured OpenRouter and direct OpenAI adapters.

## Positions

### Position 1: Pre-LLM read grounding with one response-generation request

Retrieve bounded local facts in `on_user_turn_completed`, inject them into the temporary generation
context, expose only the guarded write tool, and use the LLM once to phrase the answer.

### Position 2: Keep all LLM tools and suppress duplicate calls

Memoize identical tool name and normalized arguments within a turn while retaining the existing
model-selected tool cycle.

### Position 3: Keep LLM tool selection and render tool results with deterministic templates

Let the model choose a read tool, then bypass the post-tool LLM request by converting each tool
result directly into spoken text.

### Position 4: Keep the current path and compare faster models or providers

Retain both model requests and try to reduce each request's latency through provider, region, or
model changes.

## Argument

Position 1 is the project decision. It removes the model request whose only purpose is selecting
among three cheap local read operations while retaining the LLM where it adds value: producing a
short, natural response from grounded facts. The bounded local searches fit within the current
latency budget, and bounded results prevent the prompt from growing with the full database or
knowledge corpus.

Position 2 is lower risk but insufficient. Duplicate suppression would improve four of the 37
baseline tool turns, while all ordinary read-tool turns would still pay for tool selection and
post-tool generation. It should be included as an idempotency guarantee, not treated as the primary
latency fix.

Position 3 preserves model-based intent selection but moves answer selection, ambiguity handling,
multi-fact questions, and conversational phrasing into templates. That would create a second voice
response implementation beside the prompt and would require increasingly complex intent parsing to
avoid reading irrelevant fields. Pre-LLM grounding lets the existing LLM handle those language
tasks in a single request.

Position 4 may improve all turns, but it does not remove unnecessary work and would mix an
orchestration change with provider quality, cost, and routing variables. Provider comparisons
remain useful after the hybrid path has an attributable matched-call result.

Eager local reads are the primary tradeoff of Position 1. Some conversational turns will query both
SQLite and the knowledge base even when no grounded answer is needed. At the measured maximum of
19 ms this is substantially cheaper than another remote model request. The bounds and metrics make
that assumption visible and allow the decision to be revisited if corpus size or storage changes.

Deterministic query parsing is the other material tradeoff. The model currently has an opportunity
to rewrite a raw query before lexical search even though it does not receive structured price or
bedroom parameters. The hybrid path replaces that implicit normalization with explicit,
testable parsing for supported leasing constraints. This can be more predictable, but its recall
must be measured through no-match, clarification, caller-correction, compound-question, and
comparison scenarios before the read tools are removed.

## Implementation Shape

The implementation should remain milestone-scoped:

```text
src/leasing_voice_assistant/
  agent/
    grounding/
      __init__.py         # stable public grounding imports
      models.py           # transport-neutral query, outcome, and state snapshot types
      parser.py           # deterministic query patterns and parsing
      builder.py          # bounded retrieval, result assembly, and state transitions
    prompts.py            # identity and rules for consuming the grounding block
    voice.py              # LeasingVoiceAgent and context injection
  worker/
    main.py               # construct the custom agent and register capture only
    metrics.py            # grounding and remaining tool-cycle measurements
    turn_coordination.py  # LiveKit event observation and cancellation coordination
    tools.py              # separate read callables from the capture LiveKit tool
tests/
  test_agent_grounding.py
  test_agent_prompts.py
  test_agent_voice.py
  test_worker_metrics.py
  test_worker_turn_coordination.py
  test_worker_tools.py
```

This package split clarifies ownership among independently changing grounding concepts. It does
not change the grounding behavior, cancellation and deadline policy, payload contract, state
transition rules, or the worker runtime boundary established by this decision.

This ownership clarification does not change the runtime boundary: LiveKit session and call
lifecycle orchestration remain in `worker/`. Acknowledgment coordination and metrics likewise
remain worker-owned under ADR 0008; `agent/voice.py` depends only on narrow structural protocols.

The provider-independent builder must be directly unit-testable with an in-memory SQLite database.
Worker tests should use LiveKit data types but no room, provider client, credentials, or network.

Implementation order:

1. Extend metrics so the legacy path records the available model/tool phase boundaries.
2. Add the deterministic query parser and tests for supported, unsupported, compound, comparison,
   and indirect caller wording.
3. Add the bounded grounding builder and tests for property, unit, policy, follow-up, ambiguity,
   no-match, clarification, unavailable, target preservation, and per-turn idempotency behavior.
4. Add cancellation coordination and tests for a newer caller turn during grounding and during
   response generation, including false VAD activity that must not discard the pending reply.
5. Add `LeasingVoiceAgent` and inject grounding through `on_user_turn_completed`.
6. Register only `capture_prospect_interest` with the LLM after query-parity tests pass, then update
   prompt rules.
7. Run formatting, linting, and the full credential-free test suite.
8. Run a matched call batch before making any endpointing, response-length, model, or TTS change.

## Acceptance Criteria

Adopt the hybrid path as the only read path when a matched batch contains at least 20 calls and at
least 30 read-grounded turns and shows:

- no LLM function calls to the three read operations in hybrid mode
- no duplicate read execution within a caller turn
- no stale state transition or assistant reply when a newer caller turn begins during grounding
- read-grounded median end-to-end latency at least 1,000 ms lower than the 5,251 ms baseline tool
  median
- read-grounded p90 end-to-end latency no worse than the 6,638 ms baseline tool p90
- grounding p95 no greater than 50 ms at the current data size
- zero invented exact facts in the scripted grounding scenarios
- property-search no-match and caller-correction rates no worse than the matched legacy batch
- correct results or an explicit clarification for indirect constraints, multi-unit comparisons,
  and compound property-plus-policy questions
- no regression in ambiguous-target clarification or prospect capture safety tests
- no increase in recorded call errors

If the latency threshold passes but grounding accuracy fails, keep the legacy path available while
correcting retrieval and context assembly; do not compensate by permitting ungrounded model
answers. If grounding latency exceeds the bound, profile the local builder before introducing
parallel threads or remote infrastructure.

## Implications

- Most property, unit, policy, and FAQ turns use one LLM request instead of a tool-selection and
  post-tool pair.
- Read retrieval becomes deterministic application orchestration rather than model behavior.
- The LLM still decides how to answer, which facts are relevant, and whether to ask a clarification
  from the provided statuses and data.
- Prospect capture keeps its existing model-call and safety behavior, so its latency remains a
  separate optimization target.
- The worker gains a custom agent class, but repository, retrieval, provider, API, and safety
  boundaries remain intact.
- Eager read work increases slightly on conversational turns and must remain bounded and measured.
- Removing read function schemas reduces model prompt size and eliminates the observed duplicate
  read-tool calls by construction.
- Future vector retrieval or a larger database can replace the builder's dependencies without
  changing the LiveKit hook or prospect write boundary.

## Related Decisions

- Use SQLite for authoritative property and unit facts.
- Use local source-backed retrieval for policy and narrative answers.
- Keep the LiveKit worker as the realtime conversation owner.
- Keep FastAPI outside the audio path.
- Enforce prospect capture safety in code rather than in the prompt alone.
- Use provider adapters for LLM construction and comparison.

## Related Artifacts

- `docs/project/VOICE_EXPERIENCE_IMPROVEMENT_PLAN.md`
- `docs/project/VOICE_LATENCY_TUNING_IMPLEMENTATION_PLAN.md`
- `docs/project/adr/0003-knowledge-base-retrieval.md`
- `docs/project/adr/0005-leasing-agent-tools-and-safety-gate.md`
- `docs/project/adr/0006-livekit-sip-call-pipeline.md`
- `src/leasing_voice_assistant/agent/state.py`
- `src/leasing_voice_assistant/agent/tools.py`
- `src/leasing_voice_assistant/agent/prompts.py`
- `src/leasing_voice_assistant/agent/voice.py`
- `src/leasing_voice_assistant/worker/main.py`
- `src/leasing_voice_assistant/worker/metrics.py`
- `src/leasing_voice_assistant/worker/turn_coordination.py`
- `src/leasing_voice_assistant/worker/tools.py`
- `metrics/voice_metrics.jsonl` (local and ignored)

## Related Principles

- Keep the voice agent, grounded answers, and safe prospect capture at the center of the project.
- Remove measured remote work before optimizing already-fast local operations.
- Preserve explicit unknown and ambiguous states.
- Keep write paths safe, explicit, and independently testable.
- Make latency changes one at a time and validate them with matched calls.
- Preserve credential-free local development and tests.

## Notes

This ADR does not change endpointing, interruption thresholds, response-length instructions, LLM
provider or model, greeting generation, TTS, or playback behavior. Those variables remain separate
experiments so the effect of the hybrid grounding path can be attributed to this decision.
