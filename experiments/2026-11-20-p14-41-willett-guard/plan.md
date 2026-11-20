---
title: P14-41 trust guard for willett-hw - pre-registration
type: experiment
task: P14-41
updated: 2026-11-20
---

# P14-41: trust guard for `willett-hw` (pre-registration)

We wrote and committed this plan **before** any guard result on real data (val or test) was computed or read. Gap 121 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P14-41](../../wiki/questions/roadmap-standard.md#p14-41-trust-guard-for-willett-hw). Follow-up of [P14-33](../2026-11-19-p14-33-willett-hw/results.md).

Data: Willett handwriting 2021 (T5), CC0 1.0. CPU only (isolation runner, class `background`, 4 threads); the GPU belongs to P15-33. Per-sentence records (decoded text, truth, decisions) stay in `C:\Users\zhang\bci-data\derived\p14-41\`. The repo gets aggregates only. No weights in git.

## 1. Why P14-33 ran out of memory (found before this plan, synthetic data only)
The probes used **synthetic** log-probs with the val sentence lengths (106 sentences, 436,356 frames, longest 10,768 frames). No real decoder output went into any guard decision.

| Cause | Where | Effect |
|---|---|---|
| The CTC prefix beam search (loop) kept the LM score and the last token of **every prefix it ever made** (`lm_score`, `_last_id`) | `fidetype.lm.beam.IncrementalPrefixBeam._loop_push` | The built-in decoder of `calibrate` uses `prune_topk=None`, `prune_logp=-6`. On flat frames (the automatic near-uniform null control: log(1/98) = -4.6) every token passes, so each frame makes about 16 x 97 new prefixes of growing length. Memory grows with T^2: a synthetic run with 25 sentences reached **17.9 GB** in under 50 s of the uniform control (stopped by us) |
| The forced alignment held an emit array (T, S) float64 for all n-best texts at once | `fidetype.lm.beam.ctc_forced_align_many` | On null input the n-best texts can be almost T characters long: S about 10 x 2T, so up to tens of GB at T = 10,768 |

**Fix (library, exact, no method change):**
- The loop search cuts its per-prefix caches to the current beam when they pass 4,096 entries (`PREFIX_CACHE_MAX`). A dropped prefix that comes back is made again from its parent (in the beam) with the same values.
- The forced alignment reads the frame scores one frame at a time, goes over the texts in groups (at most 2^26 back-pointer cells per group), and returns `None` at once for a text with more labels than frames (no CTC path exists).
- Tests: `tests/test_trust_incremental.py::test_prefix_cache_pruning_is_exact` (with and without an LM, flat and peaked frames, chunked pushes, `partial`, `end_candidates`) and `::test_forced_align_many_groups_equal_one_pass`. A scratch check against the old code: equal n-best texts, scores, spans and confidences on 12 random inputs.
- Result on synthetic input: one near-uniform decision with T = 2,000 has a peak working set of 145 MB (before: more than 2.5 GB, stopped); T = 5,000: 200 MB, 21 s.
- In the script: float32 log-probs, one session in memory at a time, a peak-RSS log, and a watcher that stops the run (exit 3) above **6,000 MB** working set or on a `STOP` file. If the run stops for memory, we do **not** restart it; we report.

## 2. Question
Does the P14-33 guard recipe, calibrated on the `willett-hw` val blocks, give a guard that passes the null controls? Does it commit on the test blocks, and is it then safe and useful (safe WPM v0.1)?

## 3. Data and split (fixed)
- Model: `fidetype.pretrained.load("willett-hw")` (NumPy runtime, weights SHA-256 `66ac6590...`), greedy test CER 0.3051 (P14-33).
- Split: the P15-08 split, recomputed from the public files (test = last block of each session; val = one other block per session by salted hash). The script checks that it equals `derived/p15-08/willett/splits.json`.
- **Calibration: the 106 val sentences only. Report: the 80 test sentences only.** The training pool is never used.

## 4. Guard (fixed; the same call as the P14-33 `guard` stage)
`fidetype.trust.calibrate(lp_val, truths, alpha=0.05, delta=0.1, input_kind="logits", vocab=98 key tokens, blank=0, input_scale="log_probs", frame_period=0.01, null_inputs=<time-shuffled val input>, seed=0, audit_text=False)`. Built-in decoder (CTC prefix beam 16, 10-best, no LM, no lexicon). LTT certification (exact binomial p-values, fixed-sequence grid). Automatic null controls: near-uniform frames and frame-shuffled frames (300 each, allowed floor(0.05 x 300) = 15 commits each); user control: the decoder output on the **time-shuffled input** of the 106 val sentences (allowed floor(0.05 x 106) = 5).

Null inputs:
| Name | How |
|---|---|
| time-shuffled | the 10 ms bins of the neural input in a random order (a fixed generator per sentence), then the decoder |
| zero | an all-zero input of the same length, then the decoder (after the per-session z-score) |
| frame-shuffled | the decoder frames of the real input in a random order |
| uniform | near-uniform frames, log(1/98) + 0.05 N(0, 1), the same length |

## 5. Known before the run (from the method, not from data)
- `calibrate` splits 106 items into 26 fit + 40 policy-grid + **40 LTT** items. LTT at alpha 0.05, delta 0.1 needs at least **45** LTT items to certify any threshold ((1 - 0.05)^n <= 0.1). So with 106 val sentences, **no commit threshold can be certified**: the guard can only OFFER or WITHHOLD. About 120 or more calibration sentences are needed.
- With greedy decoding, only 1 of 80 test sentences is exact (P14-33 records). So a commit would rarely be right even with more data.
- **Prediction:** the guard is returned, the LTT is not feasible, it never commits, and safe WPM v0.1 is vacuous (0). This is the expected and honest result for this decoder.

## 6. Outcomes and verdicts
| Id | Verdict | Rule |
|---|---|---|
| **V1 guard** | refused / returned, not certified / certified | refused = `NullControlError`; certified = returned and the LTT is `feasible` |
| **V2 safety** | holds / fails / clear violation | wrong commits / 80 <= 0.05 -> holds; Clopper-Pearson 95 % lower end > 0.05 -> clear violation |
| **V3 value** | non-vacuous / vacuous | certified, at least one test commit, safe WPM v0.1 > 0 |
| **V6 controls** | pass / fail | all `calibrate` controls pass, and on the 80 test sentences the time-shuffled and the zero input each give a commit rate <= 0.05 (frame-shuffled and uniform on test are reported too) |
| V7 offers | reported | the share of test sentences offered; the exact rate and the CER of the offered top-1 text |

Safe WPM v0.1 (adopted): `fidetype.benchmark.safe_wpm.safe_wpm`, guarantee and controls from the sheet, neural time = number of 10 ms bins of the sentence window, default correction rule, no CI (one participant).

## 7. What counts as done for gap 121 (fixed here)
The roadmap "done when" of P14-41 says: a guard calibrated on the val blocks is a release file of `willett-hw` (SHA-256 in the manifest, `trust` set), with its test decisions reported (real and time-shuffled input), **or** a written refusal with numbers; "a guard that only offers is an acceptable result".
- **V1 returned (certified or not) and V6 pass:** package the guard as a release file (as `kt-semg-lda`): `willett-hw.guard.json` next to the weights (local only, not in git), a `guard` row with SHA-256 and size in `manifests/willett-hw.json`, `trust.config = "file:willett-hw.guard.json"`. The manifest and the docs say plainly that the guard **only offers and never commits** (if so), and why (40 < 45 LTT items; weak greedy decoder). Gap 121 closes. V3 vacuous is reported as **vacuous**, never as useful.
- **V1 returned but V6 fails** (a test null input commits > 5 %): do not package. Write the numbers. Gap 121 stays open; a new gap names the failing control.
- **V1 refused:** do not package. Write the refusal with the control counts. Gap 121 closes as a written refusal (roadmap rule), and the manifest `trust_note` gives the numbers.
- **V1 certified with commits** (not expected): package as above, with V2 and V3 as measured.

A non-vacuous guard for this decoder needs more calibration sentences (about 120 or more) and a stronger text decoder (a word LM: P14-12, gap 26; a stronger decoder: P15-33, gap 120). That is not part of this item; no other recipe, alpha, or decoder is tried here (no selection among variants).

## 8. Run
Detached (`launch.py`): `python -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I run.py all`. Stages `lp`, `guard`, `decide`, `score`, each with a checkpoint in `derived\p14-41\`. DONE file: `C:\Users\zhang\bci-data\derived\p14-41\DONE`. Stop: create `derived\p14-41\STOP`. Resume: delete `STOP`, run the launcher again.
