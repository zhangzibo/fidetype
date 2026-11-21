---
title: P14-48 willett-hw with the same-LM readout and a no-signal gate - results
type: experiment
task: P14-48
updated: 2026-11-20
---

# P14-48: `willett-hw` with the same-LM readout and a no-signal gate (results)

Pre-registration: [plan.md](plan.md) (commit `59c32ea`, before any real-data result). Code: commit `f14b5b4` ([run.py](run.py), [launch.py](launch.py), `src/fidetype/pretrained/lmreadout.py`, `tests/test_pretrained_lmreadout.py`). Numbers: [results/results.json](results/results.json); log: [results/run.log](results/run.log). Per-sentence records (text, truth, decisions), log-probs and the guard file stay in `C:\Users\zhang\bci-data\derived\p14-48\` only.

Run: 2026-11-20 22:49:52 - 23:09:02, detached, isolation class `background`, 4 threads, CPU only (no GPU). Stages: lp 807 s, gate < 1 s, readout 60 s, guard 152 s, decide 126 s. Peak working set **1,307 MB** (limit 5,500 MB). No stop, no restart.

## Outcome
**The packaged LM readout works and reproduces P15-25 exactly, but the no-signal gate fails one null control. Gap 144 stays open.**
- `load("willett-hw")` on CPU with the LM readout: test CER **0.1734** without the gate (equal to P15-25; the same text on 80 / 80 sentences) and **0.1760** with the gate (greedy 0.3051).
- The gate stops all uniform and zero inputs. It stops only **67 / 80** time-shuffled test inputs: **13 / 80 emit text** (allowed 4). **N1 fails.**
- The frame-shuffled order control passes (gated CER 0.883 >= 0.85).
- The re-calibrated guard is returned but **not certified** (40 LTT items < 45), as predicted. It never commits; safe WPM v0.1 is 0.00 (vacuous). All commit controls pass. The offers do not depend on the signal order (frame-shuffled 77 / 80 offers, as real input).

## Done criterion (plan section 1)
| Part | Result |
|---|---|
| D1 readout with gate, N1 and N2 pass | readout packaged (opt-in), N2 pass, **N1 fails** (time-shuffled 13 / 80 > 4) -> **not met** |
| D2 card states the LM licence and the test overlap | **met** (manifest `licence.text_files`, `readouts.lm.licence`, `readouts.lm.test_overlap`, a `limits` line; docs) |
| D3 guard re-calibrated, numbers reported | **met** (not certified; numbers below) |
| **Gap 144** | **stays open** (D1) |

## 1. Readout and gate
Gate (P11-12 rule, fitted on the 66 non-LTT val sentences of calibrate's order, real input only; positions digest `5b1dfd323c7fc94f`): pass iff `n_keys >= 7` and `0.425 <= kps <= 2.834` per second.

| Fit check (66 val sentences) | Value |
|---|---|
| Real: n_keys min / median / max | 7 / 44 / 72 |
| Real: kps min / median / max | 0.425 / 1.067 / 1.417 |
| Real gated (by construction 0) | 0 |
| Time-shuffled: n_keys min / median / max | 0 / 12 / 30 |
| Time-shuffled: kps min / median / max | 0.000 / 0.308 / 0.588 |
| Time-shuffled that pass the gate (check, not used to choose) | **4 / 66** (6 %): an early warning of the N1 failure |

### Test (80 sentences, 3,448 characters)
| Input | Gated | Emits text (gated) | Chars out (gated / raw) | CER gated | CER raw | CER greedy | n_keys min / med / max | kps min / med / max |
|---|---|---|---|---|---|---|---|---|
| real | 3 | 77 | 3,174 / 3,190 | **0.1760** | **0.1734** | 0.3051 | 4 / 39 / 92 | 0.141 / 0.935 / 1.498 |
| time-shuffled input | 67 | **13** | 201 / 728 | 0.967 | 0.859 | 0.867 | 0 / 10 / 28 | 0.000 / 0.229 / 0.779 |
| zero input | 80 | 0 | 0 / 87 | 1.000 | 0.982 | 1.000 | 0 / 0 / 0 | 0 / 0 / 0 |
| frame-shuffled frames | 2 | 78 | 3,969 / 3,979 | 0.883 | 0.882 | 1.021 | 5 / 60.5 / 138 | 0.176 / 1.434 / 2.300 |
| near-uniform frames | 80 | 0 | 0 / 335,829 | 1.000 | 97.2 | 94.4 | 1,229 / 3,712 / 9,358 | 97.3 / 97.9 / 98.4 |

Val (106 sentences, descriptive): gated CER 0.1274 (0 gated), greedy 0.2603. Exact sentences: test 9 / 80 gated, val 14 / 106. Decode time per sentence (CPU, one thread of work): real p50 0.066 s, p95 0.106 s; uniform (ungated) p50 0.38 s.

| Id | Rule | Result |
|---|---|---|
| **R0** | ungated CER within 0.005 of 0.1734 | **pass**: 0.1734 (difference 0.0000); same text as P15-25 on **80 / 80** sentences |
| R1 | gated test CER | 0.1760 |
| R2 / H-cost | real test gated <= 4 / 80 | **pass**: 3 / 80 (short sentences of 4-9 characters: n_keys 4, 9, 4; two below k_min 7, one below r_min with kps 0.406) |
| **N1** | emit on <= 4 / 80 for uniform, time-shuffled, zero | uniform 0, zero 0: pass; **time-shuffled 13: FAIL** |
| **N2** | frame-shuffled gated CER >= 0.85 | **pass**: 0.883 (78 / 80 emit text) |

> **Our take:** the readout itself is right: the NumPy package gives exactly the P15-25 texts, and the gate costs only 0.003 CER. The failure is narrow but real. The decoder still emits some characters on time-shuffled neural input (median 10 emissions, up to 28), because shuffled threshold crossings keep some per-bin structure. The gate's lower bounds (7 emissions, 0.42 per second) come from the shortest real val sentences, so the time-shuffled tail overlaps them. The 13 texts are short (201 characters in all, CER 0.967), so they are not fluent false sentences; but by the pre-registered rule the readout emits text without a signal on 16 % of time-shuffled inputs. In P11-12 (EMG) the two classes did not overlap; for this decoder they do. A stronger feature (for example the share of non-blank frames, or an emission-rate test against the sentence length the LM proposes) would be a new, separately pre-registered item.

> **Our take:** N2 passes, but the gate plays no part in it: frame-shuffled frames keep the per-frame evidence, pass the count gate (78 / 80) and give text with CER 0.88. A count gate cannot see the frame order. Only the guard's offer side would need to see it (V8 below, gap 136).

## 2. Guard re-calibrated on the gated LM readout
| Item | Value |
|---|---|
| Call | `fidetype.trust.calibrate`, alpha 0.05, delta 0.1, seed 0, decode_fn = gate + F (8-best), `null_inputs` = time-shuffled val input, no `stream_texts` (frame temperature 1.0) |
| config_id | `tcfg-8fa3866deec917f3` |
| Split inside calibrate | 26 fit + 40 policy grid + 40 LTT |
| LTT | lambda_hat inf, `feasible: false`; in-sample LTT 0 commits (median guard risk 0.098; P14-41: 0.250) |
| Guard file | `willett-hw.lm.guard.json`, 7,111 bytes, SHA-256 `eaebd93e3d9d941d6fb742dbcad9a3465f025b39dd5ce35323e9b1ac74717b2a`; no truth text (`audit_text=False`, checked) |

| Verdict | Result |
|---|---|
| **V1 guard** | **returned, not certified** (40 LTT items < 45), commit threshold = never. As predicted (plan section 2) |
| **V2 safety** | holds: 0 wrong commits / 80 (CP95 [0, 0.0451]); trivial, no commits |
| **V3 value** | **vacuous**: 0 commits, safe WPM v0.1 **0.00** (no-BCI gaze reference 4.05) |
| **V6 controls** | **pass**: calibrate uniform 0 / 300, frame-shuffled 0 / 300, time-shuffled input 0 / 106 commits; test time-shuffled 0 / 80, zero 0 / 80 commits |
| V7 offers (real) | 77 offers, 3 withholds; offered top-1 exact **12 / 77**, CER 0.1715 (P14-41 guard: 0 / 80 exact, CER 0.2967) |

### V8 offer rates on null input (gap 136, descriptive)
| Input (80 test sentences) | Commit | Offer | Withhold | Offer rate | Flag "offer null passes" (<= 0.05) |
|---|---|---|---|---|---|
| real | 0 | 77 | 3 | 0.963 | - |
| time-shuffled input | 0 | 13 | 67 | 0.163 | no |
| zero input | 0 | 0 | 80 | 0.000 | yes |
| frame-shuffled frames | 0 | 77 | 3 | **0.963** | no |
| near-uniform frames | 0 | 0 | 80 | 0.000 | yes |

The P14-41 guard (no LM) offered on 4 / 80 time-shuffled and 77 / 80 frame-shuffled inputs. With the LM readout the time-shuffled offers rise to 13 / 80 (the inputs that pass the gate). The frame-shuffled offers stay as high as the real offers.

> **Our take:** the 106-sentence val split blocks a certified guard, whatever the readout: 40 LTT items can never reach 45. The LM readout does make the offers more useful (12 exact top-1 offers instead of 0; offered CER 0.17 instead of 0.30), but an offer list is still not evidence that the signal was read (frame-shuffled 77 / 80). Gap 138 (P14-47) and gap 136 (P5-31) stay open; this run gives them the first numbers on the LM readout.

## 3. Packaging (plan section 7)
- `src/fidetype/pretrained/lmreadout.py`: the P11-07 `LMBeam` (method unchanged; test: equal tokens and scores to the experiment file on random inputs, chunked and whole pushes), `NoSignalGate` (the P11-12 fit rule), `LmReadout`, `readout_for`.
- `XBodyCtcDecoder`: `text(stream, readout="greedy" | "lm")` (greedy stays the default), `lm_readout(gate=None | gate | False)`, `guard(readout="lm")`. `m.decide(stream)` keeps the P14-41 guard.
- Manifest `willett-hw.json`: a `text` file row for `eng_tatoeba_6gram_mkn_noE2Q.npz` (SHA-256 `7c4f133c...`, 3,348,165 bytes, local only), a second `guard` row (`willett-hw.lm.guard.json`), `licence.text_files` (CC BY 2.0 FR with attribution), and a `readouts.lm` block (settings, gate values and rule, metrics, null controls, a plain warning about the N1 failure, licence, test overlap, trust). A `limits` line names the LM, the overlap and the gate failure.
- Local files (not in git): `C:\Users\zhang\bci-data\pretrained\text\eng_tatoeba_6gram_mkn_noE2Q.npz`, `C:\Users\zhang\bci-data\pretrained\willett-hw\willett-hw.lm.guard.json`.
- Check: `load("willett-hw").guard(readout="lm")` loads `tcfg-8fa3866deec917f3`; its decisions and `m.text(stream, readout="lm")` equal the run on the first 10 test sentences (10 / 10 each).
- Tests: `tests/test_pretrained_lmreadout.py` + `tests/test_pretrained.py`: 24 passed.
- `docs/pretrained-decoders.md`: the readout, the gate, the licence, the overlap and the second guard.

## 4. Checks
| Check | Result |
|---|---|
| Split equal to `derived/p15-08/willett/splits.json` | yes |
| Log-probs (val / test; real, time-shuffled, zero) equal to the P14-41 files | max abs diff 0.0 for all six |
| Gate fitted on non-LTT val only | yes (66 positions of `default_rng(0).permutation(106)`); no test or null input used |
| Text in committed files | none (results.json and the guard file hold no text) |

## 5. Deviations
None from the plan. Note: the LM is the P15-25 file (13 / 80 test sentences in the Tatoeba export). P15-38 built an LM with every Willett text blocked (`derived\p15-38\eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz`, R-ball-s0 F 0.1743). It came after this plan was committed and is not used here (follow-up).

## 6. Limits
- One participant (T5), one checkpoint, one calibration draw; no CI.
- The guard is offer-only by construction (106 val sentences).
- The gate uses only emission counts; it cannot see the frame order, and it lets 16 % of time-shuffled inputs through.
- The LM CER can be a little optimistic (test overlap with the Tatoeba export).

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests (CPU, seconds) | `.venv\Scripts\python.exe -m pytest -q tests/test_pretrained_lmreadout.py` |
| All stages, detached (about 20 min CPU) | `.venv\Scripts\python.exe experiments/2026-11-20-p14-48-willett-lm-readout/launch.py` |
| Check / stop / resume | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p14-48\DONE` exists; stop: create `derived\p14-48\STOP`; resume: delete STOP and launch again (finished stages are skipped) |

## Licence
Willett data CC0 1.0. LM text CC BY 2.0 FR (Tatoeba contributors). Our code Apache-2.0. This commit holds aggregates only: no weights, LM file, log-probs or text.
