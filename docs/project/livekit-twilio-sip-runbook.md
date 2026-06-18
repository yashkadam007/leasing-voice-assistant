# LiveKit and Twilio SIP Runbook

This runbook covers the manual Milestone 6 smoke test for inbound phone calls.
The FastAPI control plane is not in the realtime audio path.

## Required Environment

Set these values in `.env` or the worker process environment:

```sh
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
DEEPGRAM_API_KEY=...
OPENROUTER_API_KEY=...
DATABASE_URL=sqlite:///leasing_voice_assistant.db
```

Provider defaults:

```sh
STT_PROVIDER=deepgram
TTS_PROVIDER=deepgram
LLM_PROVIDER=openrouter
DEEPGRAM_STT_MODEL=nova-3
DEEPGRAM_TTS_MODEL=aura-2-thalia-en
OPENROUTER_MODEL=openai/gpt-4o-mini
```

## LiveKit SIP Setup

1. Create or select a LiveKit Cloud project.
2. Configure a SIP inbound trunk for the Twilio phone number.
3. Configure an inbound dispatch rule that places calls into a LiveKit room.
4. Ensure the SIP participant forwards caller and call metadata when available.

The worker recognizes common attributes such as `sip.phoneNumber`, `sip.from`,
`sip.callSid`, `twilio.from`, `twilio.callSid`, `sip.trunkID`, and
`sip.trunkName`. Missing phone metadata is allowed; prospect capture will be
rejected by the safety gate with `missing_phone`.

## Twilio Setup

1. Buy or select a Twilio voice number.
2. Route inbound calls from that number to the LiveKit SIP trunk.
3. Confirm the caller ID is passed through to LiveKit SIP participant metadata.

## Start The Worker

```sh
UV_CACHE_DIR=.uv-cache uv run leasing-voice-worker
```

The worker should connect to LiveKit and wait for room jobs. Missing LiveKit
settings fail fast at startup. Provider credentials are required only when the
worker starts a real call session.

## Manual Smoke Test

1. Start the worker.
2. Place a call to the Twilio number, or create an outbound SIP test call with
   a generated room and participant identity:

   ```sh
   UV_CACHE_DIR=.uv-cache uv run leasing-voice-test-call
   ```

3. Confirm LiveKit creates or selects a room and assigns the worker job.
4. Ask about an exact property, such as "Aurora Heights".
5. Ask a policy question, such as "What is the application fee?"
6. Ask about a specific unit, such as "8A".
7. Ask to be contacted or to schedule follow-up.
8. Confirm the assistant asks for required safe details before capture.
9. End the call and confirm the assistant closes politely.

Expected result: the worker joins the room, uses provider-backed voice clients,
answers from structured data or the local knowledge base, and only writes a
prospect interest when the safety gate permits it.
