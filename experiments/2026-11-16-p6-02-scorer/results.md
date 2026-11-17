---
title: P6-02 submission format v0.2 + one-command scorer - baseline results
type: experiment
task: P6-02
updated: 2026-11-16
---

# P6-02: submission format v0.2, one-command scorer, baselines on 4 new tracks

Format and scorer: [docs/benchmark-submission.md](../../docs/benchmark-submission.md). Code: [`fidetype.benchmark.scorecard`](../../src/fidetype/benchmark/scorecard.py). Runner: [run.py](run.py). Score cards (aggregates, no text): [`benchmark/results/v0.2/`](../../benchmark/results/v0.2/). Table: [results/tables.md](results/tables.md). Submissions (they hold decoded text) and truth files: `C:\Users\zhang\bci-data\derived\p6-02-scorer\` only. CPU only, no GPU.

## Done-when check

| Criterion | Status |
|---|---|
| A documented submission format (NTS stream file or NTS-derived JSONL per track, keyed by the salted unit hashes, with decisions, text, timing and the required control runs) | **met**: schema `fidetype.benchmark.submission/0.2`; `units.jsonl` rows or `streams/<unit>.jsonl`; `controls/shuffled` + `controls/zeros`; timing comes from the truth (dataset), latency optional per row |
| ONE command validates against the split, checks the controls and prints the full score card | **met**: `python -m fidetype.benchmark score <track> <submission> (--data <path> \| --truth truth.jsonl)`. Exit 0 only when shuffled, zeros and null-commit (<= 5 %) pass; 1 = controls missing or failed; 2 = rejected |
| Score card: CER / WER or key error, eWPM vs no-BCI, safe WPM @ 0.05 with certification status, wrong-commit, error among commits, commit rate, CIs over the CI unit | **met** (reuses `scoring.build_result` and `safe_wpm`; no metric code duplicated) |
| Baselines on the tracks without any (closes open gap 8 in part) | **met** for b2t24-t12, willett-hw, kt-semg, emg2qwerty (2 entries each). P11-01 has no outputs yet (GPU training not started) |
| Tests in CI without raw data | **met**: `tests/test_benchmark_scorer.py` (10 tests, synthetic KT-sEMG fixture) |

## Results (alpha 0.05, LTT delta 0.1; CIs: cluster bootstrap B = 2000 over the track CI unit)

| Track | Decoder + policy | Units | CER (key error) | eWPM [95 % CI] | No-BCI | Safe WPM @ 0.05 | Wrong-commit [CI] | Error among commits | Commit rate | Controls |
|---|---|---|---|---|---|---|---|---|---|---|
| b2t24-t12 | T12 v2 GRU + word LM + drop-in guard (cal split, n_LTT 330) | 880 | 0.304 [0.281, 0.329] | 6.36 [5.89, 6.84] | 4.00 | **0.48 certified** (17 commits, 9 wrong) | 0.010 [0.005, 0.015] | 0.529 | 0.019 | pass / pass / pass (0.000) |
| b2t24-t12 | same, always commit top-1 | 880 | 0.304 | 5.96 [5.39, 6.49] | 4.00 | n/a (not certified) | 0.931 | 0.931 | 1.000 | pass / pass / **fail** (1.000) |
| willett-hw | published real-time RNN + guard (word-list beam) | 81 of 254 (partial) | 0.077 [0.054, 0.102] | 3.47 [3.21, 3.75] | 3.88 | 0.00 vacuous (guard infeasible) | 0.000 | n/a | 0.000 | pass / pass / pass |
| willett-hw | published real-time RNN text, always commit | 81 of 254 | 0.080 [0.058, 0.103] | 4.71 [4.06, 5.49] | 3.88 | n/a | 0.963 | 0.963 | 1.000 | pass / pass / **fail** |
| kt-semg | LDA (oracle key timing) + guard | 172 | 0.553 [0.521, 0.578] | 3.37 [3.08, 3.46] | 3.61 | 0.00 vacuous (34 LTT items < 45) | 0.000 | n/a | 0.000 | pass / pass / pass |
| kt-semg | same, always commit | 172 | 0.553 | 0.55 [0.38, 1.03] | 3.61 | n/a | 1.000 | 1.000 | 1.000 | pass / pass / **fail** |
| emg2qwerty (**research only**) | per-user LDA (oracle key timing) + guard (3000 val prompts) | 15 867 prompts, 104 users | 0.490 [0.465, 0.514] | 2.57 [2.55, 2.60] | 2.82 | 0.00 vacuous (0 commits) | 0.000 | n/a | 0.000 | pass / pass / pass |
| emg2qwerty (**research only**) | same, always commit | 15 867 | 0.490 | 2.26 [2.23, 2.29] | 2.82 | n/a | 1.000 | 1.000 | 1.000 | pass / pass / **fail** |

Controls column: shuffled / zeros / null-commit (commit rate on zeros). The always-commit entries fail null-commit by design: they commit on zero input. This shows that the scorer catches it.

## What each baseline is

| Track | Decoder output (read only) | Calibration | Controls |
|---|---|---|---|
| b2t24-t12 | T12 v2 log-probs (`derived/2026-11-13-confirmatory-t12-v2/logprobs.npz`): the decoder "val" part = track `cal` (880, checked by text), "pool" = track `test` (880, checked against the truth) | drop-in guard, P14-03 recipe (same word decoder + Tatoeba word LM), now on the track `cal` split, not on test-partition trials as in P14-03 | decoder output level: frames permuted / uniform log-probs |
| willett-hw | `rnn_charProbTimeSeries` of the 81 closed-loop test trials | 195 closed-loop trials of the train + val splits of the earlier sessions; built-in CTC beam + 50k-token word list | decoder output level: rows permuted / uniform rows |
| kt-semg | shrinkage LDA on log-RMS windows (adapter reference decoder), trained on the 20 train runs; test key accuracy 0.433 | 89 cal bursts | input level: key windows from random keys of the same run / zero EMG |
| emg2qwerty | per test user: LDA fit on the user's last train session; test key accuracy 0.507 | 3000 random val-session prompts, pooled | input level, as kt-semg |

Timing: measured per unit on all four tracks (T12 20 ms bins; Willett go cue to sentence end; KT first to last key + one median inter-key interval; emg2qwerty first to last key-down). Track rate models for eWPM: T12 303.98 chars/min, Willett 67.64 chars/min, KT 390.56 keys/min, emg2qwerty 301.33 keys/min.

## Our take

> **Our take:** only T12 gives a certified, non-vacuous safe WPM (0.48). It is far below the no-BCI reference (4.00). The guard keeps the wrong-commit rate at 0.010, but it commits only 17 of 880 trials, and 9 of those are wrong. The decoder (CER 0.30) is the limit, as in P14-05.

> **Our take:** the Willett RNN output is good at the character level (CER 0.080), but only 3 of 81 sentences are exactly right without an LM. Exact-sentence commits need a strong word LM. The built-in word-list beam keeps no candidate on 59 of 81 trials, so the guard finds no certified threshold.

> **Our take:** the EMG key baselines (LDA with oracle key timing, 43-51 % key accuracy) never type a burst or a prompt exactly right. So "vacuous" is the honest status. They exist to exercise the format and the controls, not as results.

## Limitations and open issues

- T12 decoder checkpoint was chosen by early stopping on the track `cal` split (open split, allowed); the guard is calibrated on the same split.
- The T12 and Willett controls are decoder-output stand-ins (shuffled frames, uniform probabilities), not neural input passed through the decoder again. The manifests say so.
- Willett covers 81 of 254 test trials (published RNN output only on closed-loop trials): marked `[partial]`.
- KT-sEMG cal has 89 bursts: the LTT split gets 34 items, fewer than the 45 needed at alpha 0.05. No LTT guard can commit on this track with the cal split alone (CRC or a larger cal set is needed).
- EMG baselines use oracle key timing; not conformant with the track task (no key times at test). P11-01 (continuous decoder) has no outputs yet.
- The T12 stage peaked at about 2.08 GB RSS (word LM of the P14-03 recipe), slightly above the 2 GB target.

## Rerun (repo root)

```bash
.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-16-p6-02-scorer/run.py truth-b2t24-t12 truth-willett-hw truth-kt-semg truth-emg2qwerty t12 willett kt e2q score table
.venv\Scripts\python.exe -m fidetype.benchmark leaderboard
```

Times (CPU): truth < 20 s each; t12 10 min; willett 9 min; kt 30 min (most of it guard calibration on long bursts); e2q 21 min; score 1 min.
