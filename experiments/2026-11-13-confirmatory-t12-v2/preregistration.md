---
title: "Pre-registration v2: confirmatory test of the Paper 1 frozen configuration on participant T12, with a stronger decoder"
type: protocol
task: M3-28
written: 2026-11-13
status: pre-registered (this file is committed and pushed before the v2 decoder decodes any trust-pool trial)
---

# Pre-registration v2: confirmatory test on participant T12

This file fixes the full analysis **before** the v2 decoder decodes any trust-pool trial. The git commit that adds this file is the pre-registration. A later change to this file is a deviation. We list every deviation in `results.md`, section "Deviations".

Writing style: 80 % ASD-STE100.

It copies the M3-27 pre-registration ([../2026-11-13-confirmatory-t12/PROTOCOL.md](../2026-11-13-confirmatory-t12/PROTOCOL.md), commit `a7cf624`). This file states only what is the same in short form and what is different in full.

## 0. Why a v2, and what was seen before

M3-27 (result commit `5d49d7e`) was **uninformative**: the frozen configuration committed 0 of 400 test trials, because our T12 decoder was weak (test greedy PER 0.542; right sentence first for 3/400 trials). Safety held (0 wrong commits; controls 0/400).

**Prior exposure of the test data (honest statement).** The M3-27 run decoded the same trust pool (the same 880 trials, the same fit-A / calibration / test split) once, with the M3-27 decoder. We saw only aggregate numbers: the decoder quality (PER, WER, sentence exact match), the trust outcomes (0 commits), guard AUROC 0.966, and per-session counts. We did not read per-trial decodes. Nothing from the trust pool went into the v2 decoder: the v2 decoder uses only the decoder-train and decoder-validation blocks, and every v2 decoder choice used the decoder-validation PER only. The trust configuration is frozen and is not re-fitted by hand. So the leak is small, but this test is not on fully unseen data. A reader should weight it as a second, partly exposed look at T12.

## 1. Question

The same as M3-27: on a second participant (T12, Willett et al. 2023), with our own decoder, does the frozen configuration (git tag `paper1-v4-frozen-config`, commit `3e8366f`) keep the wrong-commit rate on later sessions at or below α = 0.05, and does it still refuse to commit no-signal streams? New in v2: the test must commit enough trials to be able to fail (Sec. 7).

## 2. Data (unchanged)

Willett et al. 2023 / Brain-to-Text '24 `competitionData` (CC0 1.0; Zenodo record 8047896, md5 `a7e9d972ac5b65171a37674eb47730b8`), participant T12, 24 sessions, `tx1` + `spikePow` (512 features per 20 ms bin). Raw path `C:\Users\zhang\bci-data\raw\b2t24\` (never committed). We do not use `competitionHoldOut`. Text normalisation: `normalize_words` of `fidetype.adapters.b2t25`.

## 3. Splits (unchanged)

The same splits as M3-27, Sec. 3: decoder train = `train` blocks minus the last `train` block of each session (7,900 trials); decoder validation = the last `train` block of each session (880); trust pool = the `test` block (the last block) of each session (880). Fit-A = trust pool of sessions 1-8 (240 trials), calibration = sessions 9-14 (240), **test = sessions 15-24 (400)**. Time order rules as in M3-27.

## 4. Decoder v2 (our own code; no third-party code copied)

We read nothing from the dataset's companion code (`fwillett/speechBCI`, no licence) and copy nothing from it. The values below were chosen on the decoder-validation PER only (Sec. 4.5 lists every run).

### 4.1 Input normalisation (changed: causal rolling window)
- Per session, put all trials in time order: the `train` file trials in file order (block order), then the `test` block trials.
- Each trial is z-scored with the mean and SD of each feature over all bins of the **W = 20 previous trials** (one block = 20 trials). The first 20 trials of a session (the first decoder-train block) use the stats of those same 20 trials; these are decoder-train trials only.
- z-scores are clipped to ±10 (an almost silent channel in the window gives very large values).
- So a validation or trust-pool trial uses only the features of earlier trials (no labels, no future data). A trust-pool trial uses the earlier trials of its own block (features only). This is causal and can run online.

### 4.2 Targets (unchanged)
CMUdict phonemes (first pronunciation, no stress, `SIL` between words), the 41-token `fidetype.adapters.b2t25.VOCAB`. A sentence with an out-of-vocabulary word is not a decoder target; it stays in the trust pool.

### 4.3 Model and training (final values)
| item | value |
|---|---|
| input layer | per-session affine 512 -> 512 (identity init) + softsign (as M3-27) |
| smoothing | causal half-Gaussian, SD 2 bins (past bins only) |
| patches | 32 bins, stride 4 (output frame period 80 ms; frame time = end of its 32-bin patch) |
| GRU | 5 unidirectional layers (separate single-layer GRUs, MIOpen off), hidden 1024, dropout 0.4 |
| output | linear to 41 classes, CTC loss |
| optimiser | AdamW, lr 5e-4, eps 1e-8, weight decay 1e-5, linear warm-up 500 steps, cosine decay over 120 epochs |
| batch / epochs | 64 / at most 120, early stop after 20 epochs without a better validation PER |
| augmentation | white noise SD 0.8, constant offset SD 0.2 per trial (training only) |
| seed | 0 |
| result | best validation greedy PER **0.293** at epoch 102 (run ended at the 120-epoch maximum, status `done`); train-subset PER 0.16 at epoch 20 |

### 4.4 Stream and word decoding (one change: a word trigram term)
The M3-27 Sec. 4.4 route: `NeuralTextStream` (phoneme, 41 tokens, 80 ms frames, frame time = end of its input patch, latency 0), `to_symbol_stream`, then the B2T '25 word route with the B2T '25 tuned values (`lm_weight` 1.0, `edit_penalty` 12, `word_bonus` 3; CMUdict lexicon, Tatoeba word unigram, Tatoeba char 6-gram).

**Change:** the sentence LM of the word route is `char6(text) + β · word3(text)` with **β = 2.0**. `word3` is our interpolated Kneser-Ney word trigram (D 0.75) on the same Tatoeba English corpus (`wordlm.py`; cache `C:\Users\zhang\bci-data\lm\eng_tatoeba_word3_kn.pkl`). We chose β on the final decoder's validation decodes, grid {0, 0.5, 1, 2} (`results/lm-tune.json`): sentence exact 0.068 / 0.083 / 0.089 / 0.095, WER 0.446 / 0.434 / 0.431 / 0.427. β = 2.0 is the best value and the grid edge; we did not extend the grid. No other word-route value changed. Nothing in the word route was tuned on trust-pool data.

### 4.5 Decoder runs (all on decoder-validation PER only)
All runs use the decoder-train blocks for training and the decoder-validation blocks (the last `train` block of each session) for the PER. The trust pool was not loaded. Run directories: `C:\Users\zhang\bci-data\runs\<run>\`.

| run | change against M3-27 `t12-gru-r2` | result (greedy validation PER) |
|---|---|---|
| `t12-gru-r2` (M3-27 final) | session-level normalisation, GRU 5 × 512, patch 14, lr 5e-4, batch 32 | 0.580 at epoch 10; 0.470 at epoch 150 |
| first `t12-v2-p1-roll` attempt | rolling normalisation without clipping | NaN loss in epoch 1 (float16 overflow of z-scores) → clip ±10 added; run deleted |
| `t12-v2-p1-roll` | rolling normalisation (Sec. 4.1); all else as `t12-gru-r2` | 0.510 at epoch 10 (stopped at epoch 11: the gain was clear) |
| `t12-v2-p2-roll-opt` | + lr 0.02, Adam ε 0.1, batch 64, warm-up 500 | CTC blank collapse (PER 1.0, epochs 1-4); stopped |
| `t12-v2-p3-big` | rolling + GRU hidden 1024, patch 32, batch 64, warm-up 500, lr 5e-4 | 0.391 at epoch 10 (pilot stop) |
| `t12-v2-final` | the `t12-v2-p3-big` values, at most 120 epochs (cosine), patience 20 | see Sec. 4.6 |

**Word LM term (chosen on validation only).** We added an optional word trigram to the sentence LM of the word route: `sentence_lm = char6 + β · word3`, with `word3` an interpolated Kneser-Ney trigram (D 0.75) on the same Tatoeba English corpus (CC BY 2.0 FR; `wordlm.py`). On the pilot `t12-v2-p3-big` validation decodes, sentence exact was 0.010 / 0.011 / 0.014 / 0.015 for β = 0 / 0.25 / 0.5 / 1.0 (`results/pilot-p3-lm-tune.json`). The final β comes from a grid on the final decoder's validation decodes (Sec. 4.4).

We did not try time masking, layer normalisation or other LMs (time budget).

### 4.6 Fixed decoder checkpoint
- Checkpoint: `C:/Users/zhang/bci-data/runs/t12-v2-final/best.pt`
- SHA-256: `5317b0600a5cbfc6679116d2c47f4da1007a1544a63962d8dbdf9308f1063787`
- `run.py --stage trust` refuses to run if the decoded log-probabilities do not carry this hash.

## 5. The frozen trust configuration (unchanged)

The same as M3-27 Sec. 5: `HarnessConfig(seed=0, user_config=U, max_wrong_commit=0.05, use_guard=True)`, `pipe.fit(fitA, fitA)`, `pipe.calibrate_commit(calibration, method="ltt", alpha=0.05, delta=0.1, combine="max")`, freeze with `FrozenTrustConfig.from_pipeline(pipe, recipe=PAPER1_V4_RECIPE)`, then one `pipe.evaluate(test)`. The user model U is `UserConfig.aac_gaze(chars_per_min=304.0)` (the T12 speech rate of the decoder-train trials, unchanged by the new normalisation), fallback gaze typing 20 characters per minute. `run.py` checks that the trust-core files are byte-identical to the tag. **No re-tuning on T12**: the fit-A and calibration steps are the frozen recipe; nobody chooses a value by hand.

## 6. Endpoints (unchanged)

Primary P1 (pooled wrong-commit, CP95 + session bootstrap), P2 (per session), P3 (frame-shuffled and uniform controls, seed 20261112, jitter 0.05). Secondary: commit rate, EAC, silent errors, eWPM, paired gain over no commits and over gaze typing, plug-in rule, joint LTT β 0.10 / 0.20, decoder quality, guard AUROC, intent-mismatch control. Statistics as in M3-27 Sec. 6.3 (B = 2000, seed 20261112, session clusters; exact CP).

**New secondary (v2), descriptive only:** for the test trials and for each control, the number of commits whose committed text is **empty**, and the wrong commits with a non-empty text (`n_commit_empty`, `n_wrong_commit_nonempty` in `run.py`). Reason: see Sec. 7.1. These numbers do not change C1-C3 or the outcome label.

## 7. Success criteria and the informative condition

| id | criterion | pass if |
|---|---|---|
| C1 | P1 pooled wrong-commit | point estimate ≤ 0.05 |
| C2 | P2 per session | no test session has a CP 95 % lower bound above 0.05 |
| C3 | P3 controls | commit rate ≤ 0.01 on the frame-shuffled controls **and** on the uniform controls |
| I | informative | the LTT max rule commits **at least 21** of the 400 test trials |

Why 21: C1 can fail only if the wrong commits are more than 0.05 × 400 = 20. With 20 or fewer commits, C1 passes whatever the decoder does. So 21 commits is the smallest number for which the test can fail. In code: `informative_min(n) = floor(0.05 · n) + 1`.

Outcome labels (one of three):
- **Confirmed:** C1, C2, C3 pass and I holds.
- **Uninformative:** C1, C2, C3 pass and I does not hold. We report the commit count (0-20) and the LTT result.
- **Not confirmed:** C1, C2 or C3 fails, whatever I says. We report which one and by how much.

### 7.1 Dry run on decoder-validation data and our prediction

Before this commit we ran all trust stages once on the **decoder-validation** blocks (not the trust pool), with the same session roles (fit-A sessions 1-8, calibration 9-14, "test" 15-24; `results/dryrun-trust.json`). The validation blocks also chose the decoder epoch, so these numbers are optimistic. Results:

| item (validation dry run) | value |
|---|---|
| word route, "test" sessions | WER 0.386, right sentence first 0.12, guard AUROC 0.760 |
| LTT | feasible, λ̂ 0.30 (empirical risk 0.029 on 240 calibration trials), final `commit_p` 0.30 |
| LTT max on "test" (400) | 22 commits, 11 wrong: wrong-commit 0.0275 (CP95 0.014-0.049); EAC 0.50 |
| frame-shuffled control | 6/400 commits (1 empty text) → above 0.01 |
| uniform control | **335/400 commits; 320 of them commit an empty text**, 15 a short non-empty text → above 0.01 |
| label by Sec. 7 | not confirmed (C3 fails); C1, C2 pass; I holds |

**Mechanism (our reading of the frozen code).** A near-uniform stream decodes mostly to an empty word sequence with a one-item n-best. The guard (`trust/guard.py`) then sees no low-evidence characters (there are no characters) and full n-best consistency (one candidate), so its risk is 0, and the sentence probability of a one-item n-best is 1. So the frozen policy can commit an empty text. With the M3-27 decoder this never showed, because the frozen policy committed nothing at all.

**Prediction (written before the test run):** on the test sessions, C3 will fail (outcome "not confirmed"), mainly by empty-text commits on the uniform controls; C1 and C2 will probably pass. We do **not** change the frozen configuration to avoid this: that would be re-tuning on T12, and the frozen configuration is the object under test. A fix (for example "never commit an empty text", or a guard term for empty or very short candidates) belongs to a later, separately versioned configuration.

We report the outcome whatever it is. There is no second test run. If a bug is found after the test run, we fix it, rerun once, and report both runs and the fix as a deviation.

## 8. Analysis code (fixed by this commit)

The code at this commit is the analysis code: `experiments/2026-11-13-confirmatory-t12-v2/{t12.py, prep.py, train_decoder.py, decode.py, run.py, wordlm.py, lm_tune.py, config.json}`. After this commit, the only allowed change before the test run is to write this commit's hash into `config.json` (`preregistration_commit`); `run.py --stage trust` refuses to run without it. Order of stages after this commit:
1. `decode.py --run t12-v2-final --parts val,pool` (GPU; writes the trust-pool log-probabilities, outside the repo).
2. `run.py --stage trust` (the single test run; refuses to overwrite `results/trust.json`).
3. `run.py --stage tables`.

`run.py --stage decoder` (word-route quality on decoder validation) and `run.py --stage dryrun` (the trust stages on decoder-validation data, not the trust pool) ran before this commit; their outputs are in `results/decoder.json` and `results/dryrun-trust.json`.

## 9. Data handling (unchanged)

Raw data, per-trial decodes, streams and sentences stay in `C:\Users\zhang\bci-data\` (`raw/b2t24/`, `derived/2026-11-13-confirmatory-t12-v2/`, `runs/t12-v2-*/`). The repo gets only code, configs, aggregate numbers and the frozen trust config (numbers only). No sentence text in committed files.
