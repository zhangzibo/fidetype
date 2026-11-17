---
title: T15 split audit (decoder train / calibration / evaluation overlap)
type: question
tags: [benchmark, t15, brain-to-text-25, data-leakage, splits, trust, audit]
sources: [brain-to-text-25-copytask]
updated: 2026-11-17
---

# T15 split audit: do our T15 results use trials that the decoder trained on?

**Question (orchestrator, 2026-11-17):** the P6-08 agent found that the M4-12 T15 decoder's train partition holds about 368 of the 816 `b2t25-t15` benchmark test trials ([P6-08 results](../../experiments/2026-11-17-p6-02b-v02-entries/results.md#m4-12--m4-13-on-b2t25-t15-why-only-partial)). Which committed results could this affect?

**Short answer:** the overlap is real: 366 test trials match an M4 train trial exactly, and up to 368 match when we include trials with a less exact match. But **no committed result scores an M4-x decoder on a trial that it trained on.** Every M4-x result uses the HDF5 `val_eval` partition (701 trials). That partition shares no trial with the decoder train partition (0 of 701, checked by trial id). The only result that mixes the two worlds is the partial P6-08 entry. It already scores only `val_eval` trials, and all 103 of its units are clean. The pre-registered M4-13 reruns are **not affected**. One result family has an **indirect** overlap: the Paper 1 re-split analyses of "B2T ours" use word-decoder settings that were tuned on 400 trials. About 200 of these trials are in the test half of each re-split (179-224 of 818). The bias is optimistic and probably small. Smaller issues: the same tuning trials include 16 M4 `val_eval` trials, and one id rule is ambiguous. One tool is missing: nothing checks a benchmark entry for train / test overlap. Each fix is now a gap item (gaps 32-35).

Scripts: [match.py](../../experiments/2026-11-17-t15-split-audit/match.py), [audit.py](../../experiments/2026-11-17-t15-split-audit/audit.py). Counts (no text, no plain trial ids): [audit-counts.json](../../experiments/2026-11-17-t15-split-audit/results/audit-counts.json), [match-summary.json](../../experiments/2026-11-17-t15-split-audit/results/match-summary.json). Per-trial match table (hashed ids): `C:\Users\zhang\bci-data\derived\t15-split-audit\` (local only). CPU only, background class, 4 threads, peak RAM under 1 GB.

## Two data sources, one set of trials

The Dryad record of Card et al. 2024 (CC0) has two files that hold the **same** copy-task trials in two forms:

| File | What it holds | Who uses it |
|---|---|---|
| `t15_copyTask.pkl` | 1,718 online evaluation trials: cue sentence, post-implant day, **published online RNN logits** | the `b2t25-t15` track (1,628 trials with the 125k vocabulary: 812 `cal` / 816 `test`, first / second half of each day), B2T "ours" and "published" entries, Paper 1, M2 / M3 trust work |
| `t15_copyTask_neuralData.zip` (HDF5) | 11,000+ trials of neural features, partitions `train` / `val` / `test` (`test` has no sentence) | our decoders M4-01, M4-12, M4-13 |

The pkl has no block or trial number. So [match.py](../../experiments/2026-11-17-t15-split-audit/match.py) matches a pkl trial to an HDF5 trial on (session date, normalised sentence, frame count). Session date = post-implant day + 197 days after 2023-01-01. 1,436 sentence matches agree on this offset; the next best offset has 69. The online logits have 14-17 fewer frames than `(n_time_steps - 14) // 4 + 1` (1,237 of 1,418 unique same-day sentence matches; the other 181 differ in frame count, so the audit does not count them as a frame match). An unlabelled HDF5 `test` trial matches on (date, frame count) only.

| Match quality (all 1,718 pkl trials) | Trials |
|---|---|
| sentence + frame count, one candidate | 1,238 |
| sentence only, one candidate | 149 |
| frame count only, one unlabelled HDF5 test trial | 124 |
| ambiguous (several candidates) | 151 |
| no match | 56 |

## Our T15 decoders and their partitions

M2 has no T15 decoder of its own. The M2 work (M2-09, M2-13, M2-18, M2-19) runs trust code on decoder outputs. M2-19 uses M4-12 outputs.

| Decoder | Runs | Train | Checkpoint choice | Reported numbers | Source of the split |
|---|---|---|---|---|---|
| M4-01 | `m4-01-la-fixed0`, `-fixed25`, `-shared` | HDF5 `train`, 8,065 trials (8,072 minus 7 with out-of-lexicon words) | `val_select` = HDF5 `val`, even index per session (722) | `val_eval` = HDF5 `val`, odd index per session (701 of 704 used) | [prep.py](../../experiments/2026-11-13-m4-01-02-lookahead/prep.py) |
| M4-12 | `fixed0`, `fixed10`, `fixed15`, `fixed25`, `shared` | same | same | same | [config](../../experiments/2026-11-14-m4-12-decoder-retrain/config.json) |
| M4-13 (running, step 92,000 of 115,000 at 01:17) | `m4-13-long0` | same: the run log says `train=8065 ... val_select=722` | same | same | [config](../../experiments/2026-11-15-m4-13-long-train/config.json), `runs\m4-13-long0\train.log` (read only) |

No M4 decoder reads the HDF5 `test` partition. All three use the same derived files (`derived/m4-01-02-lookahead/*.npz`: train 8,072, val_select 722, val_eval 704).

### Checks on the partitions (by trial id)

| Check | Result |
|---|---|
| An HDF5 (session, block, trial number) in two partitions | **0** |
| `logprobs-m4-12-fixed0.npz` keys (701): on a train trial / on a val_select trial | **0 / 0** (all 701 are `val_eval`) |
| `logprobs-m4-01-la-fixed0.npz` keys (701): on a train / val_select trial | **0 / 0** |
| `logprobs-m2-19-m4-12-fixed0.npz` (722 val_select + 701 val_eval): on a train trial | **0** |
| M4-13 `val_eval` / `val_select` log-probs | not written yet (the M4-13 queue and the trust-reruns queue make them) |
| Hallucination split `halluc-v0.1/b2t25-t15-val-eval.json`: ids equal to the `val_eval` ids | **701 / 701** |
| Track split we rebuilt = committed v0.1 split file; = v0.2 hashes | **yes / yes** |

## The track test set against the decoder partitions

`b2t25-t15` pkl trials by M4 partition. "Strict" = the match above. "+ possible" = an unmatched trial that has a same-day, same-sentence candidate in that partition (an upper bound).

| Track split | M4 `train` | M4 `val_select` | M4 `val_eval` | HDF5 `test` (unused by M4) | unmatched |
|---|---|---|---|---|---|
| `test` (816) | **366** (+2 possible = 368) | **102** (+4 = 106) | **98** (+5 = 103) | 109 | 141 |
| `cal` (812) | 687 (+6) | 28 (+6) | 31 (+2) | 15 | 51 |

These numbers agree with the P6-08 estimate (about 368 / 106 / 103). Text level: 428 of the 816 test sentences occur somewhere in M4 train, on any day. Inside the HDF5 split, 81 of the 704 `val_eval` sentences also occur in `train` (other trials, same sentence).

## Results, one by one

Legend: **clean** = no trial in two roles. **clean, not comparable** = clean, but the units are not the 816 `b2t25-t15` test trials. So the number must not sit next to track numbers. **contaminated** = a trial in two roles. That bias makes the result look better than it is (optimistic).

### Benchmark cards (v0.1 `b2t25-t15-copytask`, v0.2 `b2t25-t15`)

| Result | Decoder | Train / tune | Calibration | Evaluation | train ∩ eval | cal ∩ eval | Class |
|---|---|---|---|---|---|---|---|
| "B2T ours" x always-commit / plug-in / CRC / LTT (v0.1 and v0.2, 8 cards) | **not M4**: published online RNN logits (pkl) + our phoneme-beam CMUdict word decoder (m6-06, no trained weights) | 3 word-decoder settings tuned on 400 track `cal` trials ([b2t25-trust](../../experiments/2026-11-10-b2t25-trust/run.py) `stage_tune`, seed 0) | 812 track `cal` | 816 track `test` | 0 (tune ⊂ cal) | 0 | **clean** |
| "B2T published" x 4 policies (8 cards) | published online RNN + published word output | Card et al. online decoder (trained before each evaluation block, per the paper; we cannot check this) | 812 `cal` | 816 `test` | n/a (not ours) | 0 | **clean** (as published) |
| `b2t25-t15__m4-12__guard` (v0.2, partial) | M4-12 `fixed0` | HDF5 train | 616 `val_select` (106 that match a track test trial removed; 0 strict matches left) | 103 track test units | **0**: 98 strict `val_eval`; the other 5 have only a `val_eval` same-day, same-sentence candidate (frame count off); none in train or val_select | 0 | **clean**, partial 103/816, not comparable to full entries (gap 30 = P6-07) |
| M4-13 one-command entry (`run.py t15-m4-13`, not run) | M4-13 | HDF5 train (same partitions) | val_select minus track test trials | val_eval track test units | 0 by design (same code) | 0 | **clean by design**. Rerun [audit.py](../../experiments/2026-11-17-t15-split-audit/audit.py) when the M4-13 log-probs exist |

### M4-x results on `val_eval`

| Result | Decoder | Calibration / fit | Evaluation | train ∩ eval | cal ∩ eval | Other overlap | Class |
|---|---|---|---|---|---|---|---|
| M4-01/02 accuracy + trust ([results](../../experiments/2026-11-13-m4-01-02-lookahead/results.md)) | M4-01 | frozen config `tcfg-f5ca0020b3b8fce2`: split A of the 812 track `cal` trials, **published** logits | 701 `val_eval` | 0 | **31 trials** (via another decoder's output) | word settings: 16 `val_eval` trials in the 400 tune trials | **clean, not comparable**. The frozen config is not calibrated on this decoder, so no guarantee carries over (M2-19 says so) |
| M4-12 retrain accuracy + trust ([results](../../experiments/2026-11-14-m4-12-decoder-retrain/results.md)) | M4-12 | same frozen config | 701 `val_eval` | 0 | 31 (other decoder) | 16 tune trials | **clean, not comparable**. The "published 0.0954 PER" reference is on all pkl trials, another set |
| M2-19 trust re-tune | M4-12 | `val_select` (fit-A 371, clean cal 351) | 701 `val_eval` | 0 | 0 | val_select also chose the checkpoint; 16 tune trials | **clean** |
| P14-03 drop-in replay validation | M4-12 | 722 `val_select` | 701 `val_eval` | 0 | 0 | same two notes | **clean** |
| P14-05 safe WPM: T15 `val_eval` row | M4-12 | 722 `val_select` | 701 `val_eval` | 0 | 0 | same | **clean, not comparable** to the track rows in the same table |
| P14-05 safe WPM: B2T track rows | as the B2T cards | 812 `cal` | 816 `test` | 0 | 0 | — | **clean** |
| P15-05 LLM rescoring + grounding | M4-12 | `val_select` | `val_eval` | 0 | 0 | same | **clean** |
| P15-06 hallucination bound (T15) | M4-12 | `val_select` (fluent threshold on all of it, also on the LTT items: stated in the plan) | `val_eval` | 0 | 0 | same | **clean** |
| P15-07 hallucination benchmark (T15) | M4-12 | per baseline, `val_select` | 701 `val_eval` (split ids checked: 701/701) | 0 | 0 | id rule ambiguous (gap 34) | **clean** |
| P5-02 precision bound (T15) | M4-12 | 722 `val_select` | 701 `val_eval` | 0 | 0 | same | **clean** |
| P15-04 bandit, P5-11 online replay (T15) | M4-12 (P5-02 items) | `val_select` | `val_eval` | 0 | 0 | same | **clean** |
| Live demo, `t15` track ([docs/demo.md](../../docs/demo.md)) | M4-12 + M2-19 config | `val_select` | 701 `val_eval` | 0 | 0 | same | **clean** |
| M4-13 scorer `eval.py` (run once at the end) | M4-13 | M2-19 config (M4-12 `val_select`) | 701 `val_eval` | 0 | 0 | 16 tune trials | **clean** |
| Pre-registered M4-13 reruns ([trust reruns](../../experiments/2026-11-17-trust-reruns-m4-13/plan.md), [P15-03 F1](../../experiments/2026-11-17-p15-03-f1-m4-13/plan.md), [F2](../../experiments/2026-11-17-f2-m4-13/plan.md), [P5-02](../../experiments/2026-11-17-p5-02-precision-m4-13/plan.md)) | M4-13 (M4-12 as champion in F1) | M4-13 `val_select` (CPU decode) | 701 `val_eval` | 0 | 0 | val_select chose the checkpoint (the F1 plan says so); 16 tune trials | **clean: not affected** |

### pkl-only results (published online logits, no M4 decoder)

| Result | Calibration / fit | Evaluation | Overlap | Class |
|---|---|---|---|---|
| B2T '25 trust core (M6-06), M2-09 provenance, M2-13 conformal, M2-18 fixed-split rows, M3-01/02 fixed-split rows, trust v5 candidate, Paper 1 fixed-split analyses (split A / B = alternate or chronological trials of the `cal` half), P6-01 audits | inside the track `cal` half | track `test` half (816) | none: cal and test are disjoint halves of each day; tune ⊂ cal; 1 sentence occurs in both halves | **clean** |
| Paper 1 re-split analyses, "B2T ours" rows: R3 repeated splits (50), R4 200 splits and the analyses built on them (M2-18 and M3-01/02 re-split tables), R1 clean-drift pooled re-splits | each re-split permutes all 1,628 trials per day: fit-A 1/4, cal 1/4, test 1/2 (818) | the re-split test set | **tune ∩ test: 182-218 (median 199) of 818** in R3, **179-224 (median 201.5)** in R4 (checked on the split files). The 3 word-decoder settings were chosen on those trials | **contaminated (indirect: hyperparameter tuning ∩ evaluation), optimistic, probably small**. The "published" rows do not use our word decoder: clean |
| M4-06 / M4-08 / M4-09 / M4-10 replay and latency, M6-11 WebSocket | split A config (inside `cal`) | track `test` half or timing only | none | **clean** |

## What is not clean, and the fix

No result is contaminated in the strict sense (a trial used to train the decoder and also to score it). One result family has an indirect overlap (issue D). These are the issues we found:

| # | Issue | Affected results | Size | Bias | Fix (gap) |
|---|---|---|---|---|---|
| A | M4 train holds 366-368 track test trials, so no M4-x decoder can have a full-coverage `b2t25-t15` entry | the P6-08 partial entry (handled); every future M4-x track entry | 366 strict / 368 upper of 816 | optimistic, if anyone scored M4 on the full track | **gap 32 = P6-09**: retrain the M4-13 recipe on HDF5 train minus the matched track test trials (or define a track variant on `val_eval`), then make a full entry |
| B | No tool checks train / test overlap for a track entry; the overlap was found by chance | all future entries on `b2t25-t15` (and any track whose dataset has a second release) | — | — | **gap 33 = P6-10**: training-data declaration in the submission manifest + a published hashed map from HDF5 trials to track units + a scorer check |
| C | The halluc-v0.1 T15 split rule says "odd-index trials ... id = `<session>\|val\|<i>`", but `i` is the index inside `val_eval`, not inside HDF5 `val`. With the raw `val` index, 358 of 701 ids point to `val_select` trials | P15-07 split file (the results are correct; the rule text is ambiguous) | rule text only | a rebuild by the rule would score on calibration trials. The text hashes catch it | **gap 34 = P15-20**: state the index rule exactly (or move to unambiguous ids in protocol 0.2) |
| D | The 3 word-decoder settings (`lm_weight`, `edit_penalty`, `word_bonus`; grid of 12) were tuned once, on 400 fixed track `cal` trials (published logits). (1) The Paper 1 re-splits put about 200 of these 400 trials in each test set. (2) 16 of the 400 are M4 `val_eval` trials and 16 are `val_select` trials. (3) The frozen split-A config used all 812 `cal` trials, and 31 of them are `val_eval` trials (other decoder) | (1) Paper 1 R3 / R4 / R1 re-split "B2T ours" rows and the M2-18 / M3-01/02 re-split tables; (2) all M4-x word-level results on `val_eval` | (1) 179-224 of 818 per re-split; (2) 16 of 701 (2.3 %) | optimistic; (1) small, (2) very small | **gap 35 = P14-15**: re-tune inside each re-split's fit-A (at least 10 re-splits) and without HDF5 `val_eval` trials. If the chosen settings do not change, close with "no effect"; if they change, rerun the affected tables and add a note to the Paper 1 drafts |

Known and already stated (no new gap): every M4 guard is calibrated on `val_select`, which also chose the checkpoint. The effect is small: M4-12 `fixed0` PER is 0.2561 on `val_select` and 0.2574 on `val_eval` ([M4-12 results](../../experiments/2026-11-14-m4-12-decoder-retrain/results.md)). Results on `val_eval` stay honest, because `val_eval` chose nothing.

## M4-13 pre-registered reruns

**Not affected.** All four plans calibrate on M4-13 `val_select` and test on `val_eval`. They never use a `b2t25-t15` track unit. The M4-13 decoder has the same train / val_select / val_eval partitions as M4-12 (train 8,065, val_select 722 in its run log).

**Proposed amendment (not applied; the pre-registrations stay unchanged):** a short note to add to each M4-13 rerun results page under "Limits", before the results are read: "The word-decoder settings came from 400 B2T track `cal` trials. 16 of these are `val_eval` trials (published logits, not M4-13). Issue D of the [T15 split audit](t15-split-audit.md); gap 35." This is a disclosure only. It changes no hypothesis, metric or threshold.

> **Our take:** the concern was right about the data. The pkl and the HDF5 hold the same trials, and the M4 train partition holds 45 % of the track test set. But the project kept the two worlds apart: every M4-x number is on `val_eval`, and P6-08 removed the overlap before it scored. The real risk is the future: a full-coverage M4-x entry, or an outside entry trained on the public HDF5 `train`. Gaps 32 and 33 close that risk.

> **Our take:** an outside team that trains on the B2T '25 HDF5 `train` partition (the normal recipe of the B2T '25 challenge) has the same overlap with our `b2t25-t15` test set. So gap 33 matters for the benchmark as a whole, not only for our decoders.

## Follow-up 2026-11-17: gaps 34 and 35 closed

- **Issue C (gap 34, P15-20):** done, commit `645dd1b`. The split file states the index rule exactly (i = position inside the session's `val_eval` list; HDF5 `val` index = 2i + 1). A test rebuilds the 701 ids from the rule.
- **Issue D (gap 35, P14-15):** **no effect** on the Paper 1 re-split "B2T ours" rows ([results](../../experiments/2026-11-17-p14-15-retune/results.md), pre-registered). A re-tune inside each re-split's fit-A changes the setting in 35 of 200 splits, mostly exact WER ties. With these 35 tables rebuilt, 0 of 80 primary metrics move by their CI half-width (largest 0.27 of it). Without the 16 `val_eval` tune trials the setting changes to edit penalty 8 (an exact WER tie); without `val_eval` and `val_select` it stays the same. Gap 44 (P14-18) reruns the M4-12 word decode with edit penalty 8.
- **Correction to the table above:** the "B2T published" re-split rows are not fully independent of our word decoder. `published_plus_fn` uses our word n-best for the gate score and the word confidences. Gap 45 (P14-19) checks them, together with the forward chain (V1 / V2 / V4 test on whole days) and the downstream tables.

## Limits of this audit

- The match is on (date, sentence, frame count), not on a shared trial id. 141 test trials stay unmatched. The bounds above cover the ones with a same-day, same-sentence candidate. The rest have no labelled candidate, so they cannot be in M4 train under this match. A different trial order would not change this.
- 4 HDF5 trials match two pkl trials each (a sentence repeated on one day, sentence-only match). This changes the counts by at most 4.
- The published online RNN is outside our control. The paper says it decoded the evaluation blocks online, but we cannot check its training data.

## Related pages
- [Open gaps](open-gaps.md) (gaps 32-35)
- [P6-08 results](../../experiments/2026-11-17-p6-02b-v02-entries/results.md)
- [Open benchmark](../concepts/open-benchmark.md)
- [Long-term roadmap](roadmap-standard.md) (P6-09, P6-10, P14-15, P15-20)
