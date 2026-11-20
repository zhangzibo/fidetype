---
title: P11-12 no-signal gate for the EMG intended-text guard - pre-registration
type: experiment
task: P11-12
updated: 2026-11-19
---

# P11-12: a no-signal gate for the EMG intended-text guard (pre-registration)

Written and committed **before** any decision on an evaluation (track-test) prompt was computed or read with the new gate. Gap 104 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-12](../../wiki/questions/roadmap-standard.md#p11-12-no-signal-detector-for-the-emg-intended-text-guard). This item is also the path to close gap 102 (P11-11, reopened). Follow-up of [P11-11](../2026-11-19-p11-11-emg-nonvacuous/results.md) and [P11-09](../2026-11-19-p11-09-emg-trust/results.md).

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates only: no per-user value, no user pseudonym, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-12\`. The P11-09 and P11-11 files (`derived\p11-09\`, `derived\p11-11\`) are read only.

CPU only (isolation runner, class `background`, 4 threads). **No GPU.**

## Problem (from P11-11)
On time-shuffled EMG, the n-best list after the LM and the lexicon holds **one common real word** with a high probability. The out-of-lexicon gate (P11-11 amendment 1) does not stop a real word. So:
- the sentence arms S and SL were refused: the input-level time-shuffled control committed 19 and 20 / 300 (allowed 15);
- the word-prefix arm X was certified (14 / 300), but committed on 76 / 1,221 = 6.2 % of the time-shuffled **test** inputs (limit 5 %).

## What was done before this plan (disclosure)
A planning probe on **calibration (track-val) windows only** (all 1,224 real and all 1,224 time-shuffled windows of the 8 users; P11-09 log-probs and the P11-11 beam cache; no track-test window was read). Signal-side statistics of the decoder output, real vs time-shuffled:

| Statistic (per decision window) | Real: 1 % / 50 % / 99 % | Time-shuffled: 1 % / 50 % / 99 % |
|---|---|---|
| Greedy CTC key emissions (argmax, repeats joined, blank dropped) | 15 / 29 / 50 | 0 / 0 / 5 |
| Key emissions per second of window | 1.89 / 4.64 / 7.96 | 0 / 0 / 0.54 |
| Share of blank argmax frames | 0.892 / 0.945 / 0.978 | 0.994 / 1.000 / 1.000 |
| Words of the no-LM beam top-1 | 3 / 4 / 9 | 0 / 0 / 1 |

On the tuning part (below): real key emissions min 13; time-shuffled max 11 (one window), all others at most 7. Time-shuffled EMG makes the decoder emit almost nothing; the LM and the lexicon then build a word from the weak n-best tail. The **acoustic** evidence separates the two classes almost perfectly. These numbers chose the gate below. Because the probe read all calibration windows, the gate parameters are fixed by a rule on the tuning part only.

## Question
With a no-signal gate that reads only the decoder's acoustic output (no LM, no lexicon), does the P11-11 sentence arm S give a **certified, non-vacuous safe WPM v0.1 that passes all P11-09 controls**? Does the prefix arm X then pass the evaluation null control (<= 5 %)?

## Gate design (fixed here)
For a decision window `x` (T frames of key-CTC log-probs, 33 columns, blank 0, frame 10 ms):
- `n_keys(x)` = number of greedy CTC emissions: the per-frame argmax, runs of the same index joined, blank removed.
- `kps(x)` = `n_keys(x) / (0.01 T)` (key emissions per second of window).
- **Gate passes** iff `n_keys >= K_MIN` and `R_MIN <= kps <= R_MAX`. If the gate fails, the decoder returns an empty n-best list, so the guard **withholds** (the same path as the P11-11 OOV gate). The gate runs first; the P11-11 decoder (beam 64, intended text, LM w, OOV penalty c, OOV gate) is unchanged after it.

**Fit rule (fixed here).** Fit set F = the calibration prompts at the first 765 positions of calibrate's order (`default_rng(0).permutation(1224)`: fit + policy-grid parts; the same positions as the P11-11 tuning part). The 459 LTT (certify) positions and the 300 null-control windows are never used to fit.
- `K_MIN` = the largest integer k with `#{real F windows with n_keys < k} <= floor(0.01 * 765) = 7`.
- `R_MIN` = the 8th smallest `kps` of the real F windows (so at most 7 real F windows lie below it).
- `R_MAX` = 2 x the largest `kps` of the real F windows (a plausibility bound: no faster than twice the fastest calibration prompt; it stops near-uniform frames).
- Report (as a check, not to choose): the pass rate of the gate on the time-shuffled F windows **outside** the 300 null-control prompts (572 windows), and the share of real F windows gated.
The gate uses track-val (calibration) data only, as the P11-11 tuning rule. No track-train decoder output exists on disk; a run of the decoder on the 927 track-train sessions is not needed for this rule and is not done.

No other gate variant (no classifier, no entropy rule) is tested. One gate only, so there is no selection among gates.

## Data, splits, decoder (as P11-11, unchanged)
- 8 P11-01 test users; per user, track-val session = calibration (1,224 prompts), track-test session = evaluation (1,221 prompts). `check_track_splits` checks it. Unit-list digests must equal P11-09.
- Windows: P11-09 log-probs `derived\p11-09\lp\` (real, time-shuffled, zero EMG); window = prompt frames + 0.20 s.
- Decoder: the P11-11 decoder with its tuned `(w, c)` from `derived\p11-11\tune.json` (w 0.5, c 4), LM `eng_tatoeba_6gram_mkn_noE2Q.npz`, lexicon 16,875 words, OOV gate 0.5. The beam cache `derived\p11-11\nbest.pkl` is read only; new beams stay in memory or in `derived\p11-12\`.
- Target: the intended text (Backspace applied), as P11-11.

## Guards (per arm)
`fidetype.trust.calibrate` exactly as P11-11 (alpha **0.05**, delta **0.1**, LTT, seed 0, `null_trials` 300, `null_inputs` = the same 300 input-level time-shuffled calibration windows; automatic uniform and frame-shuffled controls), with `decode_fn` = gate + P11-11 decoder.

| Arm | Commit unit | `confidence` | Role |
|---|---|---|---|
| **S** | sentence | `p_top1` | **primary** |
| SL | sentence | `learned` | secondary |
| X | word prefix | `learned` | secondary (proposed v0.2) |

Arm K (raw keys) is not rerun: it was vacuous with 0 commits in P11-11, and a gate can only remove commits.

## Outcomes and verdicts (as P11-11)
Safe WPM v0.1 (adopted) on the 1,221 evaluation prompts, measured per-prompt time, default correction rule, user cluster bootstrap (B 2000, seed 0). No-BCI reference = gaze typing of each intended text at 20 characters / min (P11-11: 3.09); also against 2.93 (P11-09 raw keys).

| Id | Verdict | Rule |
|---|---|---|
| **V1 guard** | certified / refused | `calibrate` returns a guard (all three calibrate controls <= 15 / 300) with `feasible` true |
| **V2 safety** | holds / fails / clear violation | wrong commits / 1,221 <= 0.05 -> holds; CP95 lower end (Clopper-Pearson at **level 0.95**) > 0.05 -> clear violation |
| **V3 value** | non-vacuous / vacuous | status `certified`, at least one commit, value > 0 (S, SL: v0.1; X: proposed v0.2) |
| **V4 vs no-BCI** | above / below / clearly above | as P11-11 |
| **V6 controls** | pass / fail | the calibrate controls pass, and on the evaluation prompts the input-level time-shuffled and zero-EMG inputs each give a commit rate <= 0.05 |
| V7 gate cost | reported | share of real evaluation windows gated; top-1 exact rate with and without the gate |

### Hypotheses
- **H1 (primary):** arm S: V1 certified, V2 holds, V3 non-vacuous (v0.1), V6 pass.
- **H2:** arm X: V6 pass (evaluation time-shuffled commit rate <= 5 %), V1 certified, V2 holds, V3 non-vacuous; its v0.2 value stays within the P11-11 CI [2.60, 6.34].
- **H3:** the gate removes at most 2 % of real evaluation windows.
- **H4:** arm S is above the no-BCI reference of its target (no prediction of the level).

### Secondary (reported, not decided)
Proposed safe-wpm/0.2 for S, SL, X: plain and with the P14-28 reading cost (0.5 s per commit + 0.3 s per committed word); X also v0.1 complete-only. Per arm: commits, wrong commits with CP95 (level 0.95), error among commits, commit rate, actions, LTT threshold, control counts, offline decision time. Gate: `K_MIN`, `R_MIN`, `R_MAX`, F check rates.

## Gap rule
- **Gap 104 closes** iff H1 holds (S certified, safe, non-vacuous v0.1, V6 pass) **and** arm X's evaluation time-shuffled commit rate is <= 5 % (with its v0.1 and proposed v0.2 values reported on the same split).
- **Gap 102 closes** iff arm S (v0.1) or arm X (proposed v0.2) is certified, safe (V2), non-vacuous (V3) **and** passes V6. Results state which arm.
- Otherwise the gap stays open with the numbers, and every new limit becomes a new roadmap item and open-gap entry.

## Score card
The emg2qwerty track target is the raw key sequence, and the track scorer compares commits to it. Arms S, SL and X use the intended text, so their commits cannot be scored by the track scorer: they are **not** track entries and get **no** card (the P11-11 rule). The P11-09 cards keep the track-conformant result. A track that scores intended text would be a new item.

## Order, limits, outputs
1. Commit this plan before any evaluation decision with the gate. Then the code ([run.py](run.py), tests).
2. Stages (detached through the isolation runner if over 10 min; files in `derived\p11-12\`; a `DONE` file marks the end): `gate` (fit), `guards`, `decide` (real, shuffled, zeros), `score`.
3. No change of split, window, decoder, gate rule, metric or controls after this commit. Any variant is a new item.

Write-up: `results.md` in this folder with the verdicts and numbers as computed, including a failure.
