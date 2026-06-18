# ADR 0004: Provider Adapter Layer

## Issue

Milestone 4 needs a provider boundary for the real-time voice stack before the LiveKit worker starts wiring concrete speech and model SDKs into the call loop. The project already has separate API and worker entrypoints, a SQLite data layer, and local knowledge retrieval. The next risk is coupling the worker directly to Deepgram and OpenRouter details in a way that makes testing, configuration errors, and later provider changes harder than necessary.

The provider layer must support three core behaviors:

- build speech-to-text, text-to-speech, and LLM clients for the LiveKit worker
- keep provider credentials optional for linting, tests, imports, and `/health`
- fail with explicit configuration errors when the worker tries to build a selected provider without required credentials

The key decision is how thin the adapter layer should be. It should hide provider-specific construction and configuration from the worker without pretending the project needs broad multi-provider support before the first call path works.

## Decision

Use a small provider adapter package under the shared application package. Define narrow STT, TTS, and LLM build contracts, implement only the planned defaults for this submission, and expose a factory that selects providers from typed settings.

The initial package layout will add:

```text
src/
  leasing_voice_assistant/
    providers/
      __init__.py
      errors.py
      factory.py
      stt/
        __init__.py
        base.py
        deepgram.py
      tts/
        __init__.py
        base.py
        deepgram.py
      llm/
        __init__.py
        base.py
        openrouter.py
tests/
  test_provider_factory.py
```

Use the existing provider selector settings as the public configuration surface:

```env
STT_PROVIDER=deepgram
TTS_PROVIDER=deepgram
LLM_PROVIDER=openrouter
DEEPGRAM_API_KEY=...
OPENROUTER_API_KEY=...
```

Default provider selections are:

- Deepgram for STT
- Deepgram for TTS
- OpenRouter for LLM

The factory should validate credentials only when constructing provider clients. Importing the worker, running repository or retrieval tests, and serving `/health` must not require Deepgram, OpenRouter, LiveKit, or telephony credentials.

Adapter contracts should return the concrete objects expected by LiveKit Agents or the chosen OpenAI-compatible client at the point of worker integration. The rest of the worker should depend on the factory and lightweight adapter contracts, not provider SDK constructors scattered through call setup.

## Status

Accepted for implementation.

## Group

Milestone 4: Provider Adapter Layer.

## Assumptions

- LiveKit Agents remains the real-time voice framework.
- Deepgram remains the default STT and TTS provider for the first working call path.
- OpenRouter remains the default LLM provider and can be reached through an OpenAI-compatible integration.
- The first implementation only needs provider construction, selection, and validation; live call behavior belongs to the SIP pipeline milestone.
- Local tests should be able to exercise provider selection without network access or real provider credentials.
- Provider model and voice names can be environment-driven with sensible defaults once concrete SDK wiring is added.

## Constraints

- Keep the API and worker as separate runtime entrypoints.
- Do not require provider or telephony credentials for linting, tests, imports, or `/health`.
- Do not add unused provider stubs for vendors that are not part of the submission path.
- Keep provider-specific SDK details out of leasing tools, repositories, knowledge retrieval, and agent safety logic.
- Missing credentials must produce explicit errors that name the selected provider and required setting.
- The adapter layer must stay small enough to support the voice agent rather than becoming a general provider framework.

## Positions

### Position 1: Thin provider factory with default-only adapters

Define minimal provider protocols and one factory that constructs Deepgram STT, Deepgram TTS, and OpenRouter LLM clients from settings. Add no alternate provider implementations until there is a concrete need.

### Position 2: Broad provider abstraction with multiple interchangeable backends

Create general STT, TTS, and LLM abstractions with several provider implementations, normalized request and response schemas, and a richer configuration matrix.

### Position 3: Direct provider SDK construction inside the LiveKit worker

Skip a provider package and instantiate Deepgram and OpenRouter clients directly in worker call setup.

## Argument

Position 1 is the project decision. A thin factory gives the worker one place to ask for STT, TTS, and LLM clients while keeping concrete SDK setup, credential checks, and provider-specific defaults out of the call lifecycle. This is enough abstraction for the assignment because the goal is a working grounded leasing call, not a provider marketplace.

Position 2 adds flexibility the project does not yet need. Multiple unused providers would increase dependencies, tests, configuration combinations, and documentation without improving the first SIP call path. If another provider becomes necessary later, it can be added behind the same factory boundary after the default path is working.

Position 3 is simpler in the first few lines of code, but it puts provider decisions in the highest-pressure runtime module. The worker will already need to manage LiveKit room state, turn detection, leasing tools, call metadata, and safety behavior. Keeping provider construction behind a factory makes that module easier to test and less likely to accumulate unrelated SDK details.

The adapter contracts should be intentionally modest. They do not need to normalize every streaming event or invent a provider-agnostic audio protocol. LiveKit Agents already defines much of the operational shape. The project boundary is provider selection and construction, plus explicit validation before a real worker session starts.

## Implications

- Worker imports and local tests remain credential-free until provider clients are explicitly built.
- Provider selection tests can use settings objects and assert explicit errors without making network calls.
- Future provider changes are localized to `providers/` and settings, with limited worker changes.
- The first worker integration can focus on using the factory output with LiveKit Agents rather than parsing environment variables directly.
- The codebase should avoid abstracting provider runtime behavior that LiveKit Agents already owns.
- OpenRouter-specific base URL, model name, and headers should live in the OpenRouter adapter or settings, not in leasing tools.
- Deepgram STT and TTS may share a credential, but they should remain separate adapter selections because they serve different runtime roles.

## Related decisions

- Use LiveKit Agents as the voice agent framework.
- Use Deepgram for STT and TTS by default.
- Use OpenRouter for LLM by default.
- Keep provider credentials optional for linting, tests, imports, and `/health`.
- Keep the LiveKit worker separate from the FastAPI control plane.
- Use provider adapters for STT, TTS, and LLM instead of direct worker coupling.

## Related requirements

- Worker can build STT, LLM, and TTS through the factory.
- Default config is Deepgram STT, Deepgram TTS, and OpenRouter LLM.
- Missing credential errors are explicit.
- Unit tests cover provider selection and missing credentials.
- No unused future-provider stubs are required for the submission.
- Live call wiring is deferred to the SIP pipeline milestone.

## Related artifacts

- `brief.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/STATUS.md`
- `docs/project/adr/0001-project-foundation-and-runtime.md`
- `docs/project/adr/0002-sqlite-domain-model-and-seed-data.md`
- `docs/project/adr/0003-knowledge-base-retrieval.md`
- Future `src/leasing_voice_assistant/providers/`
- Future `tests/test_provider_factory.py`
- Future LiveKit worker provider integration

## Related principles

- Keep the voice agent as the center of the project.
- Prefer small milestone-scoped changes over broad infrastructure.
- Keep local setup and reviewer verification straightforward.
- Keep runtime boundaries clear.
- Make configuration failures explicit and actionable.
- Avoid letting provider SDK details leak into domain tools or safety logic.

## Notes

This ADR intentionally does not decide the final LiveKit SIP call flow, turn detection settings, leasing agent prompt, tool schemas, prospect capture safety gate, or evaluation approach. It only establishes the provider construction boundary needed before wiring the real-time call pipeline.
