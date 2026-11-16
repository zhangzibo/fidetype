---
title: P11-01 continuous EMG-to-text decoder on emg2qwerty - pre-declared plan
type: experiment-plan
task: P11-01
updated: 2026-11-15
---

# P11-01: our own continuous EMG-to-text decoder on emg2qwerty (plan, written before training)

## Why
- P11 needs better decoders. A trust layer can only add value on top of a decoder that is good enough ([M2-19](../2026-11-15-m2-19-trust-retune/results.md)).
- emg2qwerty is the largest public typing dataset (108 users, 346.4 h, 1,135 sessions). It is the standard benchmark for **continuous** EMG typing: CTC over the whole recording, no oracle key times. Our P4-01 replay baseline used oracle key times ([entity page](../../wiki/entities/emg2qwerty.md)).
- This task prepares the decoder so that GPU training can start when M4-13 frees the GPU (about 2026-11-17). Data preparation, code and tests run on the CPU now.

## Licence and rules
- Data: CC BY-NC-SA 4.0 (the stricter of README / LICENSE). **Research use only.** The weights and per-user results are derived data: they stay local in `C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\` and are never committed. Only code, this plan and aggregate numbers go into the repo.
- Code: our own (Apache-2.0). We did **not** read or copy the emg2qwerty code. We read the paper (arXiv 2410.20081) for the published numbers and the split scheme only.
- The HDF5 files are untrusted. `prep.py` opens them only through `fidetype.adapters.emg2qwerty.Session` (h5py read-only, JSON checked, no pickles), with `python -I`, from the repo root.
- The trained weights cannot ship in a product (NC data). Licence-clean EMG decoders (KT-sEMG, Toronto) stay a separate part of P11-01.

## Published baseline (what we compare against)
Sivakumar et al. 2024, Table 3. CER in %, mean ± SD over 8 test users. "No LM" = greedy CTC; "LM" = 6-gram character LM.

| Model | No LM val | **No LM test** | LM val | LM test |
|---|---|---|---|---|
| Generic (no personalisation) | 55.57 ± 4.40 | **55.38 ± 4.10** | 52.10 ± 5.54 | 51.78 ± 4.61 |
| Personalised (random init) | 15.65 ± 5.95 | 15.38 ± 5.88 | 11.03 ± 4.45 | 9.55 ± 5.16 |
| Personalised (fine-tuned from generic) | 11.39 ± 4.28 | **11.28 ± 4.45** | 8.31 ± 3.19 | 6.95 ± 3.61 |

Their recipe (paper text, facts only): log spectrogram, 33 bins per channel, 32 ms window, 8 ms hop; batch norm first; band rotation and SpecAugment; time-depth-separable conv, 1 s receptive field (900 ms past, 100 ms future); CTC; 150 epochs, 4 s windows, Adam, warmup to 1e-3 then cosine to 1e-6; 8 A10 GPUs for the generic model. CER = Levenshtein distance between the predicted and true **keystroke** sequences / length of the true sequence.

We compare with the **no-LM** column. This task has no language model.

> **Caveat (comparability):** our test users, splits, features and model differ from the paper (see below). The comparison is indicative, not a replication.

## Splits
The dataset files and `metadata.csv` define **no** split. The paper's split lists are in the repository's code configuration; we do not use the repository. So we use **our own rule**, with the paper's scheme (8 held-out test users; per test user 2 val + 2 test sessions). The rule is in `prep.py` (`make_splits`) and the result in `<cache>\splits.json` (local; it holds user pseudonyms, so it is not committed).

| Rule | Detail |
|---|---|
| Test users | Among users with at least 8 sessions: the 8 users with the smallest SHA-256(`fidetype-p11-01-2026-11-16` + user id) |
| Per test user | Sessions in name order (= date order): last 2 = **test**, the 2 before = **val**, the rest = personal **train** (chronological, as in real use) |
| Generic train | All sessions of the other 100 users |
| Generic selection | The 16 val sessions of the test users (as the paper) |
| Quality tags | All sessions kept (no filter) |

| Split | Sessions | Hours | Keystrokes |
|---|---|---|---|
| Generic train (100 users) | 1,036 | 317.1 | 4,813,379 |
| Personal train (8 users) | 67 (6-14 per user) | 19.8 | 304,907 |
| Val (8 users x 2) | 16 | 4.9 | 72,616 |
| Test (8 users x 2) | 16 | 4.6 | 71,769 |

## Features (prep.py, CPU, done before training)
| Item | Value |
|---|---|
| Input | 32 channels (left band 0-15, right band 16-31), 2 kHz |
| Window / hop | 64 samples (32 ms), Hann, mean removed / 20 samples (10 ms) -> **100 frames/s** |
| Spectrum | rfft (33 bins of 31.25 Hz); DC dropped; bins 1-32 averaged into **12 bands** with about log spacing (edges 1,2,3,4,5,6,8,10,13,16,20,25,33) |
| Value | natural log of band power (+1e-6), float16 |
| Frame time | end of its window (causal): (20 k + 64) / 2000 s after the first sample |
| Normalisation | global mean / SD per channel x band over the generic-train sessions (`norm_generic_train.npz`). Fixed, label-free, causal |
| Cache size | 32 x 12 x 2 bytes x 100 frames/s x 346.4 h = **95.8 GB** (estimate; budget 150 GB) |

Why 12 bands at 100 Hz, not 33 bins at 125 Hz: the full paper resolution needs about 330 GB in float16. That is above our 150 GB cache budget. 12 log bands keep the shape of the EMG spectrum at 29 % of the bytes per frame.

## Targets (CTC)
- Vocabulary (98): 0 = blank, 1-95 = printable ASCII `' '` to `'~'` (case kept), 96 = Backspace `⌫`, 97 = Enter `⏎`.
- The target is the **keystroke sequence**, as the paper's CER: every key-down of a token key, Backspace included. Modifiers (Shift, Ctrl, ...), arrows and non-ASCII keys are dropped (< 0.2 % of key presses).
- A key belongs to the frame whose window first reaches its key-down sample. A training window holds the keys whose frame is inside the window.

## Model ("CRT", causal ring-TCN, our own design; `emgdec.py`)
| Part | Detail |
|---|---|
| Band encoder (x2, separate weights) | circular conv over the 16-electrode ring (12 bands in, 32 out, kernel 5) -> GELU -> linear 512 -> 256 |
| Temporal stack | 8 residual blocks, d = 512: LayerNorm -> depthwise **causal** conv (kernel 5, dilations 1,2,4,8,1,2,4,8) -> GELU -> feed-forward 512-1024-512 -> dropout 0.1 |
| Head | LayerNorm -> linear 98 -> log-softmax |
| Receptive field | 121 frames = 1.21 s of the past, **no lookahead** (strictly causal; unit test) |
| Size | 8,751,522 parameters |

Differences from the published model: no lookahead (theirs uses 100 ms future context), fixed global normalisation instead of batch norm, a ring conv instead of their rotation-invariance module, dilated causal conv instead of TDS blocks.

## Training
| Setting | Generic | Personal (per test user) |
|---|---|---|
| Init | random (seed 0) | best generic checkpoint |
| Data | 1,036 sessions | the user's train sessions |
| Windows | 4 s (400 frames), batch 64, sessions drawn by length, uniform offset | same |
| Steps | **max 150,000** (9.6 M windows, about 33 passes over the data); lowered by the budget rule | 3,000 (about 100 passes over 2.5 h of data) |
| Optimiser | AdamW, wd 0.01 (0 on norms and biases), clip 1.0 | same |
| LR | warmup 2,000 to 1e-3, cosine to 1e-6 | warmup 200 to 3e-4, cosine to 1e-6 |
| Augmentation | ring rotation -1/0/+1 per band; band time jitter up to 60 ms; 2 time masks (<= 150 ms); 1 band mask (<= 3 bands); per-channel log gain SD 0.2 | same |
| Loss | CTC, blank 0, mean over target length, `zero_infinity`; length tensors on the CPU (ROCm `ctc_loss` workaround of M4-13) | same |
| Selection | val CER every 5,000 steps; best = lowest val CER | every 300 steps |
| Precision | float32 (bf16 only after a separate check; not in this run) | same |

**Budget rule (fixed now).** Machine: Ryzen 7 9800X3D, 31 GB RAM, RX 7800 XT 16 GB (ROCm 7.2.1, torch 2.9.1, `C:\venvs\fidetype-rocm`). Before the generic stage, `train.py` runs a 200-step GPU pilot (after a 20-step warm-up) for each of two conv implementations: `torch` (nn.Conv1d) and `shift` (the same function from shifted slices and matmul, without MIOpen conv kernels; equal outputs and gradients, unit test). It keeps the faster one. Generic steps = min(150,000, floor(26 h / measured s per step), rounded down to 1,000). The result goes to `budget.json` once; a resume reads it. The cosine schedule uses that step count. Estimate: 0.2-0.6 s per step -> 12-26 h generic, plus 8 x 3,000 personal steps (1.5-4 h), plus evaluation (< 1 h).

**Memory.** The cache is memory-mapped (read-only). The loader reads about 20 MB per batch in 4 threads. Expected RAM < 6 GB; GPU memory < 8 GB.

## Checkpoints, pause and launch
- `latest.pt` (model, optimiser, step, best) every 4 min and at each validation, written atomically. `best.pt` at each new best val CER.
- **Exact resume:** batch k and every random draw of step k (data, augmentation, dropout) depend only on (seed, k). A run that stops and resumes gives the same weights as a run without a stop (unit test `test_resume_is_exact`).
- **Pause:** create `C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train\pause` (or `stop`). The job saves `latest.pt` after the current step and exits (code 3). Remove the file, then launch again.
- **Hidden launch:** `launch_train.py` uses `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` (the M4-13 `launch.py` pattern). Never `Start-Process -WindowStyle Hidden`. `--wait-for <file>` lets a hidden CPU waiter (no torch, no GPU) start training when a file appears, for example `m4-13-queue.DONE` (read only).
- Keep-awake: `SetThreadExecutionState` while the job runs.
- Outputs only in `C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train\`. Nothing goes into `bci-data\runs\`.

## Evaluation (once, at the end)
- Each test session is decoded **whole** and causally (chunks with left context = receptive field; equal to one pass, unit test). Greedy CTC, no LM.
- **Primary metric: CER** = total edit distance / total reference keystrokes, on the keystroke sequence of the whole session.
- Reported, aggregate only: CER pooled over the 16 test sessions; mean over the 8 users of the per-user CER (the paper's form); prompt-level CER (keystrokes inside each text prompt, decoded from the frames of that prompt). Per-user values stay in `per_user_local.json` (never committed).
- Generic model: val and test CER. Personalised models: test CER.
- **Control:** the personalised models on time-shuffled test frames (fixed seed). Expected CER close to 1.
- **Emission delay:** per reference key, the time from key-down to the first frame whose argmax is the same token (window -0.5 s to +1 s). Median and p90.
- The test sessions are decoded once, after all selection is done on val.

## Pre-registered success criteria
| Id | Criterion | Pass if |
|---|---|---|
| **S1 (primary)** | Personalised test CER, mean over 8 users, no LM | **<= 20.0 %** |
| S1+ (stretch) | same | <= 11.28 % (published fine-tuned, no LM) |
| S2 | Generic test CER, mean over 8 users, no LM | <= 60.0 % (published 55.38 %) |
| S3 | Personalisation helps | personalised < generic test CER for >= 7 of 8 users (count only) |
| C1 | Time-shuffle control | pooled CER >= 0.90 |
| N1 | NTS output | 100 % of personalised test prompt streams reach conformance level `trust-ready` |
| L1 | Real-time form | no lookahead (structural, unit test); median emission delay reported (no threshold) |

If S1 fails, the next steps are (in order): a longer generic run, 33 bins at 125 Hz on a subset, a bounded lookahead (100 ms) as in the paper. We report a failed criterion as a failure.

## Decoder output -> NTS frames -> trust layer
1. The decoder emits one 98-way log-prob vector per 10 ms frame, stamped at the end of its input window. `causal = true`, `decoder.lookahead_s = 0`.
2. `train.py nts` cuts the frames of each text prompt and calls `fidetype.adapters.ctc_logits.from_array` (input `log_probs`, `frame_period` 0.01 s, `t0` = time of the first frame, vocabulary above with blank 0, `vocab_type = char`, `vocab_id = fidetype-p11-01-keys-v1`, modality `emg`, `decoder.weights_sha256`, `fidetype.research_only = true`, data licence). One stream per prompt; each stream is checked at level `trust-ready`.
3. The streams then go to the trust layer as any CTC stream: [CTC-logits adapter](../../wiki/concepts/ctc-logits-adapter.md) -> trust processor (collector) -> `trust_decision` events. A trust config for EMG (LTT on the personal val streams, commit gate, null controls; the M2-19 rule) is a follow-up task, not part of this plan.
4. Open point: `⌫` and `⏎` are tokens of a `char` vocabulary. Text for display = apply the Backspaces. A later FEP may define `vocab_type = key` streams with edit keys.

## Commands
| Step | Command (repo root) |
|---|---|
| Cache (done on CPU, 2026-11-15: 22.4 min, 1,135 sessions, 124,582,078 frames, 5,249,381 keys, 95.7 GB) | `.venv\Scripts\python.exe experiments\2026-11-16-p11-01-emg-decoder\launch_prep.py` |
| Tests (CPU, 14 tests) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q experiments/2026-11-16-p11-01-emg-decoder/test_p11_01.py` (GPU hidden by the test) |
| **Start GPU training** | `.venv\Scripts\python.exe experiments\2026-11-16-p11-01-emg-decoder\launch_train.py --wait-for C:\Users\zhang\bci-data\runs\m4-13-queue.DONE` (or without `--wait-for` when the GPU is free) |
| Check | `Get-Content C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train\train.log -Tail 5` |
| Pause / stop | `New-Item C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train\pause` |
| Resume | remove `pause`, run the start command again |
