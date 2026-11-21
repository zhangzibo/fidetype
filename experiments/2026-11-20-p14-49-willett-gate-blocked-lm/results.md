---
title: P14-49 + P14-50 willett-hw no-signal gate for time-shuffled input, with the Willett-blocked LM - results
type: experiment
task: P14-49, P14-50
updated: 2026-11-21
---

# P14-49 + P14-50: a no-signal gate that stops time-shuffled input, on the Willett-blocked LM (results)

Pre-registration: [plan.md](plan.md) (commit `76747e8`, with the code: [run.py](run.py), [launch.py](launch.py), `src/fidetype/pretrained/lmreadout.py`, tests; before any val or test result). Numbers: [results/results.json](results/results.json); log: [results/run.log](results/run.log). Per-sentence records (text, truth, features, decisions) and the guard file stay in `C:\Users\zhang\bci-data\derived\p14-49\` only.

Run: 2026-11-20 23:52:19 - 23:59:13, detached, isolation class `background`, 4 threads, CPU only (no GPU). Stages: check 1 s, lmval 61 s, select 2 s, readout 47 s, guard 141 s, decide 150 s, score 12 s. Peak working set **1,565 MB** (limit 5,500 MB). No stop, no restart, no failure.

## Outcome
**Both items meet their done criterion.**
- **P14-50:** the `willett-hw` LM readout now uses the Willett-blocked LM (no test overlap). Test CER **0.1743** ungated (= P15-38, the same text on 80 / 80 sentences) and **0.1746** gated (greedy 0.3051).
- **P14-49:** the pre-registered selection on val chose **C5, a small logistic score** of five posterior features. On test it lets **2 / 80** time-shuffled, **0 / 80** zero and **0 / 80** uniform inputs emit text (limit 4 each), and it stops only **1 / 80** real inputs (limit 4). The P14-48 count gate on the same inputs: time-shuffled 13 / 80, real 3 / 80.
- N2 (frame-shuffled order control) passes: gated CER 0.881 >= 0.85.
- The re-calibrated guard is returned but **not certified** (40 LTT items < 45), as predicted: 0 commits, safe WPM v0.1 0.00 (vacuous). Commit controls pass. Offers on time-shuffled input fall from 13 / 80 (P14-48) to **2 / 80**; on frame-shuffled frames they stay at 77 / 80, as often as on real input.

## Done criteria (plan section 1)
| Item | Part | Result |
|---|---|---|
| P14-50 | B1 manifest LM = `eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz`, `text` row with SHA-256, local read-only file | **met**: SHA-256 `d7f6e829...059261`, 3,348,904 bytes, `C:\Users\zhang\bci-data\pretrained\text\` (read-only, checked) |
| P14-50 | B2 CER, null controls, guard re-measured | **met** (sections 1-2) |
| **Gap 146** | | **closes** |
| P14-49 | N1': time-shuffled, zero, uniform each <= 4 / 80 emit | **met**: 2, 0, 0 |
| P14-49 | H-cost: real gated <= 4 / 80 | **met**: 1 / 80 |
| **Gap 145** | | **closes** |
| Gap 144 (P14-48) | D1: packaged readout with a gate, N1 and N2 pass | **met now**: the packaged default gate passes N1' and N2. D2 (licence and overlap on the card) is re-stated for the new LM; D3 (guard numbers) is met again |

## 1. Gate selection (val only)
Gate set S = the 66 non-LTT val positions of calibrate's order (digest `5b1dfd323c7fc94f`, the P14-48 set). Inner split A = first 33, B = last 33 (A digest `146818fe5f5314ca`). Counts are summed over fit-A/count-B and fit-B/count-A (66 evaluations each).

| Candidate | G real gated | E_ts time-shuffled pass | E_zero | E_uni | frame-shuffled pass (reported) | Eligible |
|---|---|---|---|---|---|---|
| C0 count gate (P11-12 rule) | 1 | 4 | 0 | 0 | 66 | yes |
| C1 non-blank share | 1 | 4 | 0 | 0 | 65 | yes |
| C2 emission peak probability | 1 | 3 | 0 | 0 | 63 | yes |
| C3 entropy of non-blank frames | 3 | 3 | 0 | 0 | 63 | yes |
| C4 LM tokens per emission (two-sided) | 3 | 32 | 0 | 0 | 38 | yes |
| **C5 logistic score** | 2 | **0** | 0 | 0 | 64 | yes |

Rule: the eligible candidate with the smallest E_ts -> **C5**. Re-fitted on all 66: `lo` = -1.1697 (the smallest real score), `r_max` = 2.834 per s, `k_min` = 1; standardised coefficients (peak 1.77, neg_entropy 1.04, nb_share 1.25, kps 1.14, log(1 + n_keys) 0.92), intercept 0.544. Check on S (not used to choose): 0 / 66 real gated (by the rule), 0 / 66 time-shuffled pass.

Val features on S (min / median / max), descriptive:
| Input | n_keys | peak | neg_entropy | nb_share |
|---|---|---|---|---|
| real | 7 / 44 / 72 | 0.754 / 0.849 / 0.932 | -0.823 / -0.440 / -0.269 | 0.0049 / 0.0164 / 0.0228 |
| time-shuffled | 0 / 12 / 30 | 0 / 0.592 / 0.847 | -4.585 / -1.070 / -0.485 | 0 / 0.0032 / 0.0071 |

> **Our take:** prediction (b) holds in part. Each single confidence feature (peak, entropy) is a little better than the counts, but each one alone still overlaps the real tail. The logistic score joins weak evidence from all five features, and on val it separates the two classes fully. C4 (LM length per emission) is useless: the LM top-1 length follows the emission count closely for both classes.

## 2. Test (80 sentences, 3,448 characters), new LM
### Readout with the chosen gate (C5)
| Input | Gated | Emits text | Chars out (gated / raw) | CER gated | CER raw | CER greedy |
|---|---|---|---|---|---|---|
| real | 1 | 79 | 3,182 / 3,187 | **0.1746** | **0.1743** | 0.3051 |
| time-shuffled input | 78 | **2** | 39 / 731 | 0.994 | 0.858 | 0.867 |
| zero input | 80 | 0 | 0 / 87 | 1.000 | 0.982 | 1.000 |
| frame-shuffled frames | 1 | 79 | 3,973 / 3,978 | 0.881 | 0.881 | 1.021 |
| near-uniform frames | 80 | 0 | 0 / 335,829 | 1.000 | 97.2 | 94.4 |

Val (106, descriptive): ungated CER 0.1272, greedy 0.2603. Exact test sentences (gated): 10 / 80. Decode time per sentence (CPU): real p50 0.057 s, p95 0.094 s.

| Id | Rule | Result |
|---|---|---|
| **R0** | ungated CER within 0.005 of 0.1743 (P15-38) | **pass**: 0.1743 (difference 0.0000); same text as P15-38 on **80 / 80** |
| R1 | gated test CER | 0.1746 (P14-48: 0.1760 with the old LM and the count gate) |
| **H-cost** | real gated <= 4 / 80 | **pass**: 1 / 80 |
| **N1'** | emit <= 4 / 80 each | **pass**: uniform 0, time-shuffled 2, zero 0 |
| **N2** | frame-shuffled gated CER >= 0.85 | **pass**: 0.881 (79 / 80 emit) |
| ref | P14-48 count gate, new LM, same inputs | real gated 3, CER 0.1769; time-shuffled 13 / 80 emit (fail); zero 0, uniform 0; frame-shuffled CER 0.882 |

Test features (min / median / max): real peak 0.653 / 0.839 / 0.930, time-shuffled peak 0 / 0.610 / 0.808; real n_keys 4 / 39 / 92, time-shuffled 0 / 10 / 28.

Packaged path: `load("willett-hw")` with the manifest default gate gives the run's text and the run's guard action on the first 10 real and 10 time-shuffled test inputs (20 / 20 each).

> **Our take:** the gate does its job and costs almost nothing (0.0003 CER; 1 real sentence gated instead of 3). But the margin on test is small (2 of 4 allowed), and the fit used one draw of the time-shuffled input. A new participant, session or decoder needs a re-fit; the gate is part of this model, not a general rule. The gate still cannot see the frame order (frame-shuffled 79 / 80 pass); N2 passes only because F on shuffled frames gives bad text.

## 3. Guard re-calibrated on the new LM + gate C5
| Item | Value |
|---|---|
| Call | the P14-48 call; decode_fn = gate C5 + F (new LM, 8-best), `decoder_version="2"` |
| config_id | `tcfg-26ae951a20a0cddd` |
| Split inside calibrate | 26 fit + 40 policy grid + 40 LTT |
| LTT | lambda_hat inf, `feasible: false`, 0 LTT commits |
| Guard file | `willett-hw.lm2.guard.json`, 7,111 bytes, SHA-256 `97a6c219f0bc8ed6c4483b79ece4a10a128c270ff2e0b0c0574022a5434f144e`; no truth text (`audit_text=False`; checked: 0 val or test truths in the file) |
| Trust code | the committed `fidetype.trust` of `76747e8` (loaded before the parallel P5-31 edits of `dropin.py` at 23:56:20; the sheet has no offer-control field) |

| Verdict | Result |
|---|---|
| **V1 guard** | **returned, not certified** (40 LTT items < 45); commit threshold = never. As predicted |
| **V2 safety** | holds: 0 wrong commits / 80 (trivial: no commits) |
| **V3 value** | **vacuous**: 0 commits; safe WPM v0.1 **0.00** (no-BCI gaze reference 4.05) |
| **V6 controls** | **pass**: calibrate uniform 0 / 300, frame-shuffled 0 / 300, time-shuffled input 0 / 106 commits; test time-shuffled 0 / 80, zero 0 / 80 commits |
| V7 offers (real) | 77 offers, 3 withholds; offered top-1 exact **12 / 77**, CER 0.1724 |

### V8 offer rates on null input (gap 136, descriptive)
| Input (80 test) | Commit | Offer | Withhold | Offer rate | Flag "offer null passes" (<= 0.05) | P14-48 offer rate |
|---|---|---|---|---|---|---|
| real | 0 | 77 | 3 | 0.963 | - | 0.963 |
| time-shuffled input | 0 | 2 | 78 | **0.025** | **yes** | 0.163 |
| zero input | 0 | 0 | 80 | 0.000 | yes | 0.000 |
| frame-shuffled frames | 0 | 77 | 3 | **0.963** | no | 0.963 |
| near-uniform frames | 0 | 0 | 80 | 0.000 | yes | 0.000 |

> **Our take:** the gate fixes the time-shuffled offers too, because a gated input gives an empty n-best list and the guard withholds. The frame-shuffled offers are unchanged: neither the gate nor the guard reads the frame order. This stays gap 136 (P5-31). The 106-sentence val split still blocks a certified guard (gap 138 = P14-47).

## 4. Packaging (plan section 7: the gate passed)
- `src/fidetype/pretrained/lmreadout.py`: `posterior_features`, `ScoreGate` (fit rule, `to_dict` / `from_dict`), `gate_from_dict` (count or score kind), `LmReadout` support for a gate that reads the LM length. The P14-48 `NoSignalGate` stays (kind `count`).
- Manifest `willett-hw.json`: `text` row for the new LM (the old LM row is removed: the API reads only `readouts.lm.lm_file`, so the new LM is the only and default LM); `readouts.lm.gate` = gate C5 (`kind: score`, `feature: logit`) = the default gate of `m.lm_readout()` and `m.text(stream, readout="lm")`; new `guard` row and `readouts.lm.trust` for `willett-hw.lm2.guard.json` (the P14-48 guard row is removed: it was calibrated on the old LM); licence `text_files` note: local only, because the build blocklist holds research-only emg2qwerty texts; `test_overlap`: none; metrics, null controls, warning and the `limits` line updated.
- Local files (not in git): `C:\Users\zhang\bci-data\pretrained\text\eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz` (read-only copy), `C:\Users\zhang\bci-data\pretrained\willett-hw\willett-hw.lm2.guard.json`.
- Tests: `tests/test_pretrained_lmreadout.py` (new: features, score-gate fit rule and round trip for four features, the LM-length gate in the readout, gate kinds, the manifest default gate) + `tests/test_pretrained.py`: 32 passed.
- `docs/pretrained-decoders.md`: the new LM, the gate and the guard.

## 5. Checks
| Check | Result |
|---|---|
| Split equal to `derived/p15-08/willett/splits.json` | yes |
| Log-probs: the P14-48 files (read only; SHA-256 in `results.json`) | used unchanged |
| Manifest LM SHA-256 = file SHA-256 = P15-38 value | yes; the file is read-only |
| Gate fitted and chosen on the 66 non-LTT val positions only | yes; no test input and no LTT position used |
| Text in committed files | none |

## 6. Deviations
None from the plan. Note: in this run all six candidates were eligible, so the fallback rule was not used. Stage `guard_count` was not needed.

## 7. Limits
- One participant (T5), one checkpoint, one draw of each null input; no CI. The test margin of N1' is 2 of 4.
- The gate learns "real vs time-shuffled" for this decoder; other null types (for example a different person, or real neural data from another task) are not tested.
- The gate does not see the frame order.
- The guard is offer-only (106 val sentences).

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests (CPU, seconds) | `.venv\Scripts\python.exe -m pytest -q tests/test_pretrained_lmreadout.py` |
| All stages, detached (about 7 min CPU; needs `derived\p14-48\lp_*.npz`) | `.venv\Scripts\python.exe experiments/2026-11-20-p14-49-willett-gate-blocked-lm/launch.py` |
| Check / stop / resume | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p14-49\DONE` exists; stop: create `derived\p14-49\STOP`; resume: delete STOP and launch again (finished stages are skipped) |

## Licence
Willett data CC0 1.0. LM text CC BY 2.0 FR (Tatoeba contributors); the LM build blocklist holds research-only emg2qwerty texts (CC BY-NC-SA 4.0), so the LM file stays local. Our code Apache-2.0. This commit holds aggregates only: no weights, LM file, log-probs or text.
