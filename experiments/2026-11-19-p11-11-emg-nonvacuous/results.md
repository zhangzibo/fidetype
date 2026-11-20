---
title: P11-11 non-vacuous certified safe WPM for the P11-01 emg2qwerty EMG decoder - results
type: experiment
task: P11-11
updated: 2026-11-19
---

# P11-11: a non-vacuous certified EMG safe WPM (results)

Pre-registration: [plan.md](plan.md) (commit `b412c76`, before any evaluation decision) and amendment 1 (`5f54a45`, with the code: out-of-lexicon gate, found on calibration prompts only). Aggregates: [results/results.json](results/results.json), guard sheets `results/guard-{X,K}.json`, log `results/run.log`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page and the committed files hold pooled aggregates only: no per-user value, no text, no id. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-prompt files: `C:\Users\zhang\bci-data\derived\p11-11\` only.

Run: 2026-11-19 18:30-18:56, CPU only (isolation runner, class `background`, 4 threads), detached. No GPU.

## Outcome
**The word-prefix arm X gives the first non-vacuous certified EMG safe WPM: 4.23 [2.60, 6.34] under the proposed v0.2 (420 commits, 35 wrong = 2.9 % of 1,221 test prompts, CP95 [2.0 %, 4.0 %]). This is above the no-BCI reference of the same target (3.09) and above the P11-09 reference (2.93), but not clearly above (the CI includes both). With the reading cost it is 4.03. Two limits: (1) the primary sentence-level arms S and SL were refused, because the guard commits on time-shuffled EMG (19 and 20 of 300; allowed 15); (2) arm X fails the evaluation null control (time-shuffled EMG: 76 / 1,221 = 6.2 % commits, above 5 %). The adopted v0.1 value stays near zero (X complete-only: 0.07). The raw-key track arm K stays vacuous (0 commits).**

## Verdicts (pre-registered)
| Id | Arm S (primary) | Arm SL | Arm X (prefix, v0.2) | Arm K (track keys) |
|---|---|---|---|---|
| **V1 guard** | **refused** (input-level time-shuffled control 19 / 300, allowed 15) | refused (20 / 300) | **certified** (`tcfg-40d579c2cedf3a83`; uniform 0, frame-shuffled 7, input-level 14 of 300) | certified (`tcfg-b138896e0b137793`; 0 / 0 / 0) |
| **V2 safety** | no guard | no guard | **holds**: 35 / 1,221 = 0.029, CP95 [0.020, 0.040] | holds: 0 / 1,221 |
| **V3 value** | no guard | no guard | **non-vacuous**: v0.2 4.23 [2.60, 6.34], `certified` | vacuous (0 commits) |
| **V4 vs no-BCI** | - | - | **above** (3.09 on the intended texts; 2.93 on the raw keys), not clearly above | below |
| **V6 controls** | - | - | **fail**: time-shuffled EMG commits 76 / 1,221 = 6.2 % > 5 %; zero EMG 0 / 1,221 | pass (0 / 0) |

Hypotheses: **H1** (S certified, safe, non-vacuous) **not supported**: S was refused. **H2** (S above no-BCI) not testable. **H3** (X v0.2 > S v0.1): X 4.23 vs S no value; X is the only valued arm. **H4** (K vacuous or nearly) **supported**: 0 commits; top-1 raw keys exactly right on 0.8 %.

**Gap rule.** The plan closes gap 102 if S gives a certified, non-vacuous v0.1 value with V6 pass, *or* (fallback) X gives a certified, non-vacuous proposed-v0.2 value. The fallback path holds, so gap 102 closes. V6 fails for X, and the sentence-level v0.1 path failed: both go to the new gap 104 (P11-12).

## Main numbers (1,221 track-test prompts of the 8 users; 4,985 intended words; 119.8 min neural time)
| Measure | Arm X | Arm K |
|---|---|---|
| Safe WPM, proposed v0.2 (plain) | **4.23 [2.60, 6.34]**, certified | 0.00, vacuous |
| Proposed v0.2 + reading cost (0.5 s + 0.3 s / word per commit) | 4.03 [2.51, 5.91] | 0.00 |
| Adopted v0.1 (X: complete commits only, prefix commits = no commit) | 0.07 [0.00, 0.17] (2 complete commits, 0 wrong) | 0.00 |
| No-BCI reference (gaze, 20 chars/min, same trials and target) | 3.09 (intended text) | 2.93 (raw keys) |
| Commits (prefix / complete) | 420 (418 / 2) | 0 |
| Right words committed | 527 | 0 |
| Wrong commits, rate, CP95 | 35, 0.029, [0.020, 0.040] | 0, 0, [0, 0.003] |
| Error among commits | 0.083 | - |
| Commit / offer / withhold | 420 / 592 / 209 | 0 / 1,013 / 208 |
| Top-1 exactly right (whole prompt) | 24.5 % (intended text) | 0.8 % (raw keys) |
| Correction time | 4.7 min | 0 |
| Offline decision time per prompt (beam + LM + guard) | p50 172 ms, p95 402 ms | p50 22 ms, p95 51 ms (cached beam) |

Decoder side:
| Item | Value |
|---|---|
| Tuned `(w, c)` (first 765 calibration prompts only) | LM weight 0.5, OOV penalty 4; top-1 intended text exact 21.6 % on the tuning part (no LM: 6.3 %) |
| LM | Tatoeba 6-gram MKN rebuilt without the 16 sessions' texts: 1,445 more sentences removed; held-out perplexity 3.158 |
| Lexicon | 16,875 words (typed at least twice in the 927 track-train sessions); covers 95.3 % of the test truth words |
| Prompts with a Backspace (test) | 32.5 % |
| Unit lists | equal to the P11-09 calibration and evaluation digests |

> **Our take:** two levers did the work. The intended-text target with the LM / lexicon raises the whole-prompt top-1 rate from 0.16 % (P11-09, raw keys) to 24.5 %. Word-prefix commits then turn the frequent "first word right" cases into credit: 418 of 420 commits are prefixes, about 1.4 right words per right commit. A whole-prompt commit (v0.1) is still rare, because the guard rarely trusts all 4 words at once.

## Why S and SL were refused, and why X fails V6
Post-hoc diagnosis on **calibration** windows only (the 300 null windows of the guard; no test window): on time-shuffled EMG the decoder emits almost no Space key, so 245 of the 246 non-gated null outputs are **one word**. The LM and the lexicon then turn the noise into a common, in-lexicon word with a high n-best probability (raw top-1 probability >= 0.8 on 99 of 300). Real prompts have 3 to 8 words. So the confidence score sees a "certain" short text on no-signal input. The OOV gate (amendment 1) stops nonsense strings, but not a single real word. The prefix guard X passed its calibration control at 14 / 300 (allowed 15), and the evaluation control showed 6.2 %.

> **Our take:** a no-signal detector that does not depend on the language side should fix this: for example a minimum number of words, or a rate check (decoded words per second of EMG against the user's calibration range), or an acoustic-only evidence score in the commit gate. That is a new item (gap 104, P11-12), because the plan fixed the decoder and the gate.

## Checks
| Check | Result |
|---|---|
| Track splits (our first / second test session = track val / test) | 8 / 8 users (`check_track_splits`) |
| Calibration and evaluation unit digests = P11-09 | yes |
| Decoder choices from the non-certify part only | yes: `(w, c)` on the first 765 of calibrate's order (digest `96f175801d6ff225`) |
| LM leak guard | rebuilt LM without the 16 sessions' intended texts (exact and containment) |
| Window cache | n-best of 5,066 distinct windows computed once; the guards read it (the 600 automatic control windows per arm are decoded live) |

## Deviations and fixes (stated honestly)
1. **Amendment 1** (before any evaluation decision): out-of-lexicon gate in the decoder of all arms, because the smoke arm X committed on uniform input; and an indexed form of the LM blocklist rule (same result, tested).
2. **Reporting fix after the run:** the script's own CP95 of the wrong-commit rate called `clopper_pearson(k, n, 0.05)` (level 5 % instead of 95 %). `score` was rerun on the same, unchanged decisions; only the `wrong_commit_cp95` fields changed (X: [0.020, 0.040], equal to the safe-WPM block). The same call is in the P11-09 runner; there it changes nothing reported (0 wrong commits; the P11-09 page quotes the scorer's interval).
3. No collector replay (plan, lever L4): the decision time grows with the LM rescoring (p95 402 ms offline), so the 50 ms budget (gap 37) is further away.

## Benchmark entry
None. Arms S, SL and X change the target (intended text), so they are not track entries. The track-conformant arm K is vacuous; the P11-09 cards already state the vacuous track result (plan rule).

## New gaps
| Gap | Item | What |
|---|---|---|
| 104 | P11-12 | No-signal detector for the EMG intended-text guard: time-shuffled EMG decodes to one confident real word, so the sentence-level arms are refused (19-20 / 300) and the prefix arm commits on 6.2 % of null test inputs. Done when a pre-registered gate makes S pass all controls and X's evaluation null-commit rate <= 5 %, with the v0.1 and v0.2 values on the same split |

The latency limit stays with gap 37 (P3-06). The emg2qwerty LM itself (P11-07, gap 87) is still open: this item used n-best rescoring, not an LM inside the beam, and reports no CER.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-19-p11-11-emg-nonvacuous/test_p11_11.py` |
| Full run (detached; about 30 min CPU after P11-09) | `.venv\Scripts\python.exe experiments/2026-11-19-p11-11-emg-nonvacuous/launch.py` (needs the P11-09 `prompts.json` and `lp\`, the P11-01 label cache, the Tatoeba export) |

## Limits
- 8 users, one track-test session each; the CI unit is the user (8 clusters), so the CI is wide.
- The target is the intended text after Backspace, not the track's raw keys. The time is still the measured typing time with the user's own errors.
- The value uses the **proposed** v0.2 (not adopted); the adopted v0.1 value is 0.07.
- The lexicon comes from CC BY-NC-SA data (research only); the LM text is Tatoeba (CC BY 2.0 FR).
- The guarantee assumes exchangeable val / test sessions of the same users.
