---
title: P14-33 willett-hw - Willett handwriting decoder of our own in the pretrained registry
type: experiment
task: P14-33
updated: 2026-11-19
---

# P14-33: `willett-hw` in the pretrained registry (results)

Code: [run.py](run.py) (stages `numpy`, `torch`, `guard`). Numbers: [results/results.json](results/results.json); log: `results/run.log`. Per-sentence records (decoded text, truth), the saved log-probs and the guard file: `C:\Users\zhang\bci-data\derived\p14-33-willett-hw\` only. Weights: `C:\Users\zhang\bci-data\pretrained\willett-hw\willett-hw.weights.npz` (local only, never committed). CPU only (background class, 4 threads); the GPU is hidden (`HIP_VISIBLE_DEVICES=-1`).

## The model
| Item | Value |
|---|---|
| Source run | P15-08 E1a `R-all-s0`: random init, budget "all" (781 pool sentences, 506.0 min), seed 0, final step 3000 (the primary readout of P15-08) |
| Licence check | Run `licence.json`: data "Willett handwriting (CC0-1.0)", `research_only: false`. The exporter refuses a run whose `licence.json` is not clean. No T / E / S trunk (emg2qwerty-derived, research only) is used |
| Weights file | `willett-hw.weights.npz`, 34,369,716 bytes, SHA-256 `66ac6590...` (plain float32 arrays, no pickle); checkpoint SHA-256 `a6cc87b1...` |
| Weights licence | CC0-1.0, **provisional** (user decision D11); not hosted (gap 98 = P14-30, user step) |
| Runtime | `xbody-ctc` ([`_xbody.py`](../../src/fidetype/pretrained/_xbody.py)): per-session z-score -> Linear(192 -> 512) -> the P11-01 causal trunk (8 blocks, shared NumPy code in `_crt.trunk_log_probs`) -> 98 key tokens. NumPy only |
| Reader | `readers.read_willett_session` (a `t5.*` session folder or its `sentences.mat`; scipy; only 8 named variables; 400 MB size limit) |
| Language | `en` |

## Outcome: the card metric reruns with `load("willett-hw")`
| Check | Result |
|---|---|
| Split | Recomputed from the public files (test = last block of each session with a usable sentence; val = salted-hash block). Equal to the P15-08 `splits.json`: **yes** |
| Test greedy CER, NumPy runtime on CPU | **0.3051** (1,052 / 3,448 characters, 80 sentences) |
| PyTorch value of the training run (GPU, stored `result.json`) | 0.3051 |
| Per-sentence edit counts, NumPy vs PyTorch | equal on **80 / 80** sentences (max difference 0 edits) |
| Tolerance | CER equal within 0.002 (7 edits of 3,448); met with 0 edits difference |
| NTS conformance of the test streams | `provenance` on 80 / 80 |
| `decode_file` vs direct `log_probs` (one session) | max abs difference 9.5e-7 (the stream re-normalises each row) |
| Val greedy CER of this checkpoint (step 3000) | 0.2603 (106 sentences). The P15-08 value 0.258 is the best-val step 2700, a different checkpoint |
| Time | test decode 144 s, numpy stage 347 s (4 threads, machine shared with other jobs) |

- The `torch` stage (PyTorch on CPU, log-prob difference) did not run: the machine was low on memory (see below). The stored PyTorch result already matches per sentence. The P14-01 scratch check measured the same trunk code (CRT) against PyTorch on CPU: max abs difference 3.8e-5.
- The unit test `test_xbody_runtime_equals_reference_chunks_and_causal` checks the runtime against a plain float64 loop of the same maths (atol 1e-4), chunked = one pass, and causality.

## What the card says (required caveats)
- Greedy CER 0.305 is **weak**. The published Willett et al. 2021 real-time decoder is much better (other recipe).
- The same recipe **fails on seed 1** (R-all-s1, test CER 0.920).
- **No LM.** Greedy CTC only.
- **Descriptive only:** an offline replay of one participant (T5); not a user study.
- Only the 10 dataset sessions have z-score statistics.
- **Other split than the benchmark track `willett-hw`** (last 3 sessions; cal = first third of each session, test = the rest): 193 of the track's 254 test trials (76 %) are in this model's training pool, 34 in its val blocks, 27 in its test blocks. So this model must not be scored on that track as it is.

## Guard: not packaged (new gap 121 = P14-41)
The `guard` stage (calibrate on the 106 val sentences, nulls = 106 time-shuffled val sentences, alpha 0.05, delta 0.1) started after the numpy stage. Claude Code stopped the process because the machine was critically low on memory (other jobs ran at the same time, among them P11-07). Per the rules, the job was not restarted. The guard is therefore not cheap here; it is registered as gap 121 (P14-41). The manifest has `trust: null` and a `trust_note`.

> **Our take:** with greedy CER 0.305, almost no test sentence is exact, so a sentence-level guard on this decoder would mostly OFFER. A packaged guard becomes useful with a word LM (P14-12, gap 26) or a stronger decoder (P15-33, gap 120).

## Use for other items (not done here)
- **P14-12** (gap 26, word LM for Willett-hw) and **P6-06** (gap 28, input-level controls for the Willett entry) can use this decoder: it runs on the neural cube, so input-level controls (time-shuffled, zero input) are possible. Both must respect the split caveat above (retrain on the track train split, or score on the P15-08 test blocks).

## Limits
- One reproduction on the machine that trained the model. A clean-machine test needs hosted weights (gap 98 = P14-30, user step).
- The `torch` CPU stage and the guard did not run (memory).

## Rerun
| Step | Command (repo root) |
|---|---|
| Export the weights (torch venv, CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -I tools/pretrained/export_weights.py willett-hw` |
| Card metric (NumPy) | `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-19-p14-33-willett-hw/run.py numpy` |
| PyTorch CPU comparison | `... -- C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-19-p14-33-willett-hw/run.py torch` (after `numpy`) |
| Guard (gap 121) | `... -- .venv\Scripts\python.exe -I experiments/2026-11-19-p14-33-willett-hw/run.py guard` (needs free memory) |
