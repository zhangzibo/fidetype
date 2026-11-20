---
title: P11-07 character LM inside the CTC beam for the emg2qwerty EMG decoder - results
type: experiment
task: P11-07
updated: 2026-11-19
---

# P11-07: a character LM inside the CTC beam for the P11-01 EMG decoder (results)

Pre-registration: [plan.md](plan.md) (commit `d168c51`, before any test decode), code `9e12a97`, amendment 1 `27f6d08` (before any latency result). Aggregates: [results/results.json](results/results.json), guard sheets `results/guard-{S,SL}.json`, log `results/run.log`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page and the committed files hold pooled and over-user aggregates only: no per-user value, no text, no id. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-session and per-prompt files: `C:\Users\zhang\bci-data\derived\p11-07\` only. The P11-01, P11-09, P11-11 and P11-12 files were read only.

Run: 2026-11-19 21:41-22:27 (CPU, detached, 6 single-thread workers, isolation class `background`; latency stage in class `timing`). GPU: one short stage (model chunk timing, 21:44).

## Outcome
**The in-beam LM lowers the test CER of the P11-01 personalised decoders from 14.66 % (greedy) to 10.10 % (mean over 8 users, beam 8), for 8 of 8 users. This is below the published fine-tuned no-LM value (11.28 %) and above the published LM value (6.95 %). A wider beam helps further (beam 64: 9.13 %). The intended-text CER falls from 15.16 % to 9.75 %. But the 50 ms CPU decision budget is not met at any beam width (p95 61-70 ms added, plus 47 ms for the CPU model chunk), and the certified safe WPM goes down with the new decoder (arm S 3.37 vs 4.10 in P11-12).**

## Verdicts (pre-registered)
| Id | Statement | Result | Verdict |
|---|---|---|---|
| **H1 (primary)** | F CER < greedy, for >= 7 of 8 users | 10.10 % vs 14.66 %; **8 of 8** users | **pass** |
| H2 | F <= 11.28 % (published fine-tuned no-LM) | 10.10 % | **pass** |
| H3 | Lexicon term helps (FL < F) | FL 10.88 % > F 10.10 %; FL < F for 2 of 8 users | **fail** |
| H4 | Intended-text CER improves | 9.75 % vs 15.16 % (pooled, per prompt) | **pass** |
| **H5 (gap 37)** | Bounded in-beam LM meets 50 ms on CPU | beam 8: 67.6 + 47.1 = 114.7 ms p95 | **fail** (every beam 4-64) |
| H6 | Arm S stays certified with the new decoder | certified, safe, non-vacuous, V6 pass; 3.37 [1.92, 5.18] | **pass** (value lower than 4.10) |
| C0 | Greedy reproduces P11-01 within 0.1 points | as written: 14.66 % vs 15.09 % (fails, see below); on the P11-01 session set: **15.0898 %** | **pass** on the right set |
| C1 | Time-shuffled key CER >= 0.90 | 0.985 | **pass** |

**C0, stated honestly.** The plan compared greedy on the 8 track-test sessions with the P11-01 value. But P11-01 scored **16** sessions (the last two of each user: track val + track test; 71,476 keys). On those 16 sessions our greedy decode of the P11-09 CPU log-probs gives 15.0898 % mean over users and 15.146 % pooled, equal to P11-01 to 4 digits. So the log-probs and the scorer reproduce P11-01. The plan's reference was for the wrong session set. All decoders here are compared on the same 8 track-test sessions (greedy 14.66 %).

## Tuning (765 track-val tuning prompts; digest `96f175801d6ff225`)
| Item | Value |
|---|---|
| Grid (beam 32, prune -8) | w {0.25, 0.5, 0.75, 1, 1.5} x beta {0, 0.5, 1, 2, 3} x lam {0, 1, 2, 4, 8}: 125 configs |
| Prompt CER on the tuning set: greedy / beam no LM | 18.80 % / 18.62 % |
| **F** (lam 0) | w 0.5, beta 1: 14.26 % |
| FL (lam > 0) | w 0.25, beta 1, lam 8: 13.72 % (lam at the grid edge) |
| Beam sweep (F) | B 4 / 8 / 16 / 32 / 64: 14.73 / 14.36 / 14.27 / 14.26 / 14.41 % |
| **Chosen beam** (smallest within 0.2 points of B 64) | **8** |

## Main numbers (8 track-test sessions, one per user)
### Session CER, raw keys (98 tokens; the P11-01 / paper form)
| Decoder | Mean over users | SD (n-1) | Pooled | Hyp / ref length |
|---|---|---|---|---|
| G greedy (no LM) | 14.66 % | 5.76 | 14.72 % | 0.990 |
| B0 beam 8, no LM | 14.58 % | 5.70 | 14.64 % | 0.991 |
| **F beam 8 + LM** | **10.10 %** | 5.00 | 10.17 % | 0.990 |
| FL beam 8 + LM + lexicon | 10.88 % | 6.03 | 10.96 % | 0.997 |
| F beam 4 / 16 / 32 / 64 | 11.17 / 9.59 / 9.29 / **9.13 %** | 5.44 / 4.89 / 4.75 / 4.69 | 11.24 / 9.65 / 9.35 / 9.19 % | - |
| Published fine-tuned, no LM / 6-gram LM (Table 3) | 11.28 % / 6.95 % | 4.45 / 3.61 | - | - |

The published conditions differ (users, splits, 100 ms lookahead, 33 bins, WikiText LM): see the [P11-01 comparison](../2026-11-16-p11-01-emg-decoder/results.md#comparison-with-the-published-baselines). Our LM gain (greedy to F: 4.56 points at beam 8, 5.53 at beam 64) is about the published gain (4.33 points).

### Intended text (`registry.keycodes_to_intended_text`)
| Decoder | Per prompt from the session decode: intended CER, pooled (mean over users) | Same pieces, raw key-code CER, pooled |
|---|---|---|
| G | 15.16 % (15.18 %) | 17.98 % |
| B0 | 15.09 % | 17.85 % |
| **F** | **9.75 %** (9.77 %) | 11.52 % |
| FL | 10.79 % | 13.29 % |
| F beam 64 | 8.60 % | 10.01 % |

| Each evaluation window decoded alone (33-class key form, the guard's view) | Intended CER, pooled | Key CER, pooled | Top-1 intended text exact |
|---|---|---|---|
| B0 | 14.96 % | 17.82 % | 6.3 % |
| **F** | **8.59 %** | 13.57 % | **34.2 %** |
| FL | 9.00 % | 13.43 % | 32.7 % |
| P11-11 decoder (no-LM beam 64 + LM / lexicon rescoring; P11-12 post-hoc) | 26.3 % | - | 24.5 % |

### Latency (1,221 evaluation windows, 1 thread, chunk 4 frames = 40 ms)
| Config | Offline whole window p50 / p95 | Per-chunk `push` p50 / p95 / max | **Added at window end** p50 / p95 |
|---|---|---|---|
| F beam 4 | 21.2 / 38.0 ms | 0.11 / 0.30 / 16.9 ms | 28.3 / 61.4 ms |
| **F beam 8** | 23.8 / 41.8 ms | 0.12 / 0.33 / 27.9 ms | 29.6 / **67.6 ms** |
| F beam 16 / 32 / 64 | 26.8 / 46.1; 31.3 / 51.2; 45.7 / 72.3 ms | p95 0.37 / 0.45 / 0.64 ms | p95 67.2 / 66.0 / 67.9 ms |
| FL beam 4 / 8 / 16 / 32 / 64 | p95 36.9 / 39.8 / 42.3 / 53.1 / 78.2 ms | p95 0.30-0.69 ms | p95 66.2 / 67.2 / 62.3 / 64.9 / 70.0 ms |
| P11-11 (LM rescoring after the beam, with guard) | p95 402 ms | - | - |

"Added at window end" = the last chunk's `push` + n-best + intended merge + OOV gate + no-signal gate + `guard.decide` (arm S guard) on the ready n-best.

| Acoustic model, one 4-frame chunk with its receptive field (121 frames) | p50 | p95 | max |
|---|---|---|---|
| GPU, torch ROCm, RX 7800 XT (500 chunks) | 3.2 ms | 4.2 ms | 4.9 ms |
| **CPU, NumPy CRT, 4 threads, class `timing`** (500 chunks; amendment 1) | 21.0 ms | **47.1 ms** | 100.7 ms |
| CPU, torch ROCm build, 4 threads (30 chunks; BLAS-bound, not representative) | 2,592 ms | 3,004 ms | 3,044 ms |

**H5 rule:** added p95 + CPU model p95 <= 50 ms. Beam 8: 67.6 + 47.1 = 114.7 ms. Every beam: 108-117 ms. **Fail.**

> **Our take:** the beam itself is cheap in streaming form: a 40 ms chunk costs at most 0.7 ms p95, and the added time at the window end hardly depends on the beam width (61-70 ms p95 for beams 4 to 64). So the LM inside the beam is not what breaks the budget. The end cost is mostly the per-window work after the beam (n-best to intended texts, the two gates and `guard.decide`; P11-12 measured about 40 ms p95 for the guard with a cached beam). The second cost is the CPU acoustic model (47 ms p95 per chunk with NumPy); on the GPU it is 4 ms. With the model on the GPU, the remaining gap is the guard's end-of-window work. This is evidence for gap 37, not a collector replay.

### Secondary: P11-12 arm S / SL safe WPM with the new decoder
Same gate (`gate.json`: k_min 15, r_min 1.842, r_max 17.276), same calibration (1,224 track-val prompts, LTT, alpha 0.05, delta 0.1, seed 0, the same 300 time-shuffled null windows), same controls. Decoder: gate -> FL beam 8 -> intended merge -> P11-11 OOV gate.

| Measure | Arm S (p_top1) | Arm SL (learned) | P11-12 S / SL |
|---|---|---|---|
| Guard | certified `tcfg-60a1ffc45809f11f` (threshold 0.70) | certified `tcfg-2314f933bc13ce43` (learned >= 0.80) | `tcfg-3875f995e4c256fb` / `tcfg-0cd6e9578e965f42` |
| Calibrate controls (uniform / frame-shuffled / input-level, of 300) | 0 / 2 / 0 | pass (all <= 15) | S 0 / 1 / 0 |
| **Safe WPM v0.1** | **3.37 [1.92, 5.18]**, certified | 3.16 [1.79, 4.84], certified | 4.10 [1.99, 6.60] / 5.08 [2.67, 7.96] |
| Proposed v0.2 + reading cost | 3.26 [1.88, 4.96] | 3.06 [1.76, 4.65] | 3.95 / 4.88 |
| No-BCI reference (intended text) | 3.09 | 3.09 | 3.09 |
| Commits / wrong | 154 / 43 | 135 / 34 | 167 / 35; 194 / 31 |
| Wrong-commit rate, CP95 | 0.035 [0.026, 0.047] | 0.028 [0.019, 0.039] | 0.029; 0.025 |
| Error among commits | 0.279 | 0.252 | 0.210; 0.160 |
| Top-1 intended exact (gated) | 32.4 % | 32.4 % | 24.0 % |
| Test controls: time-shuffled / zero EMG commits | 0 / 0 of 1,221 | 0 / 0 | 0 / 0 |
| Real windows gated | 2.2 % | 2.2 % | 2.2 % |
| Offline decision time (decode memoised) p50 / p95 | 58 / 106 ms | 29 / 63 ms | 20 / 40 ms |
| Verdicts V1-V6 | certified, holds, non-vacuous, above (not clearly), pass | same | same |

Always-commit reference (gated top-1, no bound): 396 right of 1,221, unguarded WPM 3.72 (P11-12: 293 right, 2.49).

> **Our take:** the new decoder gets more prompts exactly right (top-1 32.4 % vs 24.0 %), but its confidence separates right from wrong less well. The in-beam LM makes the n-best list narrower and more confident on wrong texts too, so the guard commits fewer prompts and more of them are wrong. The certified value goes down (S 3.37 vs 4.10, SL 3.16 vs 5.08). A better accuracy does not give a better guarded value by itself; the confidence needs its own work (new gap 122).

## Benchmark entry
No new card (plan rule): neither arm is above the best `intended_text` entry (5.08, P11-12 SL).

## Deviations (stated honestly)
1. **Amendment 1** (before any latency result): the ROCm torch CPU build runs matrix products without a fast BLAS (`aten::mm` 78 ms per call), so the CPU model chunk was timed with the committed NumPy CRT (same maths; check vs torch: max probability difference 4.2e-7, argmax agreement 1.0). The torch-CPU numbers are reported as is.
2. **C0 reference**: the plan used the P11-01 value from 16 sessions as the reference for 8 sessions (see Verdicts). Added after the run: the same greedy check on the 16 P11-01 sessions (greedy only, no tuned decoder on the track-val sessions beyond the tuning part). The as-written verdict stays "fail" in `results.json`.
3. The first `modellat` run was stopped after 9.5 min (the torch-CPU part ran for minutes, which led to amendment 1). A NumPy stage under the isolation runner waited on its own timing lock and was stopped; it was re-run directly (the stage takes the timing class in-process).
4. The isolation record of the latency and NumPy stages is empty (`iso.record` was read inside the context). The stages ran in class `timing` (pinned cores 8, 10, 12, 14); other agents' CPU jobs ran on the background cores at the same time.
5. FL's `lam` was chosen at the edge of the grid (8). A larger value was not tested (plan rule).

## Gap rule
- **Gap 87 closes:** the test CER (mean over 8 users) of the in-beam LM decoder is reported against the Table 3 LM column, with C1 and the reproduction check, under the plan.
- **Gap 37 stays open** with the H5 numbers (fail on CPU at every beam).

## New gaps
| Gap | Item | What |
|---|---|---|
| 121 | P3-12 | Guard end-of-window cost and CPU acoustic model inside the 50 ms budget: the in-beam beam costs < 1 ms per chunk, but the end-of-window work (n-best, gates, `guard.decide`) is 61-70 ms p95 and the NumPy model chunk 47 ms p95. Done when a profiled, incremental guard decision plus a faster CPU model (or the GPU path) gives p95 <= 50 ms on the same windows |
| 122 | P11-14 | Guard confidence for the in-beam LM decoder: better top-1 (32.4 % vs 24.0 %) but lower certified safe WPM (S 3.37 vs 4.10). Done when a pre-registered confidence (for example an LM-weight temperature, acoustic-only features, or a learned score with beam features) gives a certified value at least the P11-12 value with the same controls |

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-20-p11-07-emg-beam-lm/test_p11_07.py` |
| Full run (detached; about 45 min CPU) | `.venv\Scripts\python.exe experiments/2026-11-20-p11-07-emg-beam-lm/launch.py` (needs `derived\p11-09\` prompts and `lp\`, `derived\p11-11\` LM and lexicon, `derived\p11-12\gate.json`, the P11-01 label cache) |
| GPU / CPU model chunk | `C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-20-p11-07-emg-beam-lm/run.py modellat`, then (OMP_NUM_THREADS=4) `.venv\Scripts\python.exe -I experiments/2026-11-20-p11-07-emg-beam-lm/run.py modellat_np` (not under the isolation runner) |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-07\DONE` exists; stop the python processes whose command line has `p11-07-emg-beam-lm` |

## Limits
- 8 users, one track-test session each; CIs of the safe WPM use the user as the cluster unit, so they are wide.
- The LM is Tatoeba English (CC BY 2.0 FR), short everyday sentences; the lexicon term uses research-only words from the track-train sessions.
- Latency is an offline component measurement on one machine (no collector replay, no end-to-end stream).
- The time-shuffled control uses the 33-class key form (the 98-token shuffled log-probs do not exist on disk).
