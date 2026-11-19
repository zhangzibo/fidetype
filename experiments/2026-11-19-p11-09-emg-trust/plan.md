---
title: P11-09 trust config and real-time collector replay for the P11-01 emg2qwerty EMG decoder - pre-registration
type: experiment
task: P11-09
updated: 2026-11-19
---

# P11-09: trust config + real-time replay for the P11-01 EMG streams (pre-registration)

Written and committed **before** any evaluation number of this item was computed or read. Gap 89 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-09](../../wiki/questions/roadmap-standard.md#p11-09-trust-config-and-streaming-replay-for-the-p11-01-emg-streams). It also gives the P11-01 part of P14-10 (gap 8) and the data for a declared-subset emg2qwerty entry (P14-13, gap 27).

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates only: no per-user value, no user pseudonym, no text, no prompt id, no signal, no weights. Every output carries the FEP-0010 flags `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-09\`.

CPU only (isolation runner, class `background`, 4 threads). **No GPU** (P15-08 holds it). RAM target under 4 GB.

## What was done before this plan (disclosure)
- Code: the writer in `src/fidetype/adapters/emg2qwerty.py` and its tests, [run.py](run.py), [launch.py](launch.py).
- Stage `infer` started before this commit. It recomputes the P11-01 personal-model log-probs on the CPU (16 sessions) and the input-level control log-probs. It computes no metric. Its only check is the equality with the cached P11-01 NTS streams.
- One smoke test touched a **calibration** session only: the built-in CTC beam (beam 16, 10-best) alone took p50 22 ms, p95 47 ms, max 64 ms on 39 track-val windows of one user (median 510 frames). So V5 (below) may fail; the budget rule stays as written. No evaluation-session decision was made or read.

## Question
Does a drop-in trust guard on the P11-01 causal EMG decoder (personalised test CER 15.09 %, no LM) give a certified, non-vacuous safe WPM on emg2qwerty, and does the collector decide at real time inside the 50 ms budget?

## Data and splits
- Users: the 8 P11-01 test users (`derived\p11-01-emg-decoder\splits.json`). For each user, P11-01 kept the last 2 sessions as test. The decoder never trained on them, and no checkpoint was selected on them (the P11-01 personal val sessions are earlier sessions).
- Track check (done in code, run stops on a mismatch): for each user, our first test session is the emg2qwerty track **val** session and our second is the track **test** session (`tracks-v0.2` split rule: last session -> test, second last -> val).
- Unit: one scored prompt (track rule: at least 3 in-vocabulary key presses; truth = the `KeyboardEvent.code` sequence of the 32 track classes). Test prompts must equal the track truth rows (`derived\p6-02-scorer\truth\emg2qwerty.jsonl`); a mismatch stops the run.

| Split | Calibration / certify | Evaluate | Role |
|---|---|---|---|
| **Primary (arms P, L)** | all scored prompts of the 8 track-val sessions | all scored prompts of the 8 track-test sessions | track-conformant: calibration uses an open split only. This gives the score card. |
| **Secondary (arm H)** | prompts with bucket 0 | prompts with bucket 1 | exchangeable within-session split over all 16 sessions: bucket = first 8 hex of SHA-256(`fidetype-p11-09-2026-11-19|<session>|<prompt index>`) mod 2. Tests the guarantee when the exchangeability assumption holds by design. No card (it calibrates on track-test prompts). |

The script logs a 16-hex digest of each calibration and evaluation unit list.

**Deviation from the task brief (stated here, before results):** the brief asked for a salted-hash split. A salted-hash split mixes track-test prompts into calibration, so it cannot give a clean track entry. So the primary split is by session (track val -> calibrate, track test -> evaluate). The salted-hash split is arm H (secondary).

## Decoder side (fixed; nothing is refitted)
- P11-01 personal model of each user (`personal-u<i>\best.pt`; SHA-256 must equal the `decoder.weights_sha256` of the cached P11-01 streams), causal, no lookahead, no LM. CPU log-probs over whole sessions (`emgdec.session_log_probs`, chunk 20,000). Check: maximum absolute difference to the cached P11-01 streams <= 1e-3 on the first 5 prompts of each session; else the run stops.
- **Decision window** = the prompt frames `[prompt_lo, prompt_hi)` plus a fixed tail of **20 frames (0.20 s)**, clipped at the session end. Reason: the last key of most prompts is Enter at the prompt end, and the P11-01 emission delay is 70 ms median / 110 ms p90 plus the 32 ms window. The tail is fixed here and not tuned.
- **Writer** (`fidetype.adapters.emg2qwerty`): each of the 98 CTC tokens maps to its track key code with the track truth rule (`a`/`A` -> `KeyA`, `⌫` -> `Backspace`, `⏎` -> `Enter`, digits / other symbols -> no key). `merge_to_key_ctc` sums (log-sum-exp) the token columns of each key code into a 33-column key CTC matrix (blank + 32 keys); no-key tokens join the blank. The guard text has one character per key (Space as `_`); `key_text_to_codes` writes the track units.

## Guard (per arm)
`fidetype.trust.calibrate` on the calibration windows: input kind `logits` (built-in CTC prefix beam 16, 10-best, no LM, no lexicon; frame temperature fitted on the texts), vocabulary `key_ctc_vocab()`, alpha **0.05**, delta **0.1**, method **LTT** (the drop-in default), seed 0, `null_trials` 300, the default commit gate.
- Null inputs (input level): the decoder's output on the **time-shuffled** calibration sessions (features permuted in time, seed = SHA-256 of salt + session), 300 calibration windows drawn with `default_rng(0)`.
- The guarantee: with probability >= 0.9 over the calibration draw, wrong COMMITs / all prompts <= 0.05 (marginal, pooled over the 8 users; one pooled guard, because each user has only about 150 calibration prompts).

| Arm | Split | `confidence` | Role |
|---|---|---|---|
| **P** | primary | `p_top1` (default) | **primary**: card, replay |
| L | primary | `learned` (P5-23) | secondary |
| H | salted hash | `p_top1` | secondary |

A refused arm (`NullControlError`: a null control commits more than floor(0.05 n)) has no guard and no result. Its safe WPM is reported as "refused (no guard)".

## Outcomes

### Primary: safe WPM v0.1 of arm P
The track scorer (`fidetype.benchmark score`, `safe-wpm/0.1`, ADOPTED, unchanged) on a v0.2 submission that covers the 8 track-test sessions (`coverage.subset` declared). Timing: the track's measured per-prompt time (first to last key-down, truth `neural_s`). Correction rule: the scorer default (2 s + 0.79 s per key). CI: the scorer's percentile cluster bootstrap over users (B 2000, seed 0; 8 clusters).

### No-BCI reference
The track defines it in the scorer: **gaze typing of every prompt at 20 characters (keys) per minute** (`no_bci_wpm` of the safe-WPM block, the eWPM gaze reference), computed on the same scored prompts. We report it next to the safe WPM.

### Verdicts (arm P unless named)
| Id | Verdict | Rule |
|---|---|---|
| **V1 guard** | certified / refused | `calibrate` returns a guard (all null controls pass) |
| **V2 safety** | holds / fails / clear violation | wrong commits / all evaluation prompts <= 0.05 -> holds; CP95 lower bound > 0.05 -> clear violation |
| **V3 value** | non-vacuous / vacuous | at least one commit on the evaluation prompts and safe WPM > 0 |
| **V4 vs no-BCI** | above / below / clearly above | safe WPM v0.1 > no-BCI reference -> above; CI lower end > reference -> clearly above |
| **V5 latency** | pass / fail | collector replay: p95 of `added` over decision steps < 50 ms (`fidetype.collector.latency.BUDGET_MS`) |
| **V6 controls** | pass / fail | scorer controls on the evaluation prompts: shuffled and zeros CER gaps and the null-commit check (`controls.passed`) |
| V2-L, V2-H | as V2 | arms L and H |

### Controls
1. `calibrate` controls: uniform and frame-shuffled (300 each) plus the 300 input-level time-shuffled null inputs. Pass iff commits <= floor(0.05 n).
2. Track controls (in the submission): **shuffled** = the test-session features time-shuffled, then the same decoder, writer and guard; **zeros** = zero EMG (every band at log(1e-6), the feature of a zero signal), then the same chain. The scorer reports their CER gaps and the null-commit rate.

### Real-time replay through the collector
- 240 evaluation prompts spread evenly over the arm-P evaluation order (`np.linspace`, all 8 users), about 45 min at real time. Stream: NTS 1.0 header (key CTC vocabulary, `frame_period` 0.01 s, provenance meta + FEP-0010 flags); per prompt the window frames at 100 Hz, a source `segment_end`, then a 0.5 s pause.
- Transport: WebSocket binding (`/nts`, 127.0.0.1), sent at real time by `fidetype.collector.bench.run` (profile `implant-logits`): validate (provenance) -> segment (source boundaries only) -> guard (the arm-P guard in a per-user profile, online ACI, input kind `logits`: the CTC beam runs **inside** the collector) -> JSON Lines NTS stream + decision log + `os_text` stub + WebSocket `/decisions`.
- **Decision latency** = the collector's `added` stage at the decision steps (from the receipt of the `segment_end` to the last exporter). We report p50 and p95 (V5), the per-stage table, the conformance level of the outputs, the actions, the wrong commits, and the agreement of COMMIT vs not-COMMIT with the offline arm-P decisions of the same prompts. The 0.20 s tail is a fixed wait of the decision window, not collector latency; we state it next to the latency.
- The replay gives latency and agreement. The safe WPM comes from the offline decisions (the scorer).

### Secondary (reported, not decided)
1. Proposed `safe-wpm/0.2` (not adopted) of arm P: sentence commits only, (a) plain, (b) with the P14-28 `aac-gaze-v1` reading cost 0.5 s per commit + 0.3 s per committed word. No prefix commits: key sequences with Backspace have no clean word prefix.
2. Arms L and H: commits, wrong commits with CP95, safe WPM v0.1 (direct `safe_wpm`, user cluster bootstrap).
3. Per arm: top-1 exact rate, commit rate, error among commits, LTT threshold, frame temperature, decision time per prompt (offline), the always-commit card of the same decoder (CER, eWPM; no certified bound).

## Score card
If the leakage checks pass (track splits, truth equality, weights SHA-256) and the scorer accepts the submission, we add **two declared-subset cards** to the research-only section of the leaderboard, whatever the values: `emg2qwerty__p11-01-crt-subset8__guard` and `...__always-commit`, each with a rerun recipe. Then `python -m fidetype.benchmark.leaderboard` and `--check`. The cards are marked partial (8 of 104 sessions).

## Order, limits, outputs
1. Commit this plan before any decision on evaluation prompts. Then commit the code with the full pytest (low priority).
2. Run detached: `launch.py` (driver -> isolation runner, `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`, keep-awake in run.py). Stages: `infer` (torch venv, CPU), then `all` = prompts, guards, decide, score, replay. Resumable: each finished stage or arm is a file in `derived\p11-09\` and is skipped on a rerun. A `DONE` file marks the end.
3. A stage killed for low memory is not restarted automatically; it is reported as not run.
4. No change of split, window, writer, guard settings, metric, rule or controls after this commit. Any variant (another tail, an LM, a lexicon, prefix commits, per-user guards) is a new item.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including a failure.
