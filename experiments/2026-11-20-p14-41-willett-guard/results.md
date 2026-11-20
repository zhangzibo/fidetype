---
title: P14-41 trust guard for willett-hw - results
type: experiment
task: P14-41
updated: 2026-11-20
---

# P14-41: trust guard for `willett-hw` (results)

Pre-registration: [plan.md](plan.md) (commit `4565cc1`, before any real-data guard result). Code: [run.py](run.py), [launch.py](launch.py). Numbers: [results/results.json](results/results.json); log: [results/run.log](results/run.log). Per-sentence records (decisions, decoded text, truth), the log-probs and the guard file stay in `C:\Users\zhang\bci-data\derived\p14-41\` only. CPU only (isolation class `background`, 4 threads, detached, keep-awake). Run 2026-11-20 03:29-04:51.

## Summary
| Verdict | Result |
|---|---|
| **V1 guard** | **returned, not certified**: LTT `feasible: false` (40 LTT items < 45 needed), commit threshold = never. As pre-stated in plan section 5 |
| **V2 safety** | holds: 0 wrong commits / 80 test sentences (CP95 [0, 0.0451]) |
| **V3 value** | **vacuous**: 0 commits, safe WPM v0.1 = **0.00** (no-BCI gaze reference 4.05) |
| **V6 controls** | **pass**: calibrate controls 0 / 300 (uniform), 0 / 300 (frame-shuffled), 0 / 106 (time-shuffled input); test time-shuffled 0 / 80, zero 0 / 80 commits |
| V7 offers | 77 offers, 3 withholds of 80 test sentences; offered top-1 exact 0 / 80, CER 0.2967 |
| Gap 121 | **closed** by the pre-registered rule (plan section 7: guard returned and V6 pass -> package as an offer-only release file) |

The guard is honest but useless for typing: it never commits. This was known before the run from the method: 106 val sentences are too few to certify any commit at alpha 0.05, delta 0.1, and the greedy decoder gets only 0-1 test sentences exactly right.

## 1. Memory fix (the cause of the P14-33 stop)
| Item | Before | After |
|---|---|---|
| Cause 1 | The CTC prefix beam search (loop) kept `lm_score` and `_last_id` for every prefix it ever made. On flat frames (near-uniform control) every token passes `prune_logp = -6`, so memory grows with T^2 | The caches are cut to the current beam when they pass 4,096 entries (`PREFIX_CACHE_MAX`); exact |
| Cause 2 | `ctc_forced_align_many` built an emit array (T, S) float64 for all n-best texts at once | Frame-by-frame scores, groups of at most 2^26 back-pointer cells, `None` at once when a text has more labels than frames; exact |
| Synthetic probe (25 sentences, uniform control) | 17.9 GB after under 50 s (stopped by us) | - |
| Synthetic, one near-uniform decision | T = 2,000: > 2.5 GB (stopped) | T = 2,000: 145 MB peak, 5 s; T = 5,000: 200 MB, 21 s |
| This run (real data, all stages) | P14-33: stopped for low machine memory | **peak working set 1,194 MB** (limit 6,000 MB, not reached) |

Code: `src/fidetype/lm/beam.py` (commit `4565cc1`). Tests: `tests/test_trust_incremental.py::test_prefix_cache_pruning_is_exact` (with and without an LM, flat and peaked frames, chunked pushes, `partial`, `end_candidates`), `::test_forced_align_many_groups_equal_one_pass`. Targeted runs: `test_trust_incremental.py` + `test_lm.py` 62 passed; `test_trust_dropin.py` + `test_pretrained.py` 39 passed. A scratch check against the old code gave equal n-best texts, scores, spans and confidences on 12 random inputs. The method did not change.

## 2. Data and split
| Item | Value |
|---|---|
| Calibration | the **106 val sentences** (one val block per session, P15-08 salted hash), 436,356 frames |
| Report | the **80 test sentences** (last block of each session), 335,829 frames (55.97 min neural time) |
| Split equal to `derived/p15-08/willett/splits.json` | yes |
| Training pool | not used |

## 3. Guard
| Item | Value |
|---|---|
| Call | `fidetype.trust.calibrate`, alpha 0.05, delta 0.1, built-in CTC prefix beam 16 (no LM, no lexicon), seed 0, `null_inputs` = decoder on the time-shuffled input of the 106 val sentences (the same call as the P14-33 guard stage) |
| config_id | `tcfg-39aac48688b8bd12` |
| Split inside calibrate | 26 fit + 40 policy grid + 40 LTT |
| LTT | lambda_hat inf, `feasible: false`; in-sample LTT 0 commits, 0 wrong (median guard risk 0.250) |
| Frame temperature | 1.4945 (fitted on the val texts) |
| Warnings on the sheet | "only 40 LTT items (< 45): no threshold can be certified, so the guard never commits"; "the guard never commits" |
| Time | lp stage 722 s; calibrate 3,187 s; test decisions 983 s (the uniform input took 852 s of it) |
| Guard file | `willett-hw.guard.json`, 6,751 bytes, SHA-256 `b16963ed5d2ba09ed0525fc8193b8b8a0a1d0ec7814faf12ee8b6174e93c33fc`; holds no truth text (`audit_text=False`; checked) |

## 4. Test decisions (80 sentences per input)
| Input | Commit | Wrong commit | Offer | Withhold |
|---|---|---|---|---|
| real | 0 | 0 | 77 | 3 |
| time-shuffled input (decoder on shuffled bins) | 0 | 0 | 4 | 76 |
| zero input | 0 | 0 | 0 | 80 |
| frame-shuffled decoder frames | 0 | 0 | **77** | 3 |
| near-uniform frames | 0 | 0 | 0 | 80 |

Safe WPM v0.1 (`fidetype.benchmark.safe_wpm`, guarantee and controls from the sheet, neural time = 10 ms bins of the sentence window, no CI: one participant): **0.00, status `vacuous`**, unguarded 0.00, no-BCI 4.05.

> **Our take:** the commit side is safe and the null controls work. The offer side does not depend on the signal order: the guard offers on 77 / 80 frame-shuffled inputs, as often as on real input, and the offered top-1 is never exact. The drop-in null controls count only commits, so they cannot see this. For an offer-only guard this matters: an offer list of a weak decoder is not evidence that the neural signal was read. New gap 136 (P5-31).

> **Our take:** a `willett-hw` guard that can commit needs about 120 or more calibration sentences (45 LTT items) and a decoder that gets a real share of sentences exactly right, for example with a word LM (gap 26 = P14-12) or a stronger decoder (gap 120 = P15-33). The val blocks have only 106 sentences, so a guard on this split will stay offer-only even with a better decoder, unless the split changes.

## 5. Packaging
- Release file (as `kt-semg-lda`): `C:\Users\zhang\bci-data\pretrained\willett-hw\willett-hw.guard.json`, local only, not in git, not hosted (gap 98).
- `src/fidetype/pretrained/manifests/willett-hw.json`: `guard` file row (SHA-256, size), `trust.config = "file:willett-hw.guard.json"`, `commits: never`, the null-control numbers, and a `trust_note` with the limits.
- Check: `load("willett-hw").guard()` loads `tcfg-39aac48688b8bd12`; its decisions equal the run on the first 10 test sentences (10 / 10). `tests/test_pretrained.py` 19 passed.
- `docs/pretrained-decoders.md`: table row and trust-guard section updated.

## 6. Limits
- One participant (T5), one decoder checkpoint, one calibration draw. No CI.
- The guard is offer-only by construction (40 < 45 LTT items). The V2 "holds" verdict is trivial: there are no commits.
- The vector search path of the beam (`search="vector"`, not used here) and the LM row caches still grow with the number of beam prefixes over T. They are smaller than the fixed loop caches but not bounded: new gap 137 (P5-32).

## Rerun
| Step | Command (repo root) |
|---|---|
| All stages, detached | `.venv\Scripts\python.exe experiments/2026-11-20-p14-41-willett-guard/launch.py` (DONE file `C:\Users\zhang\bci-data\derived\p14-41\DONE`) |
| One stage, in the foreground | `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-20-p14-41-willett-guard/run.py score` |
