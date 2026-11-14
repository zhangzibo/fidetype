---
title: Streaming trust layer
type: concept
tags: [trust, streaming, real-time, provenance, risk-control, neuraltextstream, m4, commit-gate]
sources: [brain-to-text-25-copytask]
updated: 2026-11-13
---

# Streaming trust layer

Diagram: [12-streaming-trust-layer.drawio](../diagrams/12-streaming-trust-layer.drawio) (rendered in [diagrams/index.html](../diagrams/index.html#s12)). Incremental decoding: [14-incremental-decoding.drawio](../diagrams/14-incremental-decoding.drawio) ([rendered](../diagrams/index.html#s14)).

## What it is
The batch trust core reads a complete stream and selects one action. A live system gets the stream one event at a time. The **streaming trust layer** (`fidetype.trust.streaming.StreamingTrustLayer`, task **M4-03**) reads NeuralTextStream events as they arrive. It keeps a state per session. It emits commit / offer / ask / abstain decisions with provenance.

It runs a **frozen configuration**: the fitted state of the trust core, loaded from one JSON file (`fidetype.trust.frozen.FrozenTrustConfig`). So the live system uses exactly the thresholds that were calibrated, without the calibration data.

## API

| Call | What it does |
|---|---|
| `FrozenTrustConfig.from_pipeline(pipe, name, recipe)` | Freeze a fitted `TrustPipeline`: frame, sentence and character temperatures, conformal q, guard settings, policy thresholds, risk-control record |
| `cfg.save(path)` / `FrozenTrustConfig.load(path)` | Canonical JSON. `inf` and `nan` are written as strings. `cfg.config_id` = SHA-256 content id |
| `paper1_v4_harness_config()` | Harness settings of the Paper 1 frozen recipe (guard on, LTT α 0.05, δ 0.1, combine max). Fit on the user's calibration data, then freeze |
| `StreamingTrustLayer(cfg, decode_fn=None, streaming=StreamingConfig(), online=None, ledger=None, incremental=None)` | The layer. `decode_fn(stream) -> NBest` selects the frames route; without it the layer uses the hypothesis route. `incremental=factory` (opt-in, M4-08) decodes as the frames arrive (next sections) |
| `layer.push(event, session_id)` | Consume one event (dict or JSON string). Returns the decisions it causes, often none |
| `layer.end_of_utterance(session_id, final_attempt=None)` | Close the utterance when the producer sends no boundary |
| `layer.flush()`, `layer.close(sid)`, `layer.new_item(sid)` | End all pending utterances; drop a session; reset the attempt count |
| `layer.abort_utterance(sid)` | Drop the pending utterance **without** a decision (for example after a transport loss; added in M6-01) |
| `layer.feedback(decision, truth)` | The user's final text (or None). Feeds the online controller and writes a ledger correction |
| `replay(path, layer)`, `iter_events(path)` | File (JSON Lines or NPZ) → events → layer |
| `python -m fidetype.trust.streaming replay --config trust.json [--decoder greedy] files...` | Print `trust_decision` events as JSON Lines |

Each `StreamDecision` has `final`, `action`, `shown`, `inputs` (p_top1, conformal set, guard risk), `attempt`, `final_attempt`, `ticket` (online only) and `provenance`.

## Two input routes

| Route | Input | When does the layer decide? | Cost of the final decision |
|---|---|---|---|
| `frames` | `frame` events (dense or sparse) | At the end of the utterance: it builds the stream, applies the frozen frame temperature, calls `decode_fn`, runs the trust core | One decode of the utterance |
| `hypothesis` | `hypothesis` events (n-best lists) | Partial hypothesis → provisional decision. Final hypothesis → final decision at once | Trust core only |

An utterance ends at a final hypothesis, a `segment_end` event, an `end` event, a new header, or `end_of_utterance()`. An utterance with no input gives no decision.

**Rule: a consumer must not act on a provisional decision.** It can show it as a preview. Only a final decision is an action.

## State and bounds

| Item | Bound |
|---|---|
| Frame rows | Current utterance only, at most `max_frames` (default 15 000 = 10 min at 40 ms). A longer utterance gives a final ABSTAIN ("input too long") |
| Hypotheses | The latest one only (`revision_of` replaces) |
| Sessions | At most `max_sessions` (default 256) |
| Feedback tickets | At most `max_pending_feedback` per session; the oldest is closed as "feedback missing" |
| Work per frame | O(V): checks and one append |
| Provisional decodes (frames route) | Every `partial_every_frames` frames, off by default |
| Latency budget | `latency_budget_s` flags a slow decision in its provenance. It does not change the decision, so replay stays deterministic |

Bad events (frame before header, time that does not increase, a row that does not sum to 1, NaN, unknown vocab type, bad `blank_id`) raise `StreamEventError`. The session state does not change. Lines after `end` are ignored (spec ambiguity A5).

## Attempts
The policy needs `final_attempt`, because ASK is not possible on the last attempt. The session counts attempts. After a final ASK, the next utterance is the next attempt of the same item. After any other final action, the count goes back to 0. `max_attempts` defaults to 2, as in the harness.

## Online re-calibration
Pass an `OnlineCommitRiskControl` ([conformal risk control](conformal-risk-control.md), M2-16) as `online`. Each session gets its own copy. Final decisions then carry a ticket. `feedback()` closes it. With `online_floor=True` (default), the frozen `commit_p` is the floor (`lam_min`) of the online threshold. So the online loop can make the gate stricter than the frozen configuration, never looser.

> **Our take:** the floor keeps the Paper 1 guarantee (LTT on the calibration half) as the minimum. The online loop adds protection against drift inside the session. It cannot remove the offline protection.

## Per-session risk monitor (A2, opt-in)
Pass a `SessionRiskMonitor` (`fidetype.trust.session_risk`) as `session_risk` (default None: off). Each session gets its own copy. `feedback()` gives it the realised loss of each final decision: 1 for a COMMIT or OFFER_WORDS whose top-1 text is not the truth, else 0. When its e-process reaches 1/γ, the session becomes offer-only (`commit_p = +inf`) until it closes. So the gate can only get stricter. A session whose risk stays ≤ α raises a false alarm with probability ≤ γ. The state is in `session_state()["session_risk"]` and in each decision's provenance (`session_risk`). Evaluation and the recommended "certify, then commit" profile: [per-session risk control](../questions/per-session-risk-control.md).

## Provenance
Each decision carries: `config_id`, session, utterance, route, the input reference (frame range, time range and the SHA-256 of the raw stream; or the hypothesis id, `revision_of` and its SHA-256), the event range, the commit threshold in effect and the computation time. With a [provenance ledger](provenance-ledger.md), each final decision is also a hash-chained ledger entry. One context entry per session holds the full frozen configuration. `feedback()` writes the linked correction.

## Equivalence with the batch path
On the same input, the final decision equals the batch decision (`TrustPipeline.analyze` + `policy.decide`) exactly: the same action, shown texts, reason, p_top1, conformal set and guard score. `tests/test_trust_streaming.py` checks this:

| Input | Result |
|---|---|
| 20 synthetic streams × 3 configurations (plain fit, Paper 1 recipe, Paper 1 recipe with a looser gate) × 2 file forms (JSON Lines, NPZ) | All equal |
| Two utterances in one stream (`segment_end`), 3 interleaved sessions, provisional decodes every 10 frames | Final decisions equal |
| Hypothesis route, 8 streams (partial then final hypothesis) | All equal |
| Conformance golden vectors, every `accept` vector | Equal (empty streams give no decision); frame-core `reject` vectors raise |

## Latency (synthetic, CPU)
`experiments/2026-11-12-m4-streaming/bench_latency.py`; numbers in [results/latency.md](../../experiments/2026-11-12-m4-streaming/results/latency.md). 100 simulator utterances, mean 453 frames, V = 28.

| Path | p50 | p95 | p99 | Equal to batch |
|---|---|---|---|---|
| `push(frame)` | 0.008 ms | 0.014 ms | 0.016 ms | |
| End → final decision, reference beam decoder | 8.1 ms | 11.1 ms | 14.0 ms | 100/100 |
| End → final decision, greedy decoder | 0.72 ms | 1.08 ms | 1.39 ms | 100/100 |
| `push(hypothesis)` (trust core only) | 0.19 ms | 0.32 ms | 0.46 ms | 100/100 |

64 interleaved sessions: about 28 000 events/s on one core; tracemalloc peak 8.7 MB. Peak frame buffer per session: 124 kB.

> **Our take:** the trust layer adds well under 1 ms on the hypothesis route. On the frames route the decoder dominates the latency. The trust layer is not the bottleneck for real-time text entry. All synthetic decisions were OFFER (the synthetic gate is strict); the tests cover the other actions.

## Real data: a frozen Paper 1 config on Brain-to-Text '25 (M4-06)
Experiment: [2026-11-13-m4-06-real-replay](../../experiments/2026-11-13-m4-06-real-replay/results.md) ([tables](../../experiments/2026-11-13-m4-06-real-replay/results/tables.md)). Data: [Brain-to-Text '25 copy task](../sources/brain-to-text-25-copytask.md), T15, fixed split A.

We fitted the Paper 1 frozen recipe (`paper1_v4_harness_config`: guard, LTT α 0.05, δ 0.1, max rule) on fit-A (411 trials) and the clean calibration half (401). We froze it and replayed the 816 test trials as NTS files through the layer, on both routes.

| item | our decoder | published gate |
|---|---|---|
| frozen config (committed, numbers only) | `tcfg-f5ca0020b3b8fce2`, commit_p 0.3 | `tcfg-ea22af7ec91eea3f`, commit_p 0.76 |
| streaming = batch (action, shown, p_top1, guard, set; `==`) | 816/816 frames, 816/816 hypothesis | 816/816 frames, 816/816 hypothesis |
| test wrong-commit / commit / eWPM (streaming) | 0.0245 (20) / 0.100 (82) / 11.48 | 0.0294 (24) / 0.403 (329) / 18.65 |
| Paper 1 Tab. 3, guaranteed rule A | same | same |
| frame-shuffled / uniform controls committed | 0/300 / 0/300 | 0/300 / 0/300 |
| provenance | 816/816 config id + stream hash; ledger verifies | same |

Latency: hypothesis route p50 0.44 ms, p95 0.63 ms. Frames route with a fresh decode: p50 173 ms, p95 992 ms. The decoder takes this time; the layer adds under 1 ms. Frame buffer: at most 180 KiB per session.

The benchmark v0.1 NTS files round log-probs to 6 decimals. With them, p_top1 moves by at most 3.4e-8. No action changed, but exact `==` equality then fails on most trials. Exact replay needs full-precision values.

> **Our take:** the frozen config file is enough to rebuild the paper's split-A row in a streaming consumer, bit for bit. It is valid only with the decode_fn it was fitted with. On the hypothesis route the producer must apply the frozen frame temperature. M4-07 added a declaration for this (next sections).

## Incremental decoding (M4-08, opt-in)
Experiment: [2026-11-13-m4-08-incremental](../../experiments/2026-11-13-m4-08-incremental/results.md) ([tables](../../experiments/2026-11-13-m4-08-incremental/results/tables.md)). Diagram: [14](../diagrams/index.html#s14).

The default frame route decodes the whole utterance at its end. On B2T this took p50 175 ms, p95 1010 ms, max 3.2 s (M4-06). All of it falls after the user stops. The incremental route does the search while the frames arrive.

```python
from fidetype.trust.incremental import CTCBeamSpec, IncrementalGreedy
spec = CTCBeamSpec(dict(RETUNED), lm=lm, prewarm_every=5)      # one setting -> batch and incremental
layer = StreamingTrustLayer(cfg, incremental=spec.factory,
                            streaming=StreamingConfig(incremental_chunk_frames=1, partial_every_frames=5))
```

| Part | What it does |
|---|---|
| `IncrementalDecoder` (`fidetype.trust.incremental`) | `push_frames(chunk)`; `partial() -> NBest` (provisional); `finalize(stream) -> NBest` |
| `IncrementalGreedy`, `IncrementalReferenceDecoder` | CTC greedy and the demo segment beam, one closed peak at a time |
| `IncrementalPrefixBeam` (`fidetype.lm`) | The CTC prefix beam search with its state carried across chunks. `ctc_prefix_beam_search` is this class with one chunk |
| `CTCBeamSpec` | Builds the batch `decode_fn` and the incremental factory from one setting. `post` makes the final n-best (for example a lexicon word decoder) |
| `prewarm_every`, `prewarm_max_new`, `on_prewarm` | Speculative end work every N frames: align the current candidate texts; fill a word decoder's caches. It never changes a result |
| `StreamingConfig.incremental_chunk_frames` | Frames per `push_frames` call (default 1) |
| `BufferedDecoder` | Any batch `decode_fn` behind the interface (no time saved) |
| `stability_metrics` | Top-1 changes, rewrites, time to stable of the previews |
| CLI | `replay --decoder greedy|demo --incremental` |

The layer applies the frozen frame temperature to each chunk row by row, as the batch path does. Previews come from `partial()`, so a preview no longer decodes the whole buffer. The default (no factory) does not change.

**Equality.** The final decision equals the batch path exactly (`==` on action, shown texts, p_top1, guard risk and prediction set): 816/816 B2T test trials for our decoder (4 incremental variants) and for the published gate, 200/200 synthetic streams for greedy, segment beam and CTC beam + LM. The beam needs no documented difference, because the batch search is the same per-frame code.

**Latency, B2T '25 (816 utterances, 80 ms frames, ms):**

| condition | end p50 | end p95 | end max | push p95 | push max | CPU per utterance |
|---|---|---|---|---|---|---|
| batch (M4-06 path) | 175 | 1010 | 3242 | 0.02 | 0.2 | 178 |
| incremental search only | 122 | 1005 | 3099 | 0.25 | 0.9 | 154 |
| incremental + full prewarm | **33** | **71** | **595** | 21 | 2153 | 622 |

- The search moves out of the end path for free. The tail is the lexicon word decoder (a slow fallback search for a word with no close lexicon entry).
- Full prewarm runs the word work during the utterance: end p95 falls 14×. The cost: push spikes up to 2.2 s and about 4.5× CPU. This is a deployment choice.
- Synthetic: the demo segment beam goes from 10.9 to 0.9 ms (p50); the CTC beam + LM from 226 to 87 ms with prewarm.

**Fast lexicon fallback and bounded prewarm (M4-09).** Experiment: [2026-11-13-m4-09-fast-lexicon](../../experiments/2026-11-13-m4-09-fast-lexicon/results.md) ([tables](../../experiments/2026-11-13-m4-09-fast-lexicon/results/tables.md)).

- `PronLexicon.nearest` is now exact and about 20x faster: a NumPy Levenshtein to all fallback pronunciations of one length at once. It equals `nearest_bruteforce` (kept as the reference) on 5,667/5,667 calls from the B2T test decode and 9,000/9,000 synthetic calls (same words, distance and order).
- `CTCBeamSpec(prewarm_budget_s=...)` runs the prewarm in small steps, about the budget per push, and continues in the next pushes. `PhonemeWordDecoder.warm` gives the word-decoder steps. A push overshoots by at most one step.
- Final decisions equal M4-06 in every condition: 816/816 for our decoder and for the published gate.

| condition (B2T, ms) | end p50 | end p95 | end max | push p95 | push max | CPU per utterance |
|---|---|---|---|---|---|---|
| batch, brute-force `nearest` (same-run baseline) | 106 | 676 | 2361 | 0.02 | 0.2 | 108 |
| batch, fast `nearest` | 95 | 172 | 265 | 0.02 | 0.2 | 97 |
| incremental search only, fast | 81 | 148 | 249 | 0.18 | 8.2 | 102 |
| incremental + full prewarm, fast | 33 | 74 | 131 | 20.4 | 119 | 519 |
| incremental + prewarm, **budget 1 ms**, fast | 52 | 118 | 220 | **3.1** | **30** | 271 |
| incremental + prewarm, budget 0.5 ms, fast | 70 | 138 | 236 | 0.8 | 13 | 192 |

- The push target (p95 < 5 ms, max < 50 ms) holds at budgets 0.5 and 1 ms. It needs a GC rule too: Python's gen-2 garbage collection took 80-280 ms inside a push (about 2.5 M objects on the heap). Rule: `gc.collect(); gc.freeze()` after the models load, `gc.disable()` while an utterance streams, `gc.collect()` after its final decision (p50 40-90 ms, at an idle point).
- The brute-force baseline here (106/676/2361 ms) is lower than the M4-08 numbers (175/1010/3242 ms), because M4-08 ran next to the T12 GPU job.

> **Our take:** the end-of-utterance tail was our lexicon search, and the push spikes were the garbage collector. Both are fixed with no change to any decision. A worker thread is not needed for this route.

**Bounded decoder caches (M4-10).** Experiment: [2026-11-13-m4-10-bounded-caches](../../experiments/2026-11-13-m4-10-bounded-caches/results.md) ([tables](../../experiments/2026-11-13-m4-10-bounded-caches/results/tables.md)).

- The memos that live across utterances now have an LRU entry bound: `PhonemeWordDecoder(cand_cache_size=5000, lm_cache_size=50000)` and `CharNgramLM(cache_size=200000)` (`fidetype.lm.cache.LRUCache`; None = unbounded). The beam memos live in one utterance only.
- Decisions do not change: 2,000/2,000 on a long synthetic session (3 bound settings) and 816/816 on B2T (default bounds, and 256-entry memos with about 250,000 evictions).

| 2,000-utterance synthetic session, budget 1 ms | RSS after setup -> end | candidate memo | idle GC p50 (last 10 %) | push p95 | end p50 / p95 |
|---|---|---|---|---|---|
| unbounded | 640 -> 1,387 MB | 39,977 entries, about 692 MB | 208 ms | 2.47 ms | 80 / 153 ms |
| default bounds | 641 -> 707 MB (flat after about 1,000 utterances) | 5,000 entries, about 89 MB | 43 ms | 2.32 ms | 85 / 158 ms |

- The candidate memo caused the growth: one entry holds about 17 KB, because a short phoneme segment often matches hundreds of lexicon words. B2T with default bounds: push p95 3.19 ms, max 31 ms. The push target still holds.

> **Our take:** the bound costs nothing measurable and stops memory growth in a long session. It also keeps the idle `gc.collect()` short.

**Preview stability (B2T, word previews every 0.4 s).** The top-1 changes in 29 % of steps. The shown text is rewritten (not only extended) 4.4 times per utterance. In 35 % of utterances the final top-1 differs from the last preview.

> **Our take:** incremental decoding removes the decoder's search from the wait after the user stops, with no change to any decision. The real-data tail sits in our word decoder, not in the layer; a faster exact lexicon search is the next fix (done in M4-09, below). The unstable previews confirm the rule: never act on `is_final = false`. Show previews as grey text that can change.

## Spec additions (proposal, not breaking v0.1)
[FEP-0001](../../spec/feps/0001-streaming-trust-events.md) (status Draft) proposes four Development parts. A v0.1 consumer ignores all four.

| Part | What it does |
|---|---|
| `segment_end` event | Closes an utterance (open question 5 of the spec). `t` must not be before the last frame |
| Evidence fields on hypothesis items | `char_confidences` (one value per Unicode code point), `logp_acoustic`, `logp_lm` (<= 0). The guard then works on the hypothesis route |
| `trust_decision` output event | Rule 1: "do not act on `is_final = false`". Rules 5-8: `seq` increases per session; at most one final decision per utterance; no decision after it; a `COMMIT` with `shown` has a text |
| `decode_declaration` (M4-07) | Header or hypothesis object: `decoder`, `decoder_version`, `frame_temperature` (default 1.0), `params`, `config_id` |

## Decode declaration check (M4-07)
The producer declares how it made the hypotheses. The layer compares the declaration with its frozen configuration.

| Compared | Rule |
|---|---|
| `config_id` | If declared, it must equal the layer's config id |
| `frame_temperature` | Must equal the frozen frame temperature (relative tolerance 1e-9). Absent means 1.0 |
| `decoder`, `decoder_version`, `params` | Must match `StreamingConfig.expected_decoder`, if the layer sets it (`params`: every expected key) |

`StreamingConfig` settings:

| Setting | Default | Effect |
|---|---|---|
| `declaration_check` | `"warn"` | `warn`: record `status` (`match` / `mismatch` / `absent`) in the provenance and in `trust_decision.declaration`; log a mismatch once per session; the decision does not change. `abstain`: a mismatch gives ABSTAIN. `off`: no check |
| `require_declaration` | `False` | A missing declaration counts as a mismatch |
| `expected_decoder` | `None` | Decoder id, version and parameters that must match |

- A declaration on a hypothesis replaces the header declaration for that event.
- The frames route ignores the declaration: there the layer decodes itself.
- A malformed declaration is a `StreamEventError`.
- The default (`warn`) does not change any decision. All earlier tests still pass.

> **Our take:** the declaration is a claim of the producer. It catches configuration mistakes (a wrong temperature, a config for another decoder). It does not stop a dishonest producer. For a deployment we suggest `declaration_check="abstain"` with `require_declaration=True`.

## Conformance profile `fep-0001` (M4-07)
An opt-in profile of the [conformance suite](conformance-suite.md) tests every FEP-0001 rule. It has 10 checks and 40 golden vectors (12 accept, 28 reject) in `spec/conformance/fep-0001/`.

```bash
fidetype conformance --profile fep-0001                        # reference consumer over the 40 vectors
fidetype conformance check --profile fep-0001 decisions.jsonl  # check an input stream or a decision log
```

- Input streams (header first) must also pass the v0.1 core level.
- For a decision log, the reference consumer returns `acted`: `shown[0]` of each final `COMMIT`. Vector F23 has a provisional `COMMIT` and then a final `ABSTAIN`. A conforming consumer acts on nothing.
- A test runs the layer on synthetic streams (both routes, provisional decisions, ASK and retry) and checks its decision log with the profile: no failure.

## Commit gate (M2-18, opt-in)
Experiment: [2026-11-13-m2-18-empty-commits](../../experiments/2026-11-13-m2-18-empty-commits/results.md).

**Problem.** The guard gives an empty top-1 text risk 1.0 (the highest value, not 0). The policy commits if `guard_risk <= commit_max_risk`. The policy grid contains `commit_max_risk = 1.0`, and at 1.0 this test is always true: the guard limit is off. In the T12 v2 validation dry run the Paper 1 v4 recipe chose 1.0 and committed 335 of 400 uniform (no-signal) streams: 320 empty texts and 15 short texts, all with guard risk 1.0. On the T12 trust pool the same recipe chose 0.1, and only that limit (risk 1.0 > 0.1) stopped 304 empty top-1 texts. See [confirmatory test on T12](../questions/confirmatory-t12.md).

**Gate.** `fidetype.trust.content.CommitGate(min_chars=1, min_words=0, max_guard_risk=None)`. A COMMIT that fails it becomes the decision of the same policy with `commit_p = +inf` (OFFER, ASK or ABSTAIN by the normal rules). Reason prefix `commit gate:`.

| part | API |
|---|---|
| frozen configuration | `FrozenTrustConfig.commit_gate` (dict; empty = off, left out of the JSON and the `config_id`); `with_commit_gate(1, 0, 1.0)`; `build()` -> `GatedPolicy` |
| batch | `GatedPolicy.wrap(policy, CommitGate(...))` |
| streaming | `StreamingTrustLayer` applies the gate last, on every decision path |

- Default off: every configuration made before M2-18 keeps its bytes, id and decisions (Paper 1 v4 behaviour).
- The gate only removes commits. The fallback loss of an item is never above its commit loss, so a CRC / LTT bound stays valid without a new calibration.
- Before / after on the T12 dry run (uniform control commits): v4 335, gate A (no empty text) 15, **gate B (no empty text, guard risk < 1) 0**; frame-shuffled 6 -> 3; test rows unchanged (22 commits, 11 wrong).
- Paper 1 (T15): 0 empty commits in all six refitted fits; all fits chose `commit_max_risk` <= 0.5; 0 empty top-1 texts in 35,816 cached T15 n-best lists. No Paper 1 number changes; the gate changes nothing there.
- Spec: FEP-0001 section 3 rule 9 (SHOULD NOT emit an empty final COMMIT).

> **Our take:** Gate B should be on by default in a future v5 configuration. The guard-limit value 1.0 should leave the grid, or the grid fit should also require near-zero commits on no-signal versions of the fit streams.

## Limits and follow-ups
- Incremental decoding is done (M4-08). The fast exact lexicon fallback and the per-push prewarm budget are done (M4-09). The decoder caches are bounded (LRU, M4-10). M4-01 (neural decoder lookahead) and M4-02 (lookahead sweep) are still open.
- Real-data frozen configs exist for one participant and one split only (M4-06, B2T '25 split A). Each new user and session needs its own fit.
- FEP-0001 conformance is done (M4-07, profile `fep-0001`). The FEP stays Draft until review.
- Live input over LSL is done: [LSL input](lsl-input.md) (M6-01). It uses `abort_utterance()` when a stream is lost. A WebSocket input is still open.
- The commit gate (M2-18) is opt-in. On the online path the controller still counts a gated COMMIT as a commit (conservative). A v5 recipe with the gate on by default is not yet defined.

## Related
[Provenance ledger](provenance-ledger.md) · [Conformal risk control](conformal-risk-control.md) · [Conformance suite](conformance-suite.md) · [Synchronous vs asynchronous decoding](synchronous-vs-asynchronous-decoding.md) · [Architecture](../questions/architecture.md) · [Standard roadmap](../questions/roadmap-standard.md) · [Lab Streaming Layer](../entities/lab-streaming-layer.md) · [LSL input](lsl-input.md) · [Per-session risk control](../questions/per-session-risk-control.md)

SDK and demo: the [Python SDK and offline demo](python-sdk.md) page shows the public API (`fidetype.TrustLayer`) and `fidetype demo`.
