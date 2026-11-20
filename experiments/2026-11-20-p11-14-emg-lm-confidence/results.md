---
title: P11-14 guard confidence for the in-beam LM EMG decoder - results
type: experiment
task: P11-14
updated: 2026-11-20
---

# P11-14: a guard confidence for the in-beam LM decoder (results)

Pre-registration: [plan.md](plan.md) (commit `39f6432`, before any real-window computation). Code and amendment 1: `a3d50eb` (before any real-window guard, selection or decision). Card script: `659616f`. Aggregates: [results/results.json](results/results.json), guard sheets `results/guard-*.json`, confidence models `results/model-L-{F,FL}.json`, card check [results/card-results.json](results/card-results.json), log `results/run.log`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page and the committed files hold pooled aggregates only: no per-user value, no text, no id. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-prompt files: `C:\Users\zhang\bci-data\derived\p11-14\` only. The P11-01, P11-07, P11-09, P11-11 and P11-12 files were read only.

Run: 2026-11-19 23:22 to 2026-11-20 00:10, CPU only (isolation class `background`, 2 threads, one process, about 200 MB), detached. No GPU.

## Outcome
**A learned confidence makes the in-beam LM decoder the best certified EMG guard so far. The primary arm L-FL was selected on the calibration tuning items only. It gives a certified safe WPM v0.1 of 6.80 [4.49, 9.63], with 285 commits and 52 wrong (4.3 % of 1,221 test prompts). This is above the P11-12 values (S 4.10, SL 5.08) and above the P11-07 confidence on the same decoder (3.37). It is also the first EMG value whose CI lies fully above the no-BCI reference (3.09). Every control passes. The acoustic-only posterior (arm A) fails as a confidence: it is near zero for almost every LM-fused top-1.**

## What gives the gain
The commit text is the same in every arm of a decoder. Only the confidence changes.

| Signal (FL decoder) | Tuning AUROC (765 calibration items) | Test AUROC (real, committable) |
|---|---|---|
| `p_nb`: own n-best posterior (P11-07 arm S) | 0.841 | 0.807 |
| `p_fU`: fused posterior over the wider set U (beam + no-LM 64-best) | 0.888 | 0.880 |
| `p_aU`: acoustic-only posterior over U | 0.591 | 0.600 |
| `lm_pc`: LM log-prob per character of the top-1 | 0.821 | 0.849 |
| `dist_g`: distance to the greedy text (lower is better) | 0.618 | 0.619 |
| `agree_b0` / `agree_g` | 0.540 / 0.542 | 0.534 / 0.530 |
| **L** (learned; tuning value cross-validated) | **0.910** | **0.908** |

Decoder F gives the same picture (test AUROC: `p_nb` 0.746, `p_fU` 0.846, `p_aU` 0.664, `lm_pc` 0.804, L 0.877).

The fitted L-FL model has 6 non-zero weights. The largest are `lg_p_fU` (+1.66) and `lm_pc` (+1.13), then `lg_p_nb` (+0.27), `dist_g` (-0.27), `kps` (+0.18) and `log_nw` (-0.11). Backward elimination dropped `ac_gap`, `agree_b0`, `lg_p_aU` and `agree_g`.

> **Our take:** P11-07 blamed "LM fusion makes the posterior over-confident". The data say something more specific. The problem is the **small n-best** (at most 8 key sequences at beam 8): its posterior ignores strong competitors that the beam pruned away. Re-scoring the same fused score over a wider competitor set (with the no-LM 64-best) fixes most of it (AUROC 0.81 -> 0.88). A plain "is this a likely English sentence" term (`lm_pc`) adds the rest. The acoustic evidence alone does not help: the LM changes letters, so the fused top-1 is almost never the acoustically best text, and its acoustic posterior is near zero for right and wrong texts alike.

## Selection of the primary arm (tuning items only; pre-registered criterion)
Simulated LTT on the 765 tuning items, then the unguarded WPM of those commits. L uses 5-fold cross-validated scores.

| Candidate | Tuning criterion (WPM) | Commits / wrong (of 765) |
|---|---|---|
| P-F | 1.41 | 25 / 1 |
| A-F | 0.79 | 20 / 5 |
| L-F | 6.67 | 161 / 30 |
| P-FL | 5.47 | 142 / 30 |
| A-FL | 0.78 | 22 / 7 |
| **L-FL** | **7.06** | 170 / 29 |

**Primary arm: L-FL.** The tuning values use the larger simulated LTT set (765, not 459). They only rank the candidates and are not test values.

## Verdicts (pre-registered)
| Id | Statement | Result | Verdict |
|---|---|---|---|
| **H1 (primary)** | L-FL certified, safe, non-vacuous, V6 pass, value >= 4.10 | certified; 52 / 1,221 = 0.043 <= 0.05; 6.80; controls pass | **pass** |
| **H2** | value > 5.08 (best `intended_text` entry) | 6.80 | **pass** -> new card |
| H3 | better than arm P on the same decoder | 6.80 vs 3.37 (P-FL) | **pass** |
| H4 | above no-BCI | 6.80 [4.49, 9.63] vs 3.09 | **clearly above** (CI low end > 3.09) |
| C0 | P-FL reproduces P11-07 arm S | threshold 0.70, 154 commits, 43 wrong, 3.371 | **pass** (exact) |
| V6 | controls | calibrate: uniform 0, frame-shuffled 0, input-level 0 of 300; test time-shuffled 0, zero EMG 0 of 1,221 | **pass** |

## Main numbers (1,221 track-test prompts of the 8 users; 4,985 intended words; 119.8 min neural time)
| Arm | Threshold | Safe WPM v0.1 [95 % CI] | Commits / wrong | Wrong rate, CP95 (level 0.95) | Error among commits | Calibrate controls (unif / frame-shuf / input) | V4 |
|---|---|---|---|---|---|---|---|
| P-F | p_top1 0.30 | 2.33 [1.58, 3.28] | 92 / 23 | 0.019 [0.012, 0.028] | 0.250 | 0 / 1 / 0 | below |
| A-F | p_top1 0.60 | 0.43 [0.12, 0.93] | 14 / 1 | 0.001 [0.000, 0.005] | 0.071 | 0 / 0 / 0 | below |
| L-F | p_top1 0.65 | **7.02 [4.67, 10.04]** | 280 / 49 | 0.040 [0.030, 0.053] | 0.175 | 0 / 0 / 0 | clearly above |
| BL-F | learned 0.63 | 5.52 [3.45, 8.00] | 233 / 51 | 0.042 [0.031, 0.055] | 0.219 | 0 / 1 / 0 | clearly above |
| P-FL (= P11-07 S) | p_top1 0.70 | 3.37 [1.92, 5.18] | 154 / 43 | 0.035 [0.026, 0.047] | 0.279 | 0 / 2 / 0 | above |
| A-FL | p_top1 0.60 | 0.43 [0.12, 0.92] | 16 / 3 | 0.002 [0.001, 0.007] | 0.188 | 0 / 1 / 0 | below |
| **L-FL (primary)** | p_top1 0.63 | **6.80 [4.49, 9.63]** | 285 / 52 | 0.043 [0.032, 0.056] | 0.182 | 0 / 0 / 0 | clearly above |
| BL-FL | learned 0.74 | 5.67 [3.71, 8.15] | 221 / 39 | 0.032 [0.023, 0.043] | 0.176 | 0 / 1 / 0 | clearly above |
| P11-12 S / SL (reference) | 0.55 / 0.61 | 4.10 [1.99, 6.60] / 5.08 [2.67, 7.96] | 167 / 35; 194 / 31 | 0.029; 0.025 | 0.210; 0.160 | | above |

Every arm: V1 certified, V2 holds, V3 non-vacuous, V6 pass. Test time-shuffled and zero-EMG commits are 0 / 1,221 for every arm. The gate withholds 2.2 % of real test windows.

L-FL details:
- 951 right words committed; correction time 20.0 min.
- Actions: 285 commits, 88 offers, 848 withholds.
- Proposed v0.2: 6.80. With the P14-28 reading cost: 6.43.
- Offline decision time with the decode memoised: p50 25 ms, p95 65 ms.
- Always-commit reference (gated FL top-1, no bound): 396 right, unguarded WPM 3.72.

> **Our take:** the empirical wrong-commit rate of L-FL (0.043) is close to alpha (0.05), and the CP95 upper end (0.056) is just above it. That is the expected position for a guard that spends its risk budget. The bound is a (1 - delta) statement on the rate, and it holds here. L-F has a slightly higher point value (7.02), but it was not selected: the selection used tuning items only, and the two CIs overlap almost fully. The built-in learned score with acoustic and LM fields (BL) also beats 5.08, but less than L. It cannot see the wider competitor set U.

## Benchmark entry
New declared-subset card (P11-13 convention): `benchmark/results/v0.2/emg2qwerty__p11-14-intended-lfl-subset8__guard.json`. It uses target `intended_text`, status certified, and a rerun recipe with `code_ref` `659616f`. The track scorer gives the same value (6.8031), commits (285), wrong commits (52), words, correction time and no-BCI reference as this page. Its CI is [4.36, 9.65]; it differs from the runner CI only by the cluster label order (as in P11-13). Scorer controls: shuffled pass, zeros pass, null commit pass. Pooled top-1 intended CER on the card: 0.183. The leaderboard was regenerated, and `python -m fidetype.benchmark.leaderboard --check` passes.

## Deviations (stated honestly)
1. **Amendment 1** (before any real-window guard, selection or decision): the two-item n-best of A and L is empty at c <= 0.5. A synthetic check showed that the empty reject item as top-1 distorts the `calibrate` temperature (p_top1 compressed into [0.50, 0.56]). Commits are unchanged: they were only possible at c > 0.5 before.
2. A 6-window calibration smoke test of the decoder code ran before the code commit (mechanics and timing only).
3. The card offers show only the top-1 text (the A / L n-best has one real choice). This does not change safe WPM, which counts commits only.

## Gap rule
**Gap 123 closes:** the primary arm meets the done-when. It is a pre-registered confidence for the in-beam decoder (a learned score with beam features), with a certified, non-vacuous safe WPM v0.1 of at least the P11-12 value on the same split, with the same gate and controls.

## Note for P15-25 (gap 91)
P15-25 should use the P11-07 in-beam decoder FL with the P11-14 confidence L-FL for certified commits. It is the most accurate decoder (top-1 intended exact 32.4 % gated) and now also gives the highest certified value. Limits that carry over: the 50 ms CPU budget is not met (gap 37 / P3-12, gap 122). The L features need the no-LM 64-best beam as well, which adds work at the window end (decision p95 65 ms offline with a memoised decode; P3-12 must count it).

## New gaps
| Gap | Item | What |
|---|---|---|
| (new) | P11-15 | Streaming / latency cost of the L confidence: L needs a second (no-LM, beam 64) beam and an exact CTC re-scoring per window. Measure the end-of-window cost and test a cheaper competitor set (for example the in-beam LM beam at a larger width only) under the 50 ms rule (with P3-12) |
| (new) | P11-16 | Confidence for prefix commits: arm X (P11-12) used the built-in learned prefix score. Apply the P11-14 signals (`p_fU`, `lm_pc`) to word-prefix commits (safe-wpm/0.2) with the in-beam decoder |

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-20-p11-14-emg-lm-confidence/test_p11_14.py` |
| Full run (detached; about 48 min CPU) | `.venv\Scripts\python.exe experiments/2026-11-20-p11-14-emg-lm-confidence/launch.py all` (needs `derived\p11-09\` prompts and `lp\`, `derived\p11-11\` LM, lexicon and `nbest.pkl`, `derived\p11-12\gate.json`) |
| Card | `.venv\Scripts\python.exe -I experiments/2026-11-20-p11-14-emg-lm-confidence/cards.py score cards --code-ref 659616f`, then `python -m fidetype.benchmark leaderboard --results benchmark/results/v0.1 benchmark/results/v0.2 --out benchmark/site` |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-14\DONE` exists; stop the python processes whose command line has `p11-14-emg-lm-confidence` |

## Limits
- 8 users, one track-test session each. The CIs use the user as the cluster unit, so they are wide.
- The target is the intended text after Backspace, not the track's raw keys.
- The guarantee assumes exchangeable val / test sessions of the same users. The confidence model and the gate were fitted on the same calibration sessions (tuning part only; the LTT part stayed clean).
- Offline only; no collector replay. The confidence adds a no-LM beam and an exact CTC re-scoring per window.
- Eight arms were certified and scored. The primary verdicts use the one arm selected on tuning items; the other arms are secondary.
