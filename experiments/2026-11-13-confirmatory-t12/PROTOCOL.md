---
title: "Pre-registration: confirmatory test of the Paper 1 frozen configuration on a second intracortical participant (T12)"
type: protocol
task: M3-27
written: 2026-11-12
status: pre-registered (this file is committed and pushed before any decoder output on the trust-test data exists)
---

# Pre-registration: confirmatory test on participant T12

This file fixes the full analysis **before** we decode or look at any trust-test data. The git commit that adds this file is the pre-registration. A later change to this file is a deviation. We list every deviation in `results.md`, section "Deviations".

Writing style: 80 % ASD-STE100.

## 1. Question

Paper 1 froze a trust-layer configuration (git tag `paper1-v4-frozen-config`, commit `3e8366f`). All Paper 1 evidence on the commit rule comes from one intracortical participant (T15, Brain-to-Text '25). Paper 1, Sec. 7 ("A frozen configuration for a confirmatory test") asks for a test on data that we did not use.

**Question:** On a second participant (T12, Willett et al. 2023), with our own decoder, does the frozen configuration keep the wrong-commit rate on later sessions at or below α = 0.05, and does it still refuse to commit no-signal streams?

## 2. Data

| item | value |
|---|---|
| Source | Willett et al. 2023, "A high-performance speech neuroprosthesis", Nature. Dryad doi:10.5061/dryad.x69p8czpq |
| File | `competitionData.tar.gz` (the Brain-to-Text '24 benchmark form of the sentence data) |
| Copy used | Zenodo record 8047896 (the Zenodo deposit linked to the same Dryad DOI; Dryad file downloads need a login token). md5 `a7e9d972ac5b65171a37674eb47730b8`, 3,653,747,969 bytes |
| Licence | CC0 1.0 |
| Local path | `C:\Users\zhang\bci-data\raw\b2t24\` (outside the repo; never committed) |
| Participant | T12 (BrainGate2, ALS), 4 Utah arrays (area 6v and area 44), 256 channels, 20 ms bins |
| Partitions in the file | `train` (all blocks of a session except the first two and the last), `test` (the **last block** of each session, labels present), `competitionHoldOut` (the first two blocks of each session; labels withheld in this copy) |

We do not use `competitionHoldOut` (no labels). We do not use the 50-word sentences (the file already excludes them).

**Text normalisation:** `normalize_words` of `fidetype.adapters.b2t25` (lower case; keep `a`-`z`, the apostrophe and single spaces). This is the truth for all word-level outcomes.

## 3. Splits (fixed before any decoding)

Let the sessions with labelled `test` blocks be S_1 < S_2 < ... < S_N, sorted by session date (the date in the file name).

| part | content | used for |
|---|---|---|
| Decoder train | `train` blocks of all N sessions, minus the last `train` block of each session | training the decoder weights |
| Decoder validation | the last `train` block of each session | early stopping and decoder hyper-parameter choice only |
| **Trust pool** | the `test` block (last block) of each session | never used for decoder training or decoder choices |
| Fit-A | trust pool of sessions S_1 .. S_a, a = round(N / 3) | frame + sentence temperatures, conformal set, guard, policy grid (`pipe.fit(fitA, fitA)`) |
| Calibration | trust pool of sessions S_(a+1) .. S_(a+c), c = round(N / 4) | LTT only (`calibrate_commit`) |
| **Test** | trust pool of sessions S_(a+c+1) .. S_N | the single confirmatory run |

For the expected N = 24: fit-A = sessions 1-8, calibration = sessions 9-14, test = sessions 15-24.

Time order:
- Trust layer: fit-A sessions < calibration sessions < test sessions, in calendar order (the paper's "calibration precedes the test data in time" rule, Sec. 7).
- Decoder: in every session, the decoder-train blocks come before that session's trust-pool block in time. This copies the clinical practice of the source study (the decoder was retrained each day on that day's earlier blocks).
- Inside a session, trial order = file order.

**The decoder sees trust-pool sessions' earlier blocks.** This is the same for fit-A, calibration and test sessions, so the three parts stay exchangeable with respect to the decoder.

## 4. Decoder (our own code; no third-party code copied)

The companion code of the dataset (`fwillett/speechBCI`) has no licence. We read nothing from it for this work, and we copy nothing from it.

### 4.1 Input
- Features: `tx1` (threshold crossings, -3.5 × RMS) and `spikePow` (spike-band power), 256 + 256 = 512 features per 20 ms bin.
- Normalisation (causal): for each session, mean and SD of each feature over all bins of that session's decoder-train blocks. Every block of that session (train, validation, trust pool) is z-scored with these values. No statistic comes from a trust-pool block.

### 4.2 Targets
- Phonemes: CMUdict (the same file as in B2T '25, `C:\Users\zhang\bci-data\lexicon\cmudict\cmudict.dict`), first pronunciation, stress marks removed, `SIL` between words. Vocabulary: the 41 tokens of `fidetype.adapters.b2t25.VOCAB` (blank, `SIL`, 39 ARPAbet), the same as T15.
- A sentence with a word that is not in CMUdict is **not** used as a decoder training or validation target. It stays in the trust pool. Its `stream_text` (phoneme truth, used only by the frame temperature fit and greedy PER) skips the unknown words.

### 4.3 Model and training
- Per-session affine input layer (512 → 512, identity init) + softsign; Gaussian smoothing of the input along time (SD 2 bins); patches of 14 bins with stride 4 (output frame period 80 ms, as T15); unidirectional GRU; linear output to 41 classes; CTC loss.
- Planned values: GRU 5 layers, hidden size 512, dropout 0.4; AdamW, peak learning rate 2e-3 with linear warm-up and cosine decay, weight decay 1e-5; batch 32; augmentation: white noise SD 0.8 and a constant offset SD 0.2 per trial (training only).
- Stop: best validation phoneme error rate (PER), early stopping after 20 epochs without gain, at most 150 epochs.
- We may change the decoder hyper-parameters **only** on the validation PER. Every change and its validation PER goes into `results.md`. The trust pool is never decoded before the decoder is final.
- Checkpoints every few minutes; resume from the latest checkpoint. GPU: AMD RX 7800 XT, ROCm.

### 4.4 Stream and word decoding (the B2T '25 code path, unchanged)
- Stream: `NeuralTextStream`, `vocab_type="phoneme"`, the 41-token vocabulary, `log_softmax` of the decoder output, `frame_period` 0.08 s, frame time = end of its input patch, `latency` 0 (causal GRU). Provenance in `meta`: device, decoder name + checkpoint SHA-256, adapter, session id, `stream.id` (hash), no text.
- For the trust core: the one-character-per-token form (`to_symbol_stream`), as for T15.
- Phonemes → words: exactly the B2T '25 route and the B2T '25 tuned values, **with no re-tuning on T12**: CTC prefix beam (vector search, beam 64, 20-best, `prune_logp` -8, space rules) → CMUdict lexicon with 1-2 phoneme edits → word beam (`lm_weight` 1.0, `edit_penalty` 12, `word_bonus` 3, `unigram_weight` 1.0, `per_slot` 6, `per_hyp` 8, `n_best` 10, `drop_penalty` 15, `oov_logp` -20, fallback words with Tatoeba count ≥ 5) with the Tatoeba word unigram and the Tatoeba char 6-gram LM.

## 5. The frozen trust configuration (Paper 1, Sec. 7; `PAPER1_V4_RECIPE`)

The trust-core code is the code at tag `paper1-v4-frozen-config`. `run.py` checks that `src/fidetype/trust/{policy,guard,risk_control,calibration,conformal}.py` and `src/fidetype/eval/harness.py` are byte-identical to the tag, and records the result.

1. `HarnessConfig(seed=0, user_config=U, max_wrong_commit=0.05, use_guard=True)`; all other fields default: `GuardConfig()` defaults (combine `max`), conformal α 0.1 (LAC, conditional, half of fit-A), `DEFAULT_GRID` policy grid, `max_attempts` 2 (each item has one stream, so one attempt).
2. `pipe.fit(fitA, fitA)`: frame temperature on the first half of fit-A, sentence temperature on the same half, conformal on the second half; policy grid on all of fit-A (max eWPM subject to plug-in wrong-commit ≤ 0.05).
3. `pipe.calibrate_commit(calibration, method="ltt", alpha=0.05, delta=0.1, combine="max")`: Learn then Test, fixed-sequence over the grid 1.00 → 0.00 (step 0.01), exact binomial p-values; `commit_p` = max(grid value, LTT λ̂).
4. Freeze: `FrozenTrustConfig.from_pipeline(pipe, recipe=PAPER1_V4_RECIPE)`; write the JSON (numbers only, no data) to `results/trust-config-t12.json` with its `config_id`.
5. Run the test once: `pipe.evaluate(test)`.

**User model U:** `UserConfig.aac_gaze(chars_per_min=r)`, with r = the T12 speech rate = characters of the normalised sentences / total go-period duration (number of bins × 0.02 s) × 60, over the decoder-train trials. Fallback gaze typing 20 characters per minute. All other user values are the defaults of Paper 1.

## 6. Endpoints

All on the test sessions, from the single run.

### 6.1 Primary
- **P1 (pooled safety):** wrong-commit rate (wrong COMMITs / test trials) under the LTT max rule, with the exact Clopper-Pearson (CP) 95 % interval and the session-cluster bootstrap 95 % interval.
- **P2 (per session):** wrong-commit rate per test session with CP 95 % intervals; the number of test sessions above α, and the number with a CP lower bound above α.
- **P3 (no-signal controls):** commit rate of the guarded frozen configuration on two control streams made from every test trial: frame-shuffled (`shuffle_stream`) and near-uniform (`uniform_stream`, jitter 0.05). RNG seed 20261112. One-sided CP 95 % upper bound.

### 6.2 Secondary
- Commit rate, error among commits (EAC), silent-error rate, eWPM of the LTT max rule.
- Paired eWPM gain over the same fitted policy without commits (`commit_p = +inf`), and gaze typing alone.
- Plug-in rule (the policy-grid `commit_p` without LTT): the same outcomes (no guarantee; reported for contrast).
- Joint LTT (marginal wrong-commit ≤ 0.05 and EAC ≤ β, β = 0.10 and 0.20; Bonferroni over the fixed grid 0.05 .. 1.00, step 0.05; δ 0.1), as in Paper 1: commit rate and wrong-commit rate.
- Decoder quality: greedy PER, word CER and WER of the top-1 sentence, sentence exact match, truth in n-best; on decoder validation and on the test sessions.
- Guard AUROC (guard risk vs. wrong top-1) on the test sessions.
- Intent-mismatch control (the real stream of a different test sentence): commit rate (a stream-level layer is not expected to detect it).

### 6.3 Statistics
- Bootstrap: one percentile bootstrap, B = 2000, seed 20261112, resampling **test sessions** (clusters), conditional on the fitted pipeline and threshold. As in Paper 1.
- Single rates: exact CP 95 %; zero counts: one-sided 95 % CP upper bound.
- Paired eWPM gain: session-cluster bootstrap CI and an exact sign test over test sessions.

## 7. Success criteria

| id | criterion | pass if |
|---|---|---|
| C1 | P1 pooled wrong-commit | point estimate ≤ 0.05 |
| C2 | P2 per session | no test session has a CP 95 % lower bound above 0.05 |
| C3 | P3 controls | commit rate ≤ 0.01 on the frame-shuffled controls **and** on the uniform controls |

Outcome labels:
- **Confirmed:** C1, C2 and C3 pass, and the test commit rate is above 0.
- **Uninformative:** C1-C3 pass, but the frozen configuration commits no test trial (LTT infeasible, or the threshold excludes all trials). Safety holds trivially; the test says nothing about the commit rule.
- **Not confirmed:** C1, C2 or C3 fails. We report which one and by how much.
- The number of sessions above α (P2, point estimates) is descriptive only. With about 10 test sessions it cannot confirm or exclude per-session control.

We report the outcome whatever it is. There is no second test run. If a bug is found after the test run, we fix it, rerun once, and report both runs and the fix as a deviation.

## 8. Data handling

- Raw data, per-trial decodes, streams and sentences stay in `C:\Users\zhang\bci-data\` (`raw/b2t24/`, `derived/2026-11-13-confirmatory-t12/`, `runs/t12-gru/`, `cache/`). The repo gets only code, configs, aggregate numbers and the frozen trust config (numbers only).
- No sentence text in committed files.

## 9. Files

`run.py` (all stages), `train_decoder.py` (GRU), `config.json`, `results/*.json`, `results/tables.md`, `results.md`.
