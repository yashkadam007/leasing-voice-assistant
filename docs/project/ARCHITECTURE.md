# Leasing Voice Assistant Architecture

## Purpose

This project implements a real-time leasing voice assistant for inbound phone calls. A prospective renter calls a phone number, speaks with a voice AI agent, asks grounded questions about available units and leasing policies, and can be registered as a prospect once the agent has enough confidence in the caller and property details.

The implementation will use LiveKit Agents for the realtime voice loop, LiveKit SIP with Twilio for telephony, SQLite for application data, Deepgram for speech-to-text and text-to-speech, and OpenRouter for the LLM through a thin provider adapter layer.

## High-Level Flow

```text
Caller
  -> Twilio phone number
  -> LiveKit SIP inbound trunk
  -> LiveKit room
  -> LiveKit Python agent worker
     -> Deepgram STT adapter
     -> OpenRouter LLM adapter
     -> Leasing tools
        -> SQLite property/prospect database
        -> local knowledge-base retrieval
     -> Deepgram TTS adapter
  -> caller hears response

FastAPI control plane
  -> health
  -> database setup and seed helpers
  -> minimal prospect verification endpoint
```

## Runtime Components

### LiveKit SIP and Twilio

Twilio provides the phone number and routes inbound calls to LiveKit SIP. LiveKit creates or joins a room for the call. The LiveKit agent worker joins that room as an AI participant and handles the bidirectional audio conversation.

The SIP path is the primary delivery path for the assignment. A browser-based LiveKit room can be added later as a developer fallback, but it is not the core target.

### LiveKit Agent Worker

The worker owns the realtime conversation:

- joins assigned LiveKit rooms
- parses SIP/call metadata
- initializes STT, LLM, TTS, VAD, and turn detection
- registers leasing-specific tools
- maintains per-call conversation state
- speaks short, natural, grounded answers
- calls the prospect capture tool only after safety checks pass

The worker should depend on provider interfaces rather than concrete provider SDKs directly.

### FastAPI Control Plane

FastAPI is intentionally small. It should not become a CRM, admin app, or observability surface. Its responsibilities are limited to what helps a reviewer run and verify the assignment:

- health checks
- database initialization support
- seed-data support
- one read-only verification endpoint for prospects and interests, if useful for demo review

LiveKit token, dispatch, call-history, transcript, and tool-event endpoints are deferred unless they become necessary to place and verify the demo call.

### SQLite Application Database

SQLite stores authoritative structured data:

- properties
- units
- prospects
- prospect interests

The agent must use structured database tools for exact property facts such as rent, bedrooms, availability, parking, pet policy, and unit status.

### Knowledge Base

The knowledge base stores less structured leasing content:

- application process
- deposits
- lease terms
- general pet rules
- property descriptions
- FAQ content

Initial retrieval should use local files plus SQLite FTS or a lightweight lexical ranker. The knowledge base is intentionally small: one or two property fact/narrative files plus a general leasing FAQ are enough if answers remain grounded and unknowns are handled gracefully. Vector retrieval is deferred because the assignment values a working, natural voice agent over broad retrieval infrastructure.

## Provider Adapter Architecture

Provider implementations should be replaceable where the LiveKit worker builds STT, TTS, and LLM clients. The first implementation only needs Deepgram STT, Deepgram TTS, and OpenRouter LLM. The adapter layer exists to keep provider SDK details out of the worker, not to support every provider up front.

Proposed package shape:

```text
app/providers/
  stt/
    base.py
    deepgram.py
  tts/
    base.py
    deepgram.py
  llm/
    base.py
    openrouter.py
  factory.py
```

Each adapter exposes a small build contract:

```python
class STTProvider(Protocol):
    def build(self) -> object: ...

class TTSProvider(Protocol):
    def build(self) -> object: ...

class LLMProvider(Protocol):
    def build(self) -> object: ...
```

The factory selects implementations from environment variables:

```env
STT_PROVIDER=deepgram
TTS_PROVIDER=deepgram
LLM_PROVIDER=openrouter
```

## Agent Tool Boundaries

The agent should have narrow, explicit tools:

- `search_properties`: find matching properties or units from caller wording.
- `get_unit_details`: read authoritative unit facts.
- `search_knowledge_base`: retrieve policy/process/FAQ content.
- `capture_prospect_interest`: create or update a prospect and interest after safety checks.
- optional `end_conversation`: close the call politely only if it maps to real LiveKit call control; otherwise this remains a prompt behavior.

Tools should return structured data and enough source context for the agent to answer without guessing.

## Prospect Capture Safety

The prospect write path must be gated. The capture tool should reject writes unless:

- caller phone number is available from SIP metadata or equivalent call context
- caller name is known or explicitly confirmed
- property or unit resolution confidence meets the threshold
- the caller has indicated interest in that property/unit
- ambiguity has been resolved through a clarification question

Rejected writes should return structured reasons such as `missing_name`, `ambiguous_property`, `low_confidence`, or `needs_confirmation`.

## Grounding Rules

The agent must:

- use SQLite tools for exact property and unit facts
- use the knowledge retrieval tool for leasing policies and broader FAQ answers
- say when a fact is unavailable
- ask short clarification questions when property identity is ambiguous
- avoid recording interest until the safety gate passes

## Key Tradeoffs

- **LiveKit SIP over direct Twilio media streaming:** LiveKit gives a higher-level realtime agent loop and room model, which should reduce audio plumbing risk. Direct Twilio media streaming remains a reasonable fallback, but it would put more call-state and audio handling code in this repository.
- **SQLite and local retrieval over hosted services:** SQLite and local KB search keep the demo runnable from a clean checkout with fewer credentials. This is sufficient for one or two properties and keeps attention on grounded voice behavior.
- **Thin adapters over broad provider support:** The worker should not be tangled with provider SDK details, but extra provider stubs are deferred. A small working Deepgram/OpenRouter path is more valuable than unused abstraction.
- **Minimal FastAPI over admin/debug tooling:** Reviewers need to run the app, place a call, and verify a prospect was written. Anything beyond that risks turning the project into a CRM, which the brief explicitly excludes.

## Key Architectural Influences

The architecture borrows from `/Users/yash/stratex/bitbucket/voice-ai`:

- FastAPI control plane
- separate LiveKit worker
- LiveKit dispatch/metadata pattern
- service and repository boundaries
- testable tool layer

It deliberately omits the reference app's broader agent registry/admin scope until needed.
