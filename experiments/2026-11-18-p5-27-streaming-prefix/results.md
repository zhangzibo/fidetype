---
title: P5-27 streaming word-by-word prefix commits within one trial - results
type: experiment
task: P5-27
updated: 2026-11-19
---

# P5-27: streaming word-by-word prefix commits (results)

Pre-registration: [plan.md](plan.md), commit `5f74c2f` (plan, library code, tests, proposal section 7 and [`run.py`](run.py) in one commit, pushed before the `views` stage started). Aggregates: [`results/results.json`](results/results.json); log: [`results/run.log`](results/run.log); guard files without text: [`results/guard-p5-27-base.json`](results/guard-p5-27-base.json), [`results/guard-p5-27-stream.json`](results/guard-p5-27-stream.json). Per-trial decisions and checkpoint decodes (with text): `C:\Users\zhang\bci-data\derived\p5-27\` (local only).

> **Metric status.** All values use the **PROPOSED** safe-wpm/0.2 (`metric_version "0.2"`) with the P14-28 reading cost (0.5 s per commit + 0.3 s per committed word) and the **PROPOSED** "several commits per trial" extension ([proposal section 7](../../docs/safe-wpm-v0.2-proposal.md#7-several-commits-per-trial-p5-27-proposed-extension-not-adopted)). None of them is adopted. v0.1 stays the adopted metric. The user decides.

## Verdict (T15, pre-registered rule)

**single beats stream.** The streaming guard passes its controls and its safety rule, and it is certified. But it gives about half the safe WPM of the one-commit P5-24 prefix guard.

| arm | safe WPM v0.2 + reading cost [95 % CI] | trials with a commit | commit events | wrong trials / 701 [CP95] | right words |
|---|---|---|---|---|---|
| single (P5-24 prefix guard, one commit at the trial end) | **4.67** [4.26, 5.07] | 465 | 465 | 13 (0.0185) [0.0099, 0.0315] | 1,073 |
| **stream** (append-only commits every 0.48 s) | **2.34** [2.11, 2.57] | 310 | 446 | 5 (0.0071) [0.0023, 0.0166] | 528 |
| Δ stream − single (paired trial bootstrap, B = 2,000) | **−2.32** [−2.63, −2.02], hw 0.31 | | | | |

Rule check: controls pass (stream: uniform 0 / 300, shuffled 0 / 300; allowed 15) · safety holds (0.0071 ≤ 0.05; no clear violation) · status `certified` · Δ = −2.32 < −hw = −0.31 → **single beats stream**.

No-BCI reference 4.02: the stream value (2.34) and its interval are below it. The single arm stays above it (as in P14-28).

## Reference checks (all pass)

- Re-calibrated base guard config id `tcfg-e9758d5133d07fa6` = P5-24; base threshold 0.94.
- Single-arm `val_eval` decisions = P5-24 prefix decisions, **701 / 701**. The single arm reproduces the P14-28 value 4.67 exactly.
- Split hashes: score-fit `285b8c0d9baf5a41`, certify `fadfd84557fcb24b` (= plan).
- Every stream decision event chain passed `check_chain` (`run.py` asserts it per trial).
- The paired bootstrap point values equal the scorer values (4.667 / 2.344).

## Secondary outcomes (reported, not decided)

| outcome | stream | single |
|---|---|---|
| v0.2 without reading cost | 2.41 [2.16, 2.65] | 4.87 [4.43, 5.30] |
| Δ without reading cost | −2.45 [−2.79, −2.12] | |
| v0.1 complete-only view | 0.00 (vacuous: no complete commit) | 1.03 (44 complete commits) |
| prefix / complete commits (final text) | 310 / **0** | 421 / 44 |
| reading time (min, on 218.3 neural min) | 6.4 | 9.4 |

**Streaming guard.** Score fit on 451 items, 61,821 prefix × checkpoint rows (37,292 right); dropped feature `acoustic_gap` (wrong sign). LTT threshold **0.99** (in-sample risk 0.0074, p = 1.1e-4, LTT commit rate 0.435). Weights of the streaming features: `stable_log` +0.29, `at_end` −0.01, `open_last_word` −0.08. Stream config id `scfg-9171461e4f8cf0c2`.

**Commits per trial (stream):** 0: 391 · 1: 195 · 2: 96 · 3: 17 · 4: 2. Conflicts: 0. Mean checkpoints per trial 38.9.

**Commit latency** (commit time − end time of the same true word; word ends from a CTC forced alignment of the true phonemes; 701 / 701 trials aligned):

| | stream | single |
|---|---|---|
| right committed words: median (mean) [p10, p90] | **1.44 s** (1.47) [0.00, 2.88] | 11.20 s (11.67) [4.44, 19.13] |
| words committed before the trial end | 100 % | 0 % |
| right / all committed words in the latency set | 529 / 534 | 1,085 / 1,105 |

**Compute** per checkpoint on `val_eval` (decode + features, 4 threads, background class): median 0.046 s, p95 0.147 s, max 0.336 s. All are below the 0.48 s step.

**stream-p524-score arm** (the P5-24 16-feature score streamed, threshold re-certified on the stream loss): LTT passes only at **1.00** (the fixed sequence stops at 0.99), so the arm never commits: value 0.00 (vacuous), Δ vs single −4.67 [−5.07, −4.26]. Controls 0 / 300 and 0 / 300.

**T12:** not run (as pre-registered: the shared T12 loader exceeds the 1.5 GB cap).

## Exploratory diagnostic (after the verdict; not pre-registered)

One script read the local decisions and checkpoint decodes to see why the stream commits fewer words:

- The stream commits early and then stops. Commits fall at a median 31 % of the trial (p90 52 %, max 82 %). A committing trial gets 1.72 words on average. The single arm commits 2.38 words per committing trial, at the end.
- The end checkpoint scores low under the streaming score: the 1-word prefix reaches 0.99 at the end in only 8.7 % of trials (median 0.954), but at some mid-trial checkpoint in 44 % of trials (median best 0.988). So no trial ever extends its commit at the end, and no trial gets a complete commit.
- Overlap: both arms commit in 275 trials; single only in 190; stream only in 35.

> **Our take:** the stream loses for a structural reason, not for safety. (1) The trial loss gives the guard about 39 chances per trial to make a wrong prefix commit, so LTT needs a very strict threshold (0.99, against 0.94 for the one-commit guard). (2) One threshold serves every checkpoint, and the fitted score ranks end-of-trial prefixes lower than mid-trial ones, so the guard never extends a commit at the end, where the single arm gets most of its words. The latency gain is real: right words appear about 10 s earlier (median 1.4 s after the word ends, against 11.2 s). A hybrid guard (stream commits mid-trial plus the P5-24 decision at the end, or separate mid / end thresholds, certified jointly on the trial loss) might keep the latency gain and the words. Gap 92 = P5-28 registers it.

## Limits

One participant, one split, one seed; conditional intervals only (decisions fixed). The word decoder sees each truncation as a whole sentence. Word ends come from our own decoder's forced alignment, not from audio. Decode time is CPU time on this machine with other jobs running. The metric and its extension are proposals.

## Gap status

- **Gap 76 (P5-27): closed.** The roadmap "done when" holds: a streaming guard commits further words of the same utterance under one trial loss, the decision events chain the commits, and the pre-registered T15 replay reports safe WPM next to the one-commit prefix guard. The verdict is a loss for the stream.
- **Gap 53 (P14-23): stays open** (needs a pre-registered v0.1 value above 4.02 or the user's v0.2 decision).
- **New gap 92 = P5-28:** hybrid streaming + end-of-trial prefix guard (joint certification on the trial loss), with the T12 replication on a lighter loader.

## Run record

`views` 5,788 s (base calibration 239 s; 27,296 calibration, 27,239 evaluation and 22,398 null checkpoints; peak 879 MB), `evaluate` 11 s (peak 672 MB), `verdict` 0 s. One detached runner (`CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`) ran the three stages under `python -m fidetype.utils.isolation run --class background --threads 4` with a keep-awake (`SetThreadExecutionState`); log and DONE file in `C:\Users\zhang\bci-data\derived\p5-27\`. No stage was killed or restarted.
