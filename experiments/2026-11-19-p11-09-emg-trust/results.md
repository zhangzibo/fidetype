---
title: P11-09 trust config and real-time collector replay for the P11-01 emg2qwerty EMG decoder - results
type: experiment
task: P11-09
updated: 2026-11-19
---

# P11-09: trust config + real-time replay for the P11-01 EMG streams (results)

Pre-registration: [plan.md](plan.md) (commit `0c53d68`, before any evaluation decision), amendment 1 (`f28416d`: one collector stream per user) and amendment 2 (`36a921c`: CPU/GPU check on probabilities). Code: `9220525` (writer, runner, tests). Aggregates: [results/results.json](results/results.json), [results/replay-summary.json](results/replay-summary.json), guard sheets `results/guard-{P,L,H}.json`. Score cards: [`emg2qwerty__p11-01-crt-subset8__guard`](../../benchmark/results/v0.2/emg2qwerty__p11-01-crt-subset8__guard.json) and [`...__always-commit`](../../benchmark/results/v0.2/emg2qwerty__p11-01-crt-subset8__always-commit.json).

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page and the committed files hold pooled aggregates only: no per-user value, no text, no id. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-prompt files: `C:\Users\zhang\bci-data\derived\p11-09\` only.

Run: 2026-11-19 14:57-17:15, CPU only (isolation runner, class `background`, 4 threads), detached, from a clean git worktree of the code commit. No GPU.

## Outcome
**The guard is certified and safe, but vacuous: safe WPM v0.1 = 0.00 (no commit on 1,221 test prompts), below the no-BCI reference 2.93. The real-time replay fails the 50 ms budget (p95 up to 222 ms), because the built-in CTC beam runs inside the collector.** The decoder side and the writer work: personalised key error rate 17.9 % [14.5, 21.4] on the track scale, both track controls pass, and the offers alone give eWPM 3.44 [3.26, 3.70] vs gaze typing 2.93.

## Verdicts (pre-registered)
| Id | Verdict | Result |
|---|---|---|
| **V1 guard** | **certified** | `tcfg-4af5a234c1cf7826`: LTT feasible, commit threshold p_top1 >= 0.30; null controls uniform 0/300, frame-shuffled 0/300, input-level time-shuffled EMG 0/300 (allowed 15 each). But 0 of 459 LTT items commit in-sample (sheet warning). |
| **V2 safety** | **holds** | 0 wrong commits / 1,221 test prompts = 0.000, CP95 [0.000, 0.003] |
| **V3 value** | **vacuous** | 0 commits (1,221 OFFER) |
| **V4 vs no-BCI** | **below** | safe WPM 0.00 vs no-BCI 2.93 (gaze typing at 20 keys/min on the same prompts) |
| **V5 latency** | **fail** | `added` p95 above 50 ms in all 8 runs (max 222 ms; median over runs 110 ms); p50 58.6 ms (median over runs) |
| **V6 controls** | **pass** | scorer controls of the guard card: shuffled CER 0.995 (gap 0.816 [0.777, 0.852]), zeros CER 1.000 (gap 0.821 [0.784, 0.855]), null commit 0.000 |
| V2-L | holds (vacuous) | learned score (`tcfg-f68bc1dbd7d0ea3a`): 0 commits / 1,221 |
| V2-H | holds (vacuous) | salted-hash split (`tcfg-d105b0436ee08ce0`, 1,254 cal / 1,191 eval): 0 commits / 1,191 |

## Main numbers (arm P, 1,221 track-test prompts of the 8 users)
| Measure | Value |
|---|---|
| Safe WPM v0.1 (track scorer, declared subset) | **0.00**, status `vacuous` (no CI: no commit) |
| Proposed safe WPM v0.2, plain / + reading cost (secondary) | 0.00 / 0.00 (vacuous) |
| No-BCI reference (scorer: gaze typing of every prompt at 20 keys/min) | **2.93** |
| Key error rate (CER of the top-1 key sequence; user cluster bootstrap) | **0.179 [0.145, 0.214]** |
| eWPM (simulated user picks from the offers) | 3.44 [3.26, 3.70] (gaze reference 2.93 [2.86, 3.04]) |
| Top-1 exactly right (whole prompt, key codes) | 2 / 1,221 (0.16 %) |
| Commit / offer / withhold | 0 / 1,221 / 0 |
| Wrong commits, CP95 | 0, [0.000, 0.003] |
| Words / neural time | 5,219 words, 119.8 min (measured first to last key per prompt) |
| Offline decision time per prompt (beam + guard) | p50 58 ms, p95 122 ms |

Always-commit card of the same decoder (reference, no bound): key error rate 0.179, 1,219 of 1,221 commits wrong, eWPM 3.12 [2.91, 3.41]; status `scored: controls failed` (the null-commit control fails by design: it commits on zero input).

**Why vacuous.** A COMMIT must equal the whole prompt key sequence, including the user's own typing errors and Backspace keys (about 28 keys per prompt). At 17.9 % key errors, the top-1 is exactly right on 0.16 % of prompts. So the calibrated top-1 probability never reaches the certified threshold. This matches the M4-12 T15 case (P14-05: a weak decoder gives a safe but vacuous guard).

## Real-time replay through the collector
8 collector runs (one stream per user, amendment 1), 240 test prompts (30 per user, spread evenly), 171,452 frames, 1,834.6 s of stream at real time over the WebSocket binding. Profile `implant-logits`: validate (provenance) -> segment (source boundaries) -> guard (input kind logits, built-in CTC beam 16 **inside** the collector, online ACI, per-user profile) -> NTS stream + decision log + `os_text` stub + WebSocket `/decisions`.

| Stage (ms, 240 decision steps) | p50 (median over runs) | p95 (median over runs) | p95 (max over runs) | max |
|---|---|---|---|---|
| `receive` | 0.06 | 0.12 | 0.14 | 0.23 |
| `processor.check` (validate) | 0.007 | 0.06 | 0.07 | 0.10 |
| `processor.seg` | 0.002 | 0.004 | 0.005 | 0.008 |
| `processor.guard` (beam + guard) | 58.4 | 110.0 | 221.7 | 337.9 |
| `pipeline` | 58.5 | 110.1 | 222.0 | 338.0 |
| **`added`** (budget number, decision latency) | **58.6** | **110.2** | **222.0** | 338.0 |
| `e2e` | 58.8 | 110.5 | 222.3 | 338.4 |

| Item | Value |
|---|---|
| Budget (p95 `added` < 50 ms in every run) | **FAIL** (0 of 8 runs) |
| Fixed wait of the decision window (not collector latency) | 0.20 s after the prompt end |
| Actions | OFFER 240, COMMIT 0; typed by `os_text` 0 (commits only: yes); wrong commits 0 |
| Agreement with the offline decisions (COMMIT vs not) | 240 / 240 |
| Producer level of the outputs (`nts-conform`) | NTS Trust-ready (all 8 runs); producer errors 0 |

> **Our take:** almost all of the decision latency is the CTC prefix beam over a whole prompt (median about 500 frames x 33 keys) at the segment end, in Python. The collector itself adds well under 1 ms (receive + validate + segment + exporters). The P3-08 T15 replay met the budget (p95 2 ms) because its word decoder ran before the collector. Two fixes: run the beam incrementally while frames arrive (the decision then needs only the last frames), or move the beam to the decoder side, as in P3-08, and gate the collector on the n-best guard only. This is the known open gap 37 ([P3-06](../../wiki/questions/roadmap-standard.md#p3-06-logits-guard-inside-the-latency-budget-incremental-decoding)); P11-09 adds real EMG evidence to it. No new gap.

## Checks
| Check | Result |
|---|---|
| Track splits: our first / second test session = track val / track test of each user | 8 / 8 users |
| Test prompts equal the track truth rows (key codes) | 1,221 / 1,221, 0 missing |
| CPU log-probs vs the cached P11-01 GPU streams (first 5 prompts per session) | 16 / 16 sessions: frame argmax agreement 100 %, max log-prob difference 1.8e-3 (at log-probs near -30) |
| Personal weights SHA-256 = the P11-01 stream headers | 8 / 8 |
| Guard file reloads; offline decisions = replay decisions | yes; 240 / 240 |

## Deviations and fixes (stated honestly)
1. **Split** (stated in the plan before results): the primary split is by session (track val -> calibrate, track test -> evaluate), not a salted hash, because only that gives a clean track entry. The salted-hash split is arm H.
2. **Amendment 1:** one collector run per user. The validate processor refuses a stream without `decoder.weights_sha256`, and each user has own weights.
3. **Amendment 2:** the CPU/GPU equality check uses probabilities and the frame argmax; the log-prob check stopped on a 0.0018 difference at log-prob -30.8.
4. **Reporting fix after the run:** with logits input the guard decodes inside, so the input events carry no hypothesis. The first `score` pass therefore read an empty top-1 for the always-commit card (CER 1.0) and the top-1 exact rate (0.0). `top1_text` now takes the committed text or the first offered choice; `score` was rerun on the same, unchanged decisions. The guard decisions, the guard card and every verdict are the same in both passes.

## Benchmark entry
Two **declared-subset** cards in the research-only section (8 of 104 track test sessions; `coverage.subset`). Clean: the decoder never trained on these sessions, and calibration used only the track val sessions of the same users. Each card has a rerun recipe (truth, build = this runner, score) with the policy `config_id` and a reason for the 8 local weight files. This gives the P11-01 part of P14-10 (a certified but vacuous number, with its null-commit audit) and the conformant emg2qwerty entry of P14-13 (no oracle key times). The kt-semg half of P14-13 stays open.

## New gaps
| Gap | Item | What |
|---|---|---|
| 102 | P11-11 | Non-vacuous EMG safe WPM: a commit unit that the decoder can get right (word or key-prefix commits, an intended-text target after Backspace), or LM / lexicon decoding (P11-07), then the same protocol |

The latency failure goes to the existing gap 37 (P3-06, logits guard inside the latency budget).

## Correction (2026-11-19)
`run.py` called `clopper_pearson(wrong, n, 0.05)`. The third argument is the confidence level (`fidetype.utils.binomial.clopper_pearson(k, n, level=0.95)`), so the call gave a 5 % interval. The call now uses 0.95. No number on this page changes: this page quotes the scorer's interval [0.000, 0.003]. Three fields in `results/results.json` were affected: `arms.{P,L,H}.wrong_commit_cp95` held [0.0, 0.0006]. They were recomputed from the stored counts (0 wrong of 1,221 / 1,221 / 1,191) and now hold [0.0, 0.003] / [0.0, 0.003] / [0.0, 0.0031]. Found by the P11-11 agent.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q tests/test_e2q_key_writer.py experiments/2026-11-19-p11-09-emg-trust/test_p11_09.py` |
| Full run (detached; about 2.3 h CPU) | `.venv\Scripts\python.exe experiments/2026-11-19-p11-09-emg-trust/launch.py` (stages `infer` with the torch venv, then `all`; needs the P11-01 feature cache, splits and personal weights) |
| Cards | `.venv\Scripts\python.exe -I experiments/2026-11-19-p11-09-emg-trust/run.py cards`, then `python -m fidetype.benchmark leaderboard --results benchmark/results/v0.1 benchmark/results/v0.2 --out benchmark/site` |

## Limits
- 8 users, one track-test session each; the CI unit is the user (8 clusters).
- Whole-prompt exact match on keystroke sequences that contain the user's own errors is a hard target. The protocol is right for the track; it is not the only useful commit unit (gap 103).
- The replay covers 240 of 1,221 test prompts. The pytest suite did not run during the replay, but other agents' jobs may have shared the CPU.
- No LM and no lexicon (by design; P11-07 is the LM item).
