# Voice Experience Improvement Plan

## Goal

Make calls feel more natural and reduce awkward delays. First capture the current baseline; later
iterations will address one measured issue at a time and compare the same metrics again.

## Current Voice Path

```text
Caller audio
  -> LiveKit turn detection
  -> Deepgram STT
  -> OpenAI LLM
  -> optional property, knowledge, or prospect tool
  -> Deepgram TTS
  -> caller hears response
```

## Initial Observed Issues

Before baseline instrumentation, the repository and initial feedback indicated:

1. There is no recorded latency or naturalness baseline yet.
2. Fixed endpointing allows 0.8 to 1.5 seconds before downstream response processing begins.
3. Grounded answers may need a tool call and another LLM step, adding delay.
4. Existing latency values are logged but not summarized.
5. Tool execution duration is not included in the current latency summary.
6. The single default TTS voice has not been compared or formally reviewed for naturalness.
7. Interruption handling is enabled, but false interruptions and failed barge-ins are not measured.
8. The prompt may produce repetitive acknowledgements or form-like prospect capture turns.

The following still need confirmation from real call recordings: unnatural pronunciation or
prosody, repeated phrases, caller cutoffs, STT errors, overly long replies, and whether tool turns
are actually slower than non-tool turns.

## Metrics To Capture

### Latency

- Caller stops speaking to final transcript
- End-of-turn detection delay
- LLM time to first token
- Tool execution duration, grouped by tool
- TTS time to first audio byte
- Playback latency
- Caller stops speaking to first assistant audio (end-to-end response latency)
- Assistant response duration

Report p50, p90, p95, maximum, and sample count. Separate tool and non-tool turns.

### Conversation Quality

- Overall naturalness score, 1 to 5
- Voice/prosody score, 1 to 5
- Pacing score, 1 to 5
- Repeated acknowledgement rate
- Replies longer than two spoken sentences
- Caller repetition or correction rate
- Successful barge-in rate and stop latency
- False interruption and premature endpoint rates
- STT accuracy for names, properties, unit numbers, dates, prices, emails, and phone numbers

## Metrics Measurement Approach

Keep measurement local for now. Write one JSON object per line to an ignored JSONL file so the data
is structured without adding a database, dashboard, OpenTelemetry, or external service.

Create two record types:

- `turn`: one record for each completed assistant turn
- `call_summary`: one record when the call closes

Each turn record should contain:

```json
{
  "record_type": "turn",
  "timestamp": "2026-06-19T12:00:00Z",
  "call_id": "call-123",
  "turn_id": 2,
  "has_tool_call": true,
  "tool_name": "get_unit_details",
  "tool_duration_ms": 85,
  "transcription_ms": 210,
  "end_of_turn_ms": 820,
  "llm_ttft_ms": 430,
  "tts_ttfb_ms": 260,
  "playback_ms": 90,
  "e2e_ms": 1810,
  "interrupted": false
}
```

Use LiveKit's existing message metrics where available. Add monotonic timers only for missing values,
starting with tool duration. Do not store phone numbers, emails, names, or full transcripts in the
metrics file.

Add a small local summary command that reads the JSONL file and prints:

- sample count, p50, p90, p95, and maximum for every latency field
- separate end-to-end latency for tool and non-tool turns
- duration grouped by tool name
- interruption count and error count
- the slowest five turns with `call_id` and `turn_id`

## Baseline Procedure

1. Capture metrics from at least 20 representative sample calls.
2. Include at least 5 turns that use property, knowledge, or prospect tools.
3. Record a manual 1-to-5 naturalness score for each call.
4. Run the summary command and inspect the slowest turns in the normal call logs.
5. Choose the largest measured delay, make one change, then repeat the same sample scenarios.

Keep the JSONL output and summary report out of Git. If local files become difficult to compare or
production monitoring is needed, replace the local writer with an OpenTelemetry exporter later.

## Twenty-Call Baseline

Baseline captured on 2026-06-19 using 20 scripted calls covering grounded property facts,
knowledge-base answers, ambiguous requests, unsupported questions, prospect capture,
interruptions, and natural call closing.

### Summary

- Calls: 20
- Assistant records: 141
- User-response turns with end-to-end measurements: 118
- Tool turns with end-to-end measurements: 37
- Non-tool turns with end-to-end measurements: 81
- Interruptions: 19
- Errors: 0

The calls did not include manual naturalness, voice/prosody, or pacing scores, so this baseline
supports latency analysis but does not yet establish the conversation-quality baseline described
above.

### Latency Results

| Metric | Count | p50 | p90 | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tool execution | 37 | 13 ms | 18 ms | 18 ms | 19 ms |
| Transcription | 118 | 1,631 ms | 2,767 ms | 2,962 ms | 3,803 ms |
| End-of-turn detection | 118 | 1,887 ms | 3,209 ms | 3,466 ms | 4,146 ms |
| LLM time to first token | 121 | 884 ms | 1,279 ms | 1,581 ms | 2,199 ms |
| TTS time to first byte | 141 | 487 ms | 1,156 ms | 1,205 ms | 1,412 ms |
| Playback latency | 141 | 18 ms | 1,285 ms | 2,484 ms | 11,913 ms |
| End-to-end response | 118 | 3,410 ms | 5,916 ms | 6,427 ms | 7,386 ms |
| Assistant response duration | 141 | 6,929 ms | 15,305 ms | 20,166 ms | 21,978 ms |
| Call duration | 20 | 92,996 ms | 140,734 ms | 142,506 ms | 155,240 ms |

Transcription delay and end-of-turn delay overlap in the user-input phase and must not be added
together. Likewise, the aggregate TTS and playback tails include initial greetings and should not
be interpreted as steady-state response playback.

### Tool and Non-Tool Turns

| Turn type | Count | p50 E2E | p90 E2E | p95 E2E | Maximum E2E |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tool | 37 | 5,251 ms | 6,638 ms | 6,731 ms | 7,386 ms |
| Non-tool | 81 | 2,918 ms | 4,083 ms | 4,850 ms | 5,645 ms |

Tool turns add approximately 2.33 seconds at the median even though local tool execution takes at
most 19 ms. The delay is therefore in tool orchestration, primarily the model round trips required
to select a tool and turn its result into a spoken response, rather than in SQLite or local
knowledge retrieval.

Observed end-to-end latency by tool was:

| Tool | Response turns | p50 E2E | p90 E2E | Maximum E2E |
| --- | ---: | ---: | ---: | ---: |
| `search_knowledge_base` | 6 | 6,526 ms | 6,854 ms | 7,065 ms |
| `capture_prospect_interest` | 3 | 5,452 ms | 6,199 ms | 6,386 ms |
| `search_properties` | 17 | 5,095 ms | 6,437 ms | 7,386 ms |
| `get_unit_details` | 11 | 5,026 ms | 5,783 ms | 6,490 ms |

The six measured knowledge-base response turns made nine knowledge-base calls. Several turns made
the same tool call twice, so duplicate retrieval is one concrete target for investigation.

### Findings

1. **Tool orchestration is the largest response-latency problem.** Non-tool median latency is near
   the assignment's acceptable two-to-three-second range, while tool median latency is 5.25
   seconds. Existing LLM TTFT metrics do not expose each model phase in a tool turn.
2. **End-of-turn detection remains the largest steady-state non-tool delay.** Its 1.89-second median
   and 3.21-second p90 are consistent with the initial five-call sample and the current conservative
   fixed endpointing configuration.
3. **Tool-driven replies are too long.** Tool response duration has a 13.11-second median versus
   5.06 seconds for non-tool replies. Long property and policy summaries make the call feel slower
   even after audio begins and increase opportunities for barge-in.
4. **Interruption behavior needs classification and tuning.** Nineteen of 141 assistant records
   were interrupted, and the raw call summaries contain six false-interruption events across three
   calls. The current configuration accepts interruptions with zero recognized words.
5. **Normal playback is healthy.** User-response playback latency is generally around 16 to 21 ms.
   The aggregate playback tail is dominated by initial greeting records and should not drive
   steady-state playback optimization.
6. **The reporter mixes different assistant record types.** Twenty calls produced 141 assistant
   records but only 118 user-response measurements. Twenty records are expected initial greetings;
   three additional assistant continuations or resumptions have no end-to-end measurement. Reports
   should separate greetings, user-response turns, and assistant continuations.
7. **The larger sample confirms the initial baseline.** Overall median end-to-end latency changed
   from 3,369 ms after five calls to 3,410 ms after 20 calls. Tool and endpointing delays remain the
   same dominant patterns rather than being artifacts of the first five calls.

## Implemented Latency Improvements

The first four issues in `VOICE_LATENCY_TUNING_IMPLEMENTATION_PLAN.md` were implemented, followed
by ADR 0008's perceived-latency mitigation:

1. **Tool orchestration latency:** read-only property and knowledge requests now use bounded
   pre-LLM grounding. Hybrid mode exposes only the guarded `capture_prospect_interest` tool, which
   removes the model-driven read-tool selection and result-processing cycle. Turn records now also
   report grounding duration and individual LLM request phases.
2. **End-of-turn delay:** fixed endpointing was reduced from a 0.8-second minimum and 1.5-second
   maximum to a 0.5-second minimum and 1.0-second maximum.
3. **Long tool responses:** the prompt now asks for the requested fact, one useful detail, and a
   short follow-up question instead of a longer property or policy summary.
4. **LLM latency:** on 2026-06-20, the direct OpenAI deployment setting changed from
   `gpt-4o-mini` to `gpt-4.1-mini`. This is an implementation status only; no latency or naturalness
   improvement is claimed until a matched post-change call batch is measured.
5. **Perceived post-commit latency:** ADR 0008's call-scoped acknowledgment coordinator is now
   implemented behind the disabled-by-default `ACKNOWLEDGMENT_MODE` setting. On eligible slow
   property, policy, comparison, or guarded capture turns, it can play a short contextual phrase
   after a 750 ms delay. It cancels the phrase when substantive audio becomes ready first, prevents
   acknowledgment and answer audio from overlapping, limits repetition to two non-consecutive
   acknowledgments per call, and preserves normal interruption behavior. Acknowledgment timing is
   recorded separately and does not count as a reduction in actual end-to-end response latency.

False-interruption tuning and metrics record classification remain separate pending changes and
are not included in the improvement claims below.

### First Post-Change Call

The first complete post-change measurement was call `SCL_2uX6wJ4m7EUT` in
`metrics/voice_metrics.jsonl`. It contained one greeting, eight measured grounded read turns, and
one guarded prospect-capture turn. All eight read turns completed with one LLM request and no read
tool call. Grounding took 16 ms p50 and 20 ms p90, with no grounding deadline or cancellation
events.

| Metric | Twenty-call baseline | First post-change call | Change |
| --- | ---: | ---: | ---: |
| End-to-end response p50 | 3,410 ms | 3,304 ms | -106 ms (-3%) |
| End-to-end response p90 | 5,916 ms | 4,061 ms | -1,855 ms (-31%) |
| End-of-turn detection p50 | 1,887 ms | 1,639 ms | -248 ms (-13%) |
| End-of-turn detection p90 | 3,209 ms | 2,664 ms | -545 ms (-17%) |
| Legacy tool E2E p50 vs. grounded read E2E p50 | 5,251 ms | 3,304 ms | -1,948 ms (-37%) |
| Legacy tool response duration p50 vs. grounded read response duration p50 | 13,110 ms | 9,228 ms | -3,882 ms (-30%) |
| LLM time to first token p50 | 884 ms | 828 ms | -56 ms (-6%) |

The strongest directional improvement is on grounded read turns: their median response latency is
about 1.95 seconds lower than the legacy tool-turn median. The endpointing and shorter-response
changes also moved their target metrics in the expected direction. The capture turn has no
end-to-end or endpointing measurement, so prospect-capture latency cannot yet be compared.

This is an initial signal rather than a confirmed matched-call result. The post-change values come
from only eight measured response turns in one call, and the grounded read turns are compared with
the broader legacy tool cohort rather than identical scripted turns. Repeat the baseline scenarios
over a matched call batch before treating these percentages as stable.

### Latest Post-Change Call

The latest completed measurement was call `SCL_kfNaLeeUzKB9`. It contained 13 assistant records,
11 turns with end-to-end measurements, and no interruptions or errors. Ten measured turns were
grounded reads without a tool call; one was a guarded prospect-capture turn. Acknowledgments were
disabled, so all acknowledgment records were suppressed and no perceived-response metric was
available.

| Metric | Twenty-call baseline | Latest call | Change |
| --- | ---: | ---: | ---: |
| End-to-end response p50 | 3,410 ms | 4,303 ms | +893 ms (+26%) |
| End-to-end response p90 | 5,916 ms | 5,000 ms | -916 ms (-15%) |
| End-of-turn detection p50 | 1,887 ms | 2,064 ms | +177 ms (+9%) |
| End-of-turn detection p90 | 3,209 ms | 3,234 ms | +25 ms (+1%) |
| LLM time to first token p50 | 884 ms | 862 ms | -22 ms (-2%) |
| LLM time to first token p90 | 1,279 ms | 1,545 ms | +266 ms (+21%) |
| Assistant response duration p50 | 6,929 ms | 7,822 ms | +893 ms (+13%) |
| Assistant response duration p90 | 15,305 ms | 12,690 ms | -2,615 ms (-17%) |

The comparable grounded-read subset retained a meaningful improvement over legacy tool turns:

| Metric | Legacy tool turns | Latest grounded reads | Change |
| --- | ---: | ---: | ---: |
| End-to-end response p50 | 5,251 ms | 4,219 ms | -1,032 ms (-20%) |
| End-to-end response p90 | 6,638 ms | 5,076 ms | -1,562 ms (-24%) |
| Assistant response duration p50 | 13,110 ms | 7,983 ms | -5,127 ms (-39%) |

Grounding remained inexpensive at 16 ms p50 and 25 ms p90. The prospect-capture turn completed in
4,303 ms compared with the legacy capture median of 5,452 ms, but one new sample is not enough to
claim a stable capture improvement.

**Verdict:** the changes reduced legacy read-tool orchestration latency and the long-response tail,
but they have not yet demonstrated an overall median-latency improvement. Compared with the first
post-change call, end-to-end p50 regressed from 3,304 ms to 4,303 ms and p90 regressed from 4,061 ms
to 5,000 ms. End-of-turn and LLM tail variability remain material. This result is still directional
because it comes from one latest call with 11 measured turns rather than a matched multi-call batch.

## Prioritized Experiments

Continue to change one variable per matched call batch and compare against the twenty-call
baseline. Tool orchestration, endpointing, and response-length changes are implemented; the next
steps are:

1. Run a matched post-change call batch covering the same baseline scenarios, including prospect
   capture, and compare acceptance as well as latency.
2. Track premature endpoints and caller corrections with the lower endpointing values.
3. Test requiring one recognized word for interruption. Compare false interruptions, successful
   barge-ins, and interruption stop latency against the baseline.
4. Separate greeting records, user-response turns, and assistant continuations in the local
   summary.
5. Measure the `gpt-4.1-mini` direct OpenAI model over a matched call batch and compare LLM TTFT,
   end-to-end latency, grounded-answer accuracy, capture behavior, and naturalness with the
   `gpt-4o-mini` baseline.
6. Verify Deepgram acknowledgment and substantive synthesis concurrency with credentials, then run
   a matched acknowledgment-enabled call batch measuring perceived response time, actual
   substantive latency, repetition, false interruptions, and successful barge-ins before enabling
   `ACKNOWLEDGMENT_MODE` by default.

Do not prioritize local tool execution or normal playback latency: both are already small. Defer
additional model-provider comparisons until the implemented `gpt-4.1-mini` change and the
grounding, endpointing, and response-length improvements are confirmed in a matched call batch.

### Future TTS Regional Deployment

Deepgram's hosted API does not provide an India-region selector. If regional TTS latency becomes a
priority, evaluate self-hosting Deepgram in India or switching to a provider with an India endpoint.
