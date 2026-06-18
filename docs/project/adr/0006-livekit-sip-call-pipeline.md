# ADR 0006: LiveKit SIP Call Pipeline

## Issue

Milestone 6 needs to turn the importable worker placeholder into the primary inbound phone-call runtime. The project already has a FastAPI control plane, SQLite-backed leasing data, local knowledge retrieval, provider adapters, and agent tools with a code-enforced prospect capture safety gate. The next boundary is the LiveKit SIP pipeline that receives a Twilio-routed phone call, joins the assigned LiveKit room, builds the realtime voice stack, registers leasing tools, and manages the call lifecycle.

The pipeline must support five core behaviors:

- receive inbound calls through LiveKit SIP and Twilio
- parse caller and call metadata into per-call agent state
- build STT, LLM, and TTS clients through the provider factory
- register the leasing tool surface for grounded answers and safe prospect capture
- let the agent handle multi-turn questions and end the call politely

The key decision is where call orchestration belongs. LiveKit should own room, participant, audio, and realtime agent lifecycle concerns, while local code should own provider construction, metadata mapping, leasing tool registration, and conservative call-state behavior.

## Decision

Use LiveKit Agents as the worker runtime for the inbound SIP call path. The worker will be a separate process entrypoint that connects to LiveKit, receives room jobs, initializes a call-scoped agent session, builds provider clients through the existing provider factory, registers the Milestone 5 leasing tools, and seeds per-call state from SIP participant metadata.

The initial package layout should keep the worker entrypoint narrow and move call-specific behavior into testable helpers:

```text
src/
  leasing_voice_assistant/
    worker/
      __init__.py
      main.py
      call_context.py
      prompts.py
      tools.py
tests/
  test_worker_import.py
  test_worker_call_context.py
```

The worker should use this responsibility split:

- `main.py`: process entrypoint, LiveKit worker options, job/session startup, and top-level error handling.
- `call_context.py`: extraction and normalization of caller phone number, room name, participant identity, call SID, and SIP trunk metadata.
- `prompts.py`: initial realtime agent instructions that keep responses short, grounded, and leasing-focused.
- `tools.py`: LiveKit function-tool registration backed by the existing `leasing_voice_assistant.agent` domain functions.

Inbound dispatch should use LiveKit's room/job model rather than a custom FastAPI dispatch endpoint. Twilio should route calls to LiveKit SIP, LiveKit should create or select the room, and the worker should join jobs assigned by LiveKit. FastAPI remains a control plane and should not be inserted into the realtime audio path.

SIP metadata parsing should be tolerant. The worker should prefer explicit SIP participant attributes for caller phone number and call identifiers, but it must handle missing fields by leaving the state unset and allowing the prospect capture safety gate to reject writes with `missing_phone`. Metadata parsing must be unit-testable without LiveKit, Twilio, provider credentials, or network access.

The provider factory remains the only place where STT, TTS, and LLM clients are built. The worker may fail fast with explicit configuration errors when a real call session needs selected providers and required credentials are absent. Imports, tests, `/health`, and metadata helper tests must remain credential-free.

Turn detection and voice configuration should start with conservative defaults tuned for a leasing phone conversation:

- speech responses should be concise and natural
- the agent should allow caller interruptions where supported by LiveKit
- endpointing should favor not cutting off callers over maximum speed
- VAD and turn-detection settings should be centralized in worker setup for later tuning

Ending a call should initially be prompt-led and polite. A dedicated hangup or `end_conversation` tool should only be added if LiveKit exposes a concrete call-control action that can be invoked safely from the agent runtime.

The milestone should include a local runbook for the LiveKit and Twilio SIP setup. The runbook can document required environment variables, trunk routing, worker startup, and a manual inbound-call smoke test without requiring automated tests to place a real phone call.

## Status

Accepted for implementation.

## Group

Milestone 6: LiveKit SIP Call Pipeline.

## Assumptions

- LiveKit Agents remains the realtime voice framework.
- LiveKit SIP with Twilio is the primary telephony path.
- Deepgram remains the default STT and TTS provider.
- OpenRouter remains the default LLM provider.
- LiveKit room/job assignment is available for inbound SIP calls.
- Caller phone number can usually be derived from SIP participant attributes, but it may be absent or provider-specific.
- Local tests should validate worker imports, configuration behavior, and metadata mapping without real LiveKit, Twilio, Deepgram, or OpenRouter credentials.
- Manual verification will be needed for the real inbound phone-call path.

## Constraints

- Keep the API and worker as separate runtime entrypoints.
- Do not put FastAPI in the realtime audio path.
- Do not require provider, LiveKit, or telephony credentials for linting, tests, imports, or `/health`.
- Keep provider SDK construction behind the existing provider factory.
- Keep leasing-specific tool logic in the `agent` domain package; worker tool wrappers should only adapt it to LiveKit.
- Do not write prospects from raw metadata or prompt assumptions; the Milestone 5 safety gate remains authoritative.
- Do not add a browser fallback as the primary call path.
- Keep call lifecycle code small enough to support the assignment rather than becoming a generalized contact-center worker.

## Positions

### Position 1: LiveKit job-driven worker with local call-context and tool adapters

Use LiveKit Agents to receive inbound SIP room jobs. Keep worker orchestration in `worker/`, parse metadata into call state through a local helper, build providers through the factory, and register LiveKit function tools backed by the existing domain tools.

### Position 2: FastAPI-mediated dispatch and call setup

Add FastAPI endpoints that receive telephony or dispatch callbacks, prepare call metadata, and instruct the worker which rooms or calls to join.

### Position 3: Direct Twilio media streaming worker

Bypass LiveKit SIP and implement direct Twilio media streaming, audio transport, and call-control handling inside this repository.

## Argument

Position 1 is the project decision. LiveKit Agents and LiveKit SIP are already the chosen realtime and telephony framework, and they should own the hardest audio and room lifecycle concerns. The local worker can stay focused on assignment-specific behavior: mapping call metadata, constructing selected providers, registering leasing tools, and enforcing grounded conversation rules through prompt and tool boundaries.

A FastAPI-mediated path adds an extra internal network boundary without improving the primary call experience. The control plane is useful for health checks, setup support, and reviewer verification, but realtime audio and agent lifecycle work belong in the worker. Keeping FastAPI out of this path also avoids making API availability a prerequisite for an active call when the worker and LiveKit can handle the room job directly.

Direct Twilio media streaming would give lower-level control but would increase project risk. It would require this repository to handle audio transport details, streaming protocol behavior, realtime turn handling, and more provider plumbing. LiveKit SIP exists to absorb those concerns and gives the project a room model that matches the selected agent framework.

Metadata parsing must be deliberately defensive. Phone numbers and call identifiers are essential for prospect capture and demo verification, but telephony attributes can vary by trunk or provider. The right behavior is to normalize the fields we recognize, expose missing values clearly in call state, and rely on the capture safety gate to block unsafe writes.

The worker should fail late enough to preserve local developer ergonomics and early enough to make real-call misconfiguration obvious. Importing the worker should not validate provider or telephony credentials. Starting a real LiveKit session and building providers should produce explicit missing-credential errors.

Turn-detection defaults should be treated as configuration, not domain logic. The first implementation should choose conservative settings that work for short leasing conversations, then leave later tuning to the end-to-end milestone after real call behavior is observed.

## Implications

- The worker becomes the owner of realtime call sessions while FastAPI remains a small control plane.
- Provider credentials are required for real calls but not for local tests or imports.
- Call metadata mapping gets its own focused tests.
- The Milestone 5 tool safety gate remains the final authority for prospect writes.
- A real inbound call cannot be fully verified by unit tests; the milestone needs a manual LiveKit/Twilio runbook and smoke-test checklist.
- Tool registration can remain thin because the domain behavior is already testable outside LiveKit.
- Missing caller phone metadata should degrade into safe capture rejection, not a worker crash.
- Future transcript or call-event persistence can be added later if demo debugging requires it.

## Related decisions

- Use LiveKit Agents as the voice agent framework.
- Use LiveKit SIP/Twilio for primary telephony.
- Keep FastAPI as a control plane, not the realtime call owner.
- Use Deepgram for STT and TTS by default.
- Use OpenRouter for LLM by default.
- Use provider adapters for STT, TTS, and LLM construction.
- Enforce prospect capture safety inside the agent tool layer.

## Related requirements

- Inbound phone call reaches a LiveKit room.
- Worker joins the assigned room and speaks.
- Caller can ask multiple leasing questions during the call.
- Agent can use property, unit, knowledge-base, and prospect capture tools during a call.
- Caller phone number is mapped into call state when SIP metadata provides it.
- Missing phone metadata does not create unsafe prospect records.
- Call can end politely.
- Documentation explains LiveKit SIP and Twilio setup for a manual smoke test.

## Related artifacts

- `brief.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/STATUS.md`
- `docs/project/adr/0001-project-foundation-and-runtime.md`
- `docs/project/adr/0002-sqlite-domain-model-and-seed-data.md`
- `docs/project/adr/0003-knowledge-base-retrieval.md`
- `docs/project/adr/0004-provider-adapter-layer.md`
- `docs/project/adr/0005-leasing-agent-tools-and-safety-gate.md`
- Future `src/leasing_voice_assistant/worker/main.py`
- Future `src/leasing_voice_assistant/worker/call_context.py`
- Future `src/leasing_voice_assistant/worker/prompts.py`
- Future `src/leasing_voice_assistant/worker/tools.py`
- Future `tests/test_worker_call_context.py`
- Future LiveKit/Twilio SIP runbook

## Related principles

- Keep the voice agent as the center of the project.
- Keep runtime boundaries clear.
- Prefer LiveKit-owned realtime primitives over custom audio plumbing.
- Ground exact facts in structured data.
- Ground policy and narrative answers in retrievable source content.
- Keep write paths safe, explicit, and testable.
- Preserve credential-free local linting, tests, imports, and health checks.
- Prefer small milestone-scoped changes over broad infrastructure.

## Notes

This ADR intentionally does not decide final end-to-end conversation tuning, prospect capture wording, transcript persistence, call recording evidence, or evaluation design. Those decisions belong to later milestones after the SIP call path can carry a real multi-turn conversation.
