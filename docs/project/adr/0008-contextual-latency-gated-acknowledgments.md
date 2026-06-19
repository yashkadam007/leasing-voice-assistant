# ADR 0008: Contextual Latency-Gated Acknowledgments

## Issue

The implemented latency changes reduce avoidable work, but they cannot eliminate every pause in a
voice conversation. The first post-change call still measured 3,304 ms median end-to-end response
latency and 4,061 ms p90. Approximately 1,639 ms of the median occurred before the caller's turn was
committed, while the remaining delay included LLM generation, TTS startup, and playback scheduling.
The guarded prospect-capture path may also retain a second model phase.

Silence after turn commitment can make the assistant appear unresponsive even when the underlying
latency is acceptable. A short, relevant acknowledgment such as "Let me check the available units"
can establish that the assistant understood the request and is working on it. Unconditional filler,
however, would lengthen fast turns, repeat conspicuously, and create more opportunities for false
interruptions.

Acknowledgments cannot safely mask endpointing delay. Before LiveKit commits a caller turn, the
assistant does not know whether the caller has finished. Speaking during that interval could cut off
a caller or respond to an incomplete utterance. This decision therefore addresses only silence after
turn commitment and remains separate from the latency reductions in
`docs/project/VOICE_EXPERIENCE_IMPROVEMENT_PLAN.md`.

## Decision

Add a call-scoped acknowledgment coordinator to the LiveKit worker. It will schedule a short,
contextual acknowledgment after a caller turn is committed, but play it only when all of the
following are true:

- the turn belongs to an explicitly supported intent class
- no acknowledgment was used on the immediately preceding caller turn
- the per-call acknowledgment limit has not been reached
- substantive response audio has not become ready before the configured delay expires
- the turn and its response generation are still current
- neither the caller nor the assistant is already speaking when playback is due to start

The initial supported intent classes are:

- property or unit search: "Let me check the available options."
- property policy or fee lookup: "Let me check that property information."
- comparison or compound grounded question: "Let me compare those details."
- guarded prospect capture: "One moment while I note that."

When a turn has more than one supported signal, select exactly one class using this precedence:

1. guarded prospect capture
2. comparison or compound grounded question
3. property policy or fee lookup
4. property or unit search

The higher-specificity class wins even when a lower-priority signal is also present. Phrase history
and call limits are applied after class selection. Unit tests must cover every pairwise overlap and
a turn containing all supported read signals.

Use a small curated phrase catalog rather than asking the LLM to generate filler. Each intent class
will have at least three semantically equivalent phrases. Selection will avoid every phrase already
used during the call until the class's pool is exhausted. The wording must describe an action in
progress and must not claim that a fact was found or a prospect was captured before the relevant
operation succeeds.

The first implementation will be a delayed hedge, not a learned latency predictor. Start a
configurable timer when the final user turn is committed. The initial experiment will use a 750 ms
post-commit delay and acknowledgments no longer than 1.2 seconds of expected speech. If substantive
audio becomes ready before acknowledgment playback begins, cancel the acknowledgment. These values
are experiment defaults and must be tuned from measured time to first substantive audio, not treated
as permanent conversation constants.

Acknowledgment and substantive audio must never overlap. If an acknowledgment has started when the
substantive response becomes ready, queue the substantive response immediately after it. Do not wait
for an acknowledgment that is still synthesizing if it can be cancelled cleanly. The coordinator
must use LiveKit speech handles and lifecycle events as the source of playback state; sleeps alone
are insufficient because TTS startup and room playback are asynchronous.

Acknowledgment preparation is best-effort and must remain outside the substantive response's
critical path. Substantive generation, synthesis, and playback must never await acknowledgment
synthesis. An acknowledgment timeout, provider error, cancellation error, or slow first audio must
be contained by the coordinator and recorded as `error` or `cancelled`; it must not delay, cancel,
replace, or fail the substantive response. If substantive audio becomes ready before the first
acknowledgment audio is emitted, cancel or abandon the acknowledgment and let substantive playback
proceed immediately. The only intentional delay permitted is completion of an acknowledgment that
has already begun audible playback.

Before implementing the full coordinator, add a focused LiveKit integration test or local fake that
proves the installed SDK can prepare the substantive response while separately scheduling
acknowledgment speech without cancelling, serializing behind, or duplicating the response. If the
public speech APIs cannot provide this ordering, implement the coordination at the agent generation
or TTS node boundary. Do not depend on private LiveKit attributes.

The proof must also cover the configured TTS provider, not only LiveKit's speech lifecycle. Verify
whether one call-scoped Deepgram client can synthesize acknowledgment and substantive segments
concurrently, whether the SDK serializes them on one connection, and whether provider concurrency or
rate limits introduce contention. Measure substantive TTS time to first audio with acknowledgment
synthesis enabled and disabled. If the provider or adapter serializes the requests or materially
regresses substantive first audio, use an isolated supported synthesis path or suppress the
acknowledgment; do not accept contention as a rollout tradeoff. Provider-backed verification may
require credentials, but the coordinator's unit and integration fakes must remain credential-free.

### Eligibility and context

Use deterministic application context to choose an acknowledgment class:

- `GroundingOutcome` supplies property search, policy, comparison, and compound-question signals.
- the guarded tool lifecycle supplies prospect-capture intent after tool selection.
- ambiguous, `no_match`, `needs_clarification`, unavailable, incomplete, and ordinary social turns
  receive no acknowledgment in the initial rollout.

The coordinator must not add a second general-purpose intent model or make a remote request to choose
filler. If the existing grounding result cannot classify the turn confidently, silence followed by
the substantive response is preferable to an irrelevant phrase.

This design depends on ADR 0007's pre-LLM grounding for contextual read-turn classification. It also
depends on the existing response lifecycle and phase metrics for gating and evaluation. Prospect
capture acknowledgment does not depend on pre-LLM read grounding, but it does depend on the hybrid
tool boundary that leaves only the guarded write tool exposed to the LLM.

### Interruption behavior

Acknowledgments are assistant speech and must remain interruptible. When caller activity satisfies
the configured interruption policy:

1. Stop acknowledgment playback using the normal LiveKit interruption path.
2. Mark the acknowledgment interrupted and never resume or replay it.
3. Cancel or invalidate the stale substantive response through the existing turn epoch behavior.
4. Let the newer caller turn proceed normally, subject to the same eligibility and cooldown rules.

An interrupted acknowledgment still counts against the call limit because replaying another filler
immediately would sound mechanical. Raw VAD activity that LiveKit classifies as a false interruption
must not advance phrase history or schedule a replacement acknowledgment.

The current interruption configuration accepts interruptions with zero recognized words. The
twenty-call baseline also recorded false interruptions. Acknowledgments increase the amount of time
the assistant is speaking, so matched-call rollout must measure false interruptions and successful
barge-ins explicitly. Changing interruption thresholds is not part of this ADR's implementation
experiment; if tuning is required, measure it as a separate variable before enabling acknowledgments
by default.

### Repetition and call limits

Apply all of the following controls:

- no acknowledgment on consecutive caller turns
- no more than two acknowledgments per call in the initial experiment
- no exact phrase reuse within a call while an unused variant exists
- no acknowledgment for an initial greeting, closing, clarification, or response resumption
- no acknowledgment when the caller has already heard substantive audio for the current turn

Phrase selection and history are call-scoped and memory-only. Do not store caller text or the chosen
intent input in metrics.

### Metrics

Extend turn records with content-free acknowledgment fields:

- `acknowledgment_eligible`
- `acknowledgment_class`
- `acknowledgment_scheduled`
- `acknowledgment_started`
- `acknowledgment_outcome`: `completed`, `cancelled`, `interrupted`, `suppressed`, or `error`
- `acknowledgment_start_ms`: caller turn commitment to first acknowledgment audio
- `acknowledgment_duration_ms`
- `substantive_audio_ready_ms`
- `substantive_audio_start_ms`
- `acknowledgment_to_substantive_gap_ms`
- `acknowledgment_phrase_id`, using a stable catalog identifier rather than spoken text

Continue reporting the existing end-to-end latency unchanged. Acknowledgment audio is not the
substantive answer and must not be used to claim a reduction in actual response latency. Add a
separate perceived-response metric from caller turn commitment to the first acknowledgment or
substantive audio, whichever occurs first.

## Status

Accepted for implementation.

## Group

Voice experience: perceived-latency mitigation.

## Assumptions

- A relevant acknowledgment after a genuinely slow committed turn feels more natural than silence.
- The installed LiveKit SDK exposes enough public lifecycle state to coordinate two speech segments.
- The configured TTS provider can prepare a short acknowledgment without delaying substantive TTS;
  this assumption must be verified before rollout.
- ADR 0007 grounding outcomes are reliable enough to classify the initial read-turn intents.
- A two-per-call limit is sufficient to test the experience without dominating the conversation.

## Constraints

- Never speak before LiveKit commits the caller turn.
- Never overlap acknowledgment and substantive response audio.
- Never make an extra LLM request to select or compose an acknowledgment.
- Never imply retrieval or prospect capture succeeded before authoritative completion.
- Never make substantive generation, synthesis, or playback await acknowledgment synthesis.
- Contain every acknowledgment timeout, provider failure, and cancellation failure within the
  acknowledgment coordinator.
- Preserve normal caller barge-in and stale-turn cancellation behavior.
- Keep prospect writes behind the existing code-enforced safety gate.
- Do not require provider or telephony credentials for imports, linting, unit tests, or `/health`.
- Keep acknowledgment state call-scoped and do not persist caller text or personal information.
- Do not count acknowledgment audio as an actual latency reduction.

## Positions

### Position 1: Contextual acknowledgment with delayed, lifecycle-based gating

Schedule curated intent-specific speech after turn commitment and cancel it when substantive audio
becomes ready before the delay expires.

### Position 2: Unconditional acknowledgment on supported intents

Play an acknowledgment immediately after every property, policy, comparison, or capture request.

### Position 3: Prompt the response LLM to begin with filler

Ask the normal response generation to start slow turns with an acknowledgment before giving the
answer.

### Position 4: Keep silence until the substantive answer

Make no perceived-latency change and rely only on actual latency reductions.

## Argument

Position 1 is the project decision. It provides feedback only when the system has observed a real
post-commit delay, and deterministic context keeps the phrase relevant. Curated wording makes
success claims and repetition testable. The cooldown and call limit constrain the additional speech
and interruption exposure.

Position 2 is simpler but makes already-fast turns slower and causes repetition precisely when the
assistant is performing well. It would optimize consistency of behavior rather than conversational
naturalness.

Position 3 cannot hide LLM time to first token because the filler comes from the same request. It
also gives the model another opportunity to overuse generic phrases such as "Sure" and "Of course."
Prompt wording may still control response style, but it is not the latency hedge.

Position 4 has the lowest implementation risk and remains the fallback when the coordinator cannot
meet its timing or quality criteria. Actual latency reduction remains preferable to filler, but the
measured remote stages cannot be reduced to zero and callers benefit from bounded progress feedback
at the tail.

The primary tradeoff is that acknowledgment speech consumes conversational time. A late or
irrelevant acknowledgment can make the response objectively and subjectively worse. The decision
therefore treats cancellation rate, transition gap, repetition, false interruptions, and caller
barge-in as first-class acceptance measures rather than considering any earlier audio a success.

## Implementation Shape

Keep the change inside the worker and metrics boundaries:

```text
src/leasing_voice_assistant/worker/
  acknowledgments.py     # phrase catalog, call-scoped policy, and coordinator state
  agent.py               # expose deterministic grounding classification and turn epoch
  main.py                # bind the coordinator to the LiveKit session
  metrics.py             # acknowledgment and perceived-response measurements
tests/
  test_worker_acknowledgments.py
  test_worker_agent.py
  test_worker_metrics.py
```

Implementation order:

1. Add speech-lifecycle fakes and prove preparation, cancellation, ordering, failure containment,
   and interruption behavior against the installed LiveKit API.
2. Verify configured-provider concurrency and compare substantive TTS first audio with concurrent
   acknowledgment synthesis enabled and disabled.
3. Add the phrase catalog and pure call-scoped eligibility policy with precedence, cooldown, and
   limit tests.
4. Add the coordinator and integrate deterministic grounding and capture classifications.
5. Add acknowledgment metrics without changing existing end-to-end metric semantics.
6. Add a typed rollout setting defaulting to disabled.
7. Run formatting, linting, and the full credential-free test suite.
8. Run the matched disabled-versus-enabled evaluation described below with acknowledgments as the
   only changed voice-experience variable.

## Acceptance Criteria

The historical twenty-call batch cannot serve as the naturalness control because it did not capture
manual naturalness scores. Run a matched A/B evaluation containing at least 20 calls with
acknowledgments disabled and 20 calls with acknowledgments enabled, with at least 30 eligible turns
in each cohort. Use the same scripted scenarios, provider and turn settings, scoring rubric, and
evaluation conditions in both cohorts. Randomize or interleave cohort order where practical, and
have the same reviewer score every call without being told the cohort when recordings permit
blinding.

Enable acknowledgments by default only when that matched evaluation shows:

- no acknowledgment begins before caller turn commitment
- no overlapping acknowledgment and substantive audio
- no acknowledgment synthesis failure or contention delays substantive response generation,
  synthesis, or playback
- no stale acknowledgment or substantive response after a successful barge-in
- zero acknowledgment phrases that falsely imply retrieval or capture success
- exact phrase repetition in no more than 5% of calls
- acknowledgments on no more than two turns per call and never on consecutive turns
- at least 90% of started acknowledgments begin before substantive audio would otherwise have begun
- p90 acknowledgment-to-substantive gap no greater than 400 ms
- no regression in successful barge-in rate
- false-interruption rate no more than one percentage point above the matched disabled batch
- enabled-cohort mean manual naturalness score is at least 0.5 higher than the matched disabled
  cohort on the five-point scale
- no increase in call errors, duplicate responses, unsafe capture attempts, or invented facts

Also review cancellation rate. A rate above 50% indicates that the timer or eligibility policy is
adding unnecessary work even if callers do not hear it; tune the delay before rollout. If TTS startup
causes acknowledgments to begin after the substantive response would have started, reject the
experiment rather than adding longer filler.

## Implications

- Some slow turns provide immediate, relevant progress feedback without changing factual answers.
- Fast turns retain direct answers without ceremonial acknowledgment.
- The worker gains explicit coordination between turn, generation, TTS, and interruption state.
- Evaluation distinguishes perceived response onset from substantive response latency.
- False-interruption exposure may increase because the assistant speaks for longer.
- A larger or prerecorded phrase catalog may be considered later, but is not required initially.

## Related Decisions

- ADR 0006 keeps LiveKit session and turn handling in the worker.
- ADR 0007 provides bounded pre-LLM grounding and call-scoped cancellation coordination.
- Prospect capture remains guarded by deterministic application code.
- Actual latency improvements and perceived-latency mitigation remain separately measured.

## Related Artifacts

- `docs/project/VOICE_EXPERIENCE_IMPROVEMENT_PLAN.md`
- `docs/project/VOICE_LATENCY_TUNING_IMPLEMENTATION_PLAN.md`
- `docs/project/adr/0005-leasing-agent-tools-and-safety-gate.md`
- `docs/project/adr/0006-livekit-sip-call-pipeline.md`
- `docs/project/adr/0007-pre-llm-grounding-for-low-latency-read-turns.md`
- `src/leasing_voice_assistant/worker/agent.py`
- `src/leasing_voice_assistant/worker/main.py`
- `src/leasing_voice_assistant/worker/metrics.py`

## Related Principles

- Preserve natural turn-taking before optimizing silence.
- Prefer useful, contextual language over generic filler.
- Do not disguise actual latency measurements with earlier non-substantive audio.
- Keep grounded answers and safe prospect capture authoritative.
- Change one voice-experience variable per matched evaluation batch.

## Notes

This ADR does not change endpointing, interruption thresholds, response length, LLM provider or
model, grounding behavior, tool safety, TTS provider, or greeting behavior. It does not introduce
background music, earcons, generic thinking sounds, or acknowledgments generated by the response
LLM. Those are separate decisions if later evidence justifies them.
