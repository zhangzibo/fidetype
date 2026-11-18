---
title: M2-19 trust config re-tune for the M4-12 decoder - results
type: experiment
task: M2-19
updated: 2026-11-15
---

# M2-19: trust config re-tuned for the retrained T15 decoder

Plan (committed before any run): [plan.md](plan.md), commit `0415f4c`. Frozen configs (committed before the `val_eval` run, commit `0727ae1`): [configs/](configs/). Code: [decode.py](decode.py), [run.py](run.py), post hoc [posthoc_gate.py](posthoc_gate.py). Tables: [results/tables.md](results/tables.md). Numbers: `results/fit.json`, `results/eval.json`, `results/controls.json`, `results/posthoc-gate.json`. Log: `results/run.log`.

## Setting
| item | value |
|---|---|
| data | Brain-to-Text '25, T15 neural data (CC0), M4-01/02 derived files (read only) |
| decoders | M4-12 `m4-12-fixed0` (dedicated L 0, primary) and `m4-12-shared` at L 0 (secondary); checkpoints unchanged |
| new decodes | `val_select` + `val_eval` on the GPU into `C:\Users\zhang\bci-data\derived\m2-19-trust-retune\`. The `val_eval` log-probs are bit-equal to the M4-12 ones (701/701, both models) |
| fit data | `val_select` (722 even-index `val` trials): fit-A 371 (positions 0::2 per session), clean cal 351 (1::2) |
| test data | `val_eval` (701 odd-index `val` trials); not used for any fit |
| recipe | `paper1_v4_harness_config` (guard on, policy grid on fit-A with plug-in wrong-commit <= 0.05), then LTT on clean cal |
| guarantee | LTT, alpha 0.05, delta 0.1, exact binomial p-value, grid 1.00 -> 0.00 step 0.01, combine max (same as the old config `tcfg-f5ca0020b3b8fce2`) |
| risk | wrong-commit rate = wrong COMMITs / all trials |

## Where the old frozen config came from
`tcfg-f5ca0020b3b8fce2` was made in M4-06 on the **online** logits of `t15_copyTask.pkl` (the published online RNN, not our GRU), split A (fit-A 411, clean cal 401), with the same recipe and guarantee (LTT alpha 0.05, delta 0.1; lambda_hat 0.00, final commit_p 0.3 from the grid). Its frame T (3.8151) and sentence T (4.4440) belong to that decoder. On the M4-12 decoder it gives 0 commits.

## Results

### Fitted configs (fit on `val_select` only)
| decoder / method | config_id | frame T | sentence T | grid commit_p | lambda_hat | final commit_p | guard commit_max_risk | offer_max_k |
|---|---|---|---|---|---|---|---|---|
| dedicated L 0 / LTT (**primary**) | `tcfg-e7e8c472f6d9ab33` | 1.2385 | 7.7998 | 0.4 | 0.33 (p 0.0344) | **0.4** | 1.0 (guard off for COMMIT) | 1 |
| dedicated L 0 / CRC | `tcfg-aa410b001a0f1db5` | 1.2385 | 7.7998 | 0.4 | 0.3062 (bound 0.0483) | 0.4 | 1.0 | 1 |
| shared L 0 / LTT | `tcfg-af10f34fd5cc03a5` | 1.1945 | 7.8308 | 0.4 | 0.33 (p 0.0621) | 0.4 | 1.0 | 1 |

- The grid threshold (0.4) is stricter than lambda_hat (0.33), so the grid sets commit_p, as in the old config. LTT and CRC give the same final config values, so their `val_eval` results are identical.
- Clean cal: 7/351 commits, 4 wrong (dedicated); 7/351, 3 wrong (shared).

### `val_eval` (701 held-out trials)
| config | commits (rate) | wrong-commit (rate) [CP95] | error among commits [CP95] | eWPM | COMMIT / OFFER / ASK / ABSTAIN | stream = batch |
|---|---|---|---|---|---|---|
| **dedicated L 0, re-tuned LTT** | **9 (0.013)** | **6 (0.0086) [0.0031, 0.0185]** | 0.667 [0.299, 0.925] | **6.03** | 9 / 692 / 0 / 0 | 701/701 |
| dedicated L 0, re-tuned CRC | 9 (0.013) | 6 (0.0086) [0.0031, 0.0185] | 0.667 | 6.03 | 9 / 692 / 0 / 0 | 701/701 |
| shared L 0, re-tuned LTT | 9 (0.013) | 7 (0.0100) [0.0040, 0.0205] | 0.778 [0.400, 0.972] | 5.94 | 9 / 692 / 0 / 0 | 701/701 |
| dedicated L 0, old frozen | 0 | 0 | — | 5.94 | 0 / 701 / 0 / 0 | 701/701 |
| shared L 0, old frozen | 0 | 0 | — | 5.88 | 0 / 701 / 0 / 0 | 701/701 |

| baseline (dedicated / shared) | eWPM | wrong-commit |
|---|---|---|
| always commit (re-tuned frame T) | 5.60 / 5.52 | 0.913 / 0.913 (640/701) |
| gaze typing alone | 4.02 / 4.02 | — |

- **Guarantee check:** the `val_eval` wrong-commit rate is 0.0086, below alpha 0.05. The CP95 upper bound (0.0185) is also below 0.05. So the guarantee holds on this held-out draw, for both decoders and both methods.
- **Decision rules (plan):** commit rate > 0 (yes, 9), wrong-commit <= 0.05 (yes), eWPM > old config 5.94 (yes, 6.03, +0.09), stream = batch 701/701 (yes). So the pre-declared success criteria are met.
- No empty commits on real input (`n_commit_empty` 0). Silent error 0.

### Controls (dedicated LTT config, 300-trial draw of `val_eval`, rng seed 0)
| input | commits | of them empty text |
|---|---|---|
| real | 4/300 | 0 |
| frame-shuffled | 0/300 | 0 |
| **uniform (jitter 0.05)** | **186/300** | 162 (the other 24 are one word) |

The re-tuned config fails the uniform control. The grid picked `commit_max_risk` 1.0, so the guard does not stop a COMMIT. On no-signal input the decoder gives an empty (or one-word) top-1 with a high calibrated p_top1. This is the M2-18 empty-commit mechanism. NTS 1.x rule TD-9 forbids a blank final text COMMIT.

### Post hoc (not in the plan): the M2-18 commit gate
`with_commit_gate(min_chars 1, min_words 0, max_guard_risk 1.0)` on the primary config (`tcfg-4e6143e37d1642f3`). A gate only removes commits, so the LTT guarantee still holds.

| | commits | wrong-commit [CP95] | error among commits | eWPM | uniform control | frame-shuffled control |
|---|---|---|---|---|---|---|
| re-tuned LTT | 9 | 6 [0.0031, 0.0185] | 0.667 | 6.03 | 186/300 | 0/300 |
| re-tuned LTT + gate | 7 | 4 [0.0016, 0.0145] | 0.571 | 6.03 | **0/300** | 0/300 |

Stream = batch 701/701 with the gate. The gate removed the 2 real commits with guard risk 1.0.

## Our take
> **Our take:** The formal goal is reached: the re-tuned config commits, and the held-out wrong-commit rate (0.0086, CP95 upper 0.0185) is well under alpha 0.05. But the practical value is very small. Only 1.3 % of trials commit, the commits are short (1 to 2 words), and 6 of 9 commits are wrong. The eWPM gain over the old config is +0.09 (6.03 vs 5.94), which is within noise. The guarantee holds mostly because the commit rate is tiny, not because the commits are good.

> **Our take:** The per-trial wrong-commit risk is the wrong safety lens at this decoder accuracy. With a top-1 sentence-exact rate of about 9 %, any commit policy with alpha 0.05 will commit few trials, and the error rate among commits can still be high. A user-facing claim needs a bound on precision (error among commits), or a risk with a minimum commit rate. This is a design question for P5-02.

> **Our take:** The re-tuned config must not ship without the commit gate (or the v5 recipe): it commits 186/300 uniform streams. Re-tuning on a new decoder can switch the guard off for COMMIT, so the control checks must be part of every re-tune.

> **Our take:** The real bottleneck is the decoder plus our word decoder (WER about 0.40, sentence exact about 0.09). Better trust tuning cannot make commits useful at this accuracy. The next gain comes from the decoder (M4-12 is at 2.5x the published PER) or a stronger LM.

## Limitations
- One participant, one split, one test draw. One draw cannot prove a 1 - delta statement.
- 9 commits: all commit-side estimates have wide CIs (error among commits CP95 [0.299, 0.925]).
- `val_select` chose the M4-12 checkpoint (best = last step in all runs, so no real choice); we judge the bias as negligible.
- The guarantee is for the mix of the 41 sessions, not per session.
- The word decoder settings were tuned on the online logits (M2-10), not on this decoder.
- The commit-gate analysis is post hoc.

## Deviations from the plan
- Added a post hoc commit-gate analysis after the uniform control failed (labelled as post hoc; no pre-declared number changed).

## Note 2026-11-18: P14-21 rerun with word-decoder edit penalty 8

P14-21 ([results](../2026-11-17-p14-21-edit8-rows/results.md)) refit and re-evaluated with the word decoder at edit penalty 8. Reference (edit 12) reproduced all configs and rows. **Effect:** dedicated_0 LTT / CRC 9 -> 21 commits, 6 -> 15 wrong; shared LTT 9 -> 28, 7 -> 18 (commit-rate half-width 0.009). Held-out wrong-commit stays below alpha 0.05 (CP95 upper 0.035 / 0.040). eWPM does not change by its half-width. Ungated frame-shuffled control: 0 -> 3 of 300 commits (the M2-18 gate used by later rows keeps it at 0). The numbers above stay as committed.
