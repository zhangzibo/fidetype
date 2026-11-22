---
title: P5-36b two-direction LM-beam direction score against rev_out - results
type: experiment
task: P5-36
updated: 2026-11-22
---

# P5-36b: results (2026-11-22)

Pre-registration: [plan.md](plan.md) with [run.py](run.py), [launch.py](launch.py), the library code and the synthetic tests, commit `dab694f` (14:17), before any val or test number. Numbers: [results/fit.json](results/fit.json), [results/results.json](results/results.json); log: [results/run.log](results/run.log). Per-item records (actions, scores, feature values, times; no text) stay in `C:\Users\zhang\bci-data\derived\p5-36b\` only.

## Verdict

| Guard | B1 `rev_out` offers (<= 4 / 80) | B2 real offers removed (<= 4 / 80) | Secondary B3-B5 | Checks C1, C2 |
|---|---|---|---|---|
| LM (`tcfg-26ae951a20a0cddd`) | **pass: 0 / 80** (coherence only: 78) | **pass: 4 / 80** (77 -> 73) | all pass | hold |
| Built-in (`tcfg-39aac48688b8bd12`) | **pass: 1 / 80** (coherence only: 77) | **fail: 6 / 80** (77 -> 71) | all pass | hold |

**Partial result.** The two-direction LM-beam score is much stronger than every earlier direction score: `rev_out` offers drop from 77-78 to 0-1 of 80 (P14-57: 11 and 18; P5-36 `lm_direction`: 10 and 10). For the LM guard it meets the last part of the gap 181 done-when (0 / 80 `rev_out` offers, 4 / 80 real offers removed). For the built-in guard it removes 6 / 80 real offers (limit 4). The plan (section 4.3) needs B1 and B2 for **both** guards, so the done-when is **not met**. Gap 181 stays open with this evidence.

No packaged gate, guard file or manifest changed. `config_id` values unchanged.

## Threshold fit (val S, 66 real inputs; all 66 are coherence offers for each guard)

Rule: `tau` = the value at index `floor(0.05 x 66)` = 3 of the ascending `D` values of the real S offers.

| | Built-in | LM |
|---|---|---|
| `tau` | **0.3259** | **0.1344** |
| real val offers removed | 3 / 66 | 3 / 66 |
| `rev_out` val offers, coherence only -> both gates | 66 -> **0** | 66 -> **0** |
| `D` of the real val offers (min / 5 % / median / 95 % / max) | -0.010 / 0.338 / 0.902 / 1.351 / 1.448 | -0.064 / 0.162 / 0.910 / 1.320 / 1.627 |

## Test (80 sentences) and secondary rules

| Rule | Built-in | LM |
|---|---|---|
| **B1** `rev_out` offers <= 4 / 80 | pass: **1** | pass: **0** |
| **B2** real offers removed <= 4 / 80 | **fail: 6** (removed `D`: -0.433, 0.133, 0.172, 0.258, 0.258, 0.302) | pass: **4** (removed `D`: -0.077, -0.019, 0.113, 0.128) |
| **B3** real LTT offers >= 36 / 40 | pass: 40 / 40 | pass: 40 / 40 |
| **B4** P14-54 test nulls <= 4 / 80 each | pass: time-shuffled 1 -> 0, zero 0, frame-shuffled 0, near-uniform 0 | pass: time-shuffled 1 -> 0, zero 0, frame-shuffled 0, near-uniform 0 |
| **B5** P14-55 nulls keep their results | pass (table below) | pass |
| C1 antisymmetry (1e-9) | 66 / 66 val, 80 / 80 test | 66 / 66, 80 / 80 |
| C2 equivalence (guard with both gates vs "coherence, then `D < tau`") | 200 / 200 | 200 / 200 |
| `coherence` of `rev_out` = real (1e-9) | 80 / 80 | 80 / 80 |

B5, offers with both gates (P14-55 offers -> now). The 22 P14-55 offered null inputs were made again from their seeds; 22 / 22 repeat their P14-55 action and `coherence` (both guards). The 1 P14-54 offered input repeats too.

| P14-55 null | n | Built-in | LM |
|---|---|---|---|
| time-shuffled d = 1..10 | 800 | 14 -> **0** (CP95 0.0037) | 13 -> **5** (CP95 0.0131) |
| frame-shuffled | 800 | 0 -> 0 | 0 -> 0 |
| near-uniform | 800 | 0 -> 0 | 0 -> 0 |
| `rev_in` | 80 | 2 -> 0 | 1 -> 0 |
| `do_nothing` | 27 | 0 -> 0 | 0 -> 0 |
| `lines` | 80 | 0 -> 0 | 0 -> 0 |

Descriptive (real test offers): `D` min / 5 % / median / 95 % / max: built-in -0.433 / 0.258 / 0.881 / 1.293 / 1.670; LM -0.077 / 0.167 / 0.816 / 1.287 / 1.493. Real test offers with `D < 0`: 1 (built-in), 2 (LM). Per-frame variant (not used by a rule), median: 0.0081 (built-in), 0.0070 (LM).

## Cost (80 real test inputs; 1 thread, background priority, other jobs running)

| | Built-in | LM |
|---|---|---|
| two beam searches `t_beam2`, median (5 % / 95 %) | **0.249 s** (0.153 / 0.425) | **0.105 s** (0.044 / 0.169) |
| coherence-only guard decision, median | 0.331 s | 0.252 s |
| median ratio extra / decision | 0.75 | 0.43 |
| per frame | 0.068 ms | 0.027 ms |

A median sentence has 3,793 frames (37.9 s of data at 0.01 s per frame), so the extra time is less than 1 % of the sentence time. The gate is lazy: a withhold costs nothing extra.

> **Our take:**
> - The LM beam fixes the direction problem of the greedy text. Most real sentences now decode clearly better forward (median about 0.85 per token), and the score is exactly antisymmetric, so `rev_out` is almost never offered.
> - The fail on the built-in guard comes from the threshold rule, not from the direction power. Its `tau` (0.326) is high because the val tail is thin (val values 0.183, 0.297, 0.326 at index 1-3). On test, 5 of its 6 removed offers have `D > 0` (0.13 to 0.30): they decode better forward, but less well than the val 5 % point. The LM guard frames give a lower `tau` (0.134).
> - **Post hoc, for information only (it uses the test set; not a result):** at a fixed threshold 0, both guards would remove 1 and 2 real test offers and give 1 and 2 `rev_out` offers. On val, threshold 0 removes 1 / 66 and 2 / 66. The P5-36 argument for a fixed threshold 0 (a forward English LM; `x` and `rev x` cannot both pass) applies to this score as well. A fixed-0 rule needs a new pre-registration and data that is not yet seen (for example new time-reversed draws on another Willett split or another dataset), because this test set is now used for that choice.
> - Why the two guards differ: the feature reads the frames after each guard's frame scaler. The LM guard's frames are the frames the LM readout is used with. The beam is 2.4 times slower on the built-in guard's frames, so these frames probably keep more candidates per frame (we did not measure this). A version that always reads the LM-guard frames (or the raw decoder frames) for both guards is a second option.

## Deviations from the plan

None. The run used the pre-registered inputs, seeds and rules. The plan estimate was 30-60 min; the run took 520 s.

## Run record

CPU only, isolation class `background`, 1 thread, keep-awake. 14:17:13-14:25:53 (520 s): val 114 s, test (both guards, with LTT) 366 s, nulls 40 s. Peak working set 519 MB. Inside the 3 h cap.

## Limits

- One participant (T5), one decoder checkpoint, one LM, one beam setting; 80 test sentences, so a count of 4 vs 6 has a wide interval.
- `rev_out` is one synthetic fault form (rows reversed after the decoder). A partial reversal or a reorder of chunks is not tested.
- The cost numbers come from a shared machine; they are indicative only.
