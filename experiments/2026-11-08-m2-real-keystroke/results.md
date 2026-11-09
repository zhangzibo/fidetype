# M2-10: the trust core on real MEG decoder output (2026-11-08)

Run (repo root, GPU env, detached, about 40 min in total on a busy machine):

```
C:\venvs\fidetype-rocm\Scripts\python.exe experiments/2026-11-08-m2-real-keystroke/run.py
C:\venvs\fidetype-rocm\Scripts\python.exe experiments/2026-11-08-m2-real-keystroke/run.py --stages lm,trust --redo
```

Settings: [config.json](config.json). Generated tables: [results/tables.md](results/tables.md). Raw numbers: `results/decoder.json`, `results/lm.json`, `results/trust.json`. Run 1 (LM top-1 commit without frame calibration, n-best 20) is kept in `results/run1-uncalibrated-b/`. Streams: `C:\Users\zhang\bci-data\streams\keystroke-sync-2026-11-08\{val,test}\<subject>\*.npz`, labels in `<split>/labels.jsonl`.

## Main finding
On real MEG, the LM beam never finds the true sentence (0 of 209 test trials, also not in the n-best). Always-commit LM top-1 therefore commits a wrong sentence for 100 % of trials, and the text is fluent Spanish in 83 % of them. The trust policy commits 0 % (wrong-commit 1.00 → 0.00) at no measurable speed cost (eWPM 9.61 → 9.70; paired CI of the difference [−0.11, +0.35]). **But the policy does not tell real input from null input. It refuses everything, because no text has enough neural evidence.**

## Setting (read first)
- **Synchronous, oracle key timing.** The key-press times come from the keyboard log (Brain2Qwerty v1 setting). This is **not** a real-time device setting. Each window also uses 0.3 s of signal after the key press.
- The signal is the motor signal of **overt typing**. It is not imagined or attempted typing.

## Data
| item | value |
|---|---|
| Cache | `spanishbcbl/v1`, all blocks in `_index.json` at run time: 20 blocks, 11 subjects (S1 3, S25 4, S3/S11/S15/S19 2, S5/S9/S12/S16/S18 1). Only S25 has all its blocks cached. The preprocessing job is still adding blocks. |
| Train | `split == "train"`, `is_training` trials excluded: 947 trials, 38 204 keys |
| Val | 114 trials, **11 sentences** |
| Test | 209 trials, **17 sentences** (all subjects pooled) |
| Labels | `key_chars` (what the subject typed), 27 classes (a–z, space). Return, backspace and `<?>` keys give no frame. The 40 `is_training` (practice) trials are dropped from all splits. |
| Truth for the trust pipeline | `target_text` (the intended sentence) |

**The data is small.** Test has 209 trials but only 17 different sentences, so trials of one sentence are correlated. We give two 95 % CIs: trial bootstrap `[...]` and sentence-cluster bootstrap `{...}` (1000 resamples).

## Decoder
- Features: −0.2..+0.3 s around each key press, 306 channels, 10 bins of 50 ms (3060 values), z-scored on train.
- Model: per-subject multinomial logistic regression (numpy L-BFGS, L2 penalty chosen by 3-fold grouped CV on train). A shared MLP with a subject embedding (GPU) was worse on val (key acc 0.336 vs 0.419). **Chosen: logistic regression.**
- Stream: one key frame per key press (classifier log-probs, blank mass 1e-3), one blank frame between key presses. `vocab_type="char"`, 28 tokens, `blank_id=0`, `decoder.causal=false`, `decoder.timing="oracle-keystroke"`, no text in `meta`.

| input | split | key acc | greedy CER vs typed | greedy CER vs target |
|---|---|---|---|---|
| real MEG | val | **0.419** | 0.563 | 0.580 |
| real MEG | test | **0.390** | 0.590 | 0.597 |
| control (a): shuffled MEG (key windows of another trial, same subject) | test | 0.111 | 0.774 | 0.774 |
| control (b): labels permuted at train time | test | 0.099 | 0.767 | 0.768 |
| shared MLP (not chosen) | test | 0.308 | 0.648 | 0.653 |

Majority-class chance: 0.13 (space). Both controls are at chance. Per subject, test key accuracy is 0.28 (S12) to 0.48 (S16); see [tables.md](results/tables.md). This agrees with the M1 sanity check (letter 31–49 %).

### Beam + Spanish 6-gram LM (CER/WER vs target)
| beam | lm_weight | val CER | test CER | test WER | true sentence in n-best |
|---|---|---|---|---|---|
| old defaults (beam 16) | 0.5 (best on val) | 0.533 | 0.552 | 1.096 | 0.00 |
| old defaults | 1.0 | 0.562 | 0.557 | 1.081 | 0.00 |
| RETUNED, frame-calibrated | **0.5 (best on val, used below)** | 0.496 | **0.531** | 1.023 | 0.00 |
| RETUNED, frame-calibrated | 1.25 | 0.516 | 0.542 | 0.956 | 0.00 |
| RETUNED, frame-calibrated | 3.0 | 0.602 | 0.622 | 0.925 | 0.00 |

- The LM cuts CER only a little (0.597 greedy → 0.531). A larger weight lowers WER but raises CER: the LM writes more real words, but they are the wrong words.
- WER is near or above 1: the text is wrong almost everywhere.
- Example (test): target `la fuerza atrae el electron primero` → top-1 `la alardeante en las estro tiene el`.
- The frame temperature on val is 1.01–1.02, so the classifier is already calibrated per key, and frame calibration changes almost nothing.

## Trust pipeline (test, 209 trials; fitted on val)
Decoder: RETUNED beam, `lm_weight=0.5`, `n_best=10`, `from_lm_hypotheses` with `"frame"` confidences. Frame T, sentence T, conformal sets and policy thresholds are all fitted on val (`fit(val, val)`); the policy limit is wrong-commit ≤ 0.05.

| policy | eWPM | wrong-commit | silent error | committed CER | COMMIT / OFFER |
|---|---|---|---|---|---|
| (a) always commit greedy | 9.21 [8.97, 9.42] {8.84, 9.57} | 1.00 | 0.081 [0.048, 0.120] | 0.597 | 1.00 / 0 |
| (b) always commit LM top-1 (frame-calibrated) | 9.61 [9.34, 9.86] {9.27, 9.97} | 1.00 | 0.081 [0.048, 0.120] | 0.530 | 1.00 / 0 |
| (b0) as (b), no frame calibration | 9.59 [9.33, 9.85] {9.25, 9.96} | 1.00 | 0.081 | 0.531 | 1.00 / 0 |
| (c) full trust policy | 9.70 [9.52, 9.89] {9.29, 10.15} | **0.00** | **0.000** | — | 0 / 1.00 |
| (d) (c) without calibration | 9.69 [9.52, 9.88] {9.30, 10.14} | 0.010 [0.000, 0.024] | 0.000 | 0.406 | 0.01 / 0.99 |
| (e) (c) without guard | 9.70 [9.52, 9.89] {9.29, 10.15} | 0.00 | 0.000 | — | 0 / 1.00 |
| (f) guard = n-best inconsistency only, plus p_top1 | 9.70 [9.52, 9.89] {9.29, 10.15} | 0.00 | 0.000 | — | 0 / 1.00 |

- Paired difference (c) − (b): eWPM [−0.11, +0.35] trial CI, {−0.07, +0.28} sentence CI; wrong-commit −1.00; silent error [−0.12, −0.05].
- **The eWPM numbers come only from the simulated user.** No candidate is ever right, so every sentence is communicated through the user's corrections. (c) OFFERs the top-1 (fitted `offer_max_k=1`, final fallback "offer") and the user always edits it. The time costs are the default `UserConfig` assumptions.
- (c), (e) and (f) are identical: no text passes the commit gate, so the guard variant does not matter. The Pareto runs at limits 0.02, 0.1 and 0.2 are also identical.

### Calibration, conformal sets, guard (test)
| metric | (c) trust | (d) no calibration |
|---|---|---|
| frame T / sentence T | 1.018 / 20.0 (grid edge) | 1 / 1 |
| char ECE before → after | 0.037 → 0.042 | 0.037 |
| sentence ECE before → after | 0.182 → 0.103 | 0.180 |
| conformal coverage (target 0.9) | 0.00 | 0.00 |
| mean set size | 10 (the full list; q = inf) | 10 |
| n-best miss rate | **1.00** | 1.00 |
| word-level conformal coverage / set size | 0.27 / 2.19 | — |

- Sentence calibration pushes the temperature to the grid limit. No top-1 is ever right, so the best calibrated posterior is as flat as possible.
- Conformal coverage is 0 because the truth is never in the list. The calibrator makes the set the full list, as it should.

**Guard AUROC.** The harness AUROC for "top-1 wrong" is undefined: every top-1 is wrong. We use two other targets instead:

| signal | AUROC: top-1 CER above median | Spearman with top-1 CER | AUROC: shuffled MEG vs real | AUROC: uniform vs real |
|---|---|---|---|---|
| combined risk (c) | **0.848** | 0.66 | 0.49 | 0.98 |
| low-evidence fraction | 0.848 | — | 0.49 | 0.98 |
| n-best inconsistency (= risk of f) | 0.516 | 0.07 | 0.51 | 0.64 |
| −p_top1 | 0.552 | 0.10 | 0.52 | 0.26 |

- On real MEG, the evidence term carries the guard. Inconsistency and p_top1 are near chance. **This is the opposite of the simulator**, where inconsistency (0.78–0.90) and p_top1 (0.75–0.91) were the better signals.
- **No signal tells shuffled MEG from real MEG (AUROC 0.49–0.52).** The shuffled-MEG stream is real classifier output for real key presses, so its confidence statistics are the same. Only the uniform stream is detected.

### Word-level alternatives (test, policy b/c lists)
| unit | share of true words found |
|---|---|
| top-1 sentence | 0.264 |
| top-3 per-word slot (`word_alternatives`) | 0.291 |
| best of the top-3 sentences | 0.289 |

Per-word top-3 choices add only 2.7 points. The alternatives are wrong words too.

## Null-input audit (test streams, 209 each)
"Fluent" = at least 2 words and ≥ 80 % of the words in the Tatoeba Spanish lexicon (77 396 words).

| policy | real: fluent / fluent and COMMITted | shuffled MEG | frame-shuffled stream | uniform stream |
|---|---|---|---|---|
| (a) greedy commit | 0.005 / 0.005 | 0.000 | 0.010 | 0.000 |
| (b) LM top-1 commit | 0.83 / **0.83** | **0.84** | **0.86** | **1.00** |
| (b0) LM top-1, no calibration | 0.82 / 0.82 | 0.83 | 0.85 | 1.00 |
| (c) trust | 0.83 / **0.00** | **0.00** | **0.00** | **0.00** |
| (d) no calibration | 0.82 / 0.014 | 0.014 | 0.014 | 0.019 |
| (e) no guard | 0.83 / 0.00 | 0.00 | 0.00 | 0.00 |
| (f) inconsistency + p_top1 | 0.83 / 0.00 | 0.00 | 0.00 | 0.00 |

- The LM writes fluent Spanish from any input. On real MEG the fluent output is also always wrong. **For this decoder, real output and hallucination look the same**: 83 % fluent on real input, 84 % on shuffled MEG.
- The trust policy commits none of it. Without calibration, (d) commits fluent text for 1–2 % of null inputs.

## Comparison with the simulator (M2, [results](../2026-11-08-m2-trust-sim/results.md))
| claim | simulator | real MEG (this run) |
|---|---|---|
| Large cut in wrong commits | 0.29–0.47 → 0.02–0.09 | 1.00 → 0.00 |
| Small speed cost | −1.5 to −3.7 eWPM (7–16 %) | +0.09 eWPM, CI includes 0 |
| No fluent commits on null input | 0 % (trust) vs 98–100 % (always commit) | 0 % vs 84–100 % |
| Guard discriminates | inconsistency and p_top1 best | only the evidence term works; nothing separates shuffled MEG from real |
| n-best recall | miss rate 0.28–0.37 | miss rate 1.00 |

> **Our take:** The claim "far fewer wrong or hallucinated commits for a small speed cost" holds in its numbers, but here it is a degenerate case. The decoder is far below the regime the simulator modelled (simulator CER 0.03–0.06 after the LM; here 0.53). With no correct candidate, the best policy is to commit nothing, and the trust core finds that. This is a useful safety result: the core did not let the LM's fluent text through. It is not yet evidence that the core can pick the correct commits from the wrong ones on real data. To test that, we need a decoder whose LM top-1 is right for a real share of sentences (Brain2Qwerty v1 MEG reports CER about 0.32 with a deep model). Then the commit gate will have something to pass.

## Limits
- Oracle key timing (synchronous v1 setting). The stream length tells the number of key presses.
- Overt typing: the classifier reads the motor signal of the finger movement.
- Few sentences: 17 test and 11 val sentences. Calibration and the policy fit use the same 114 val trials. The sentence temperature sits at its grid limit.
- A linear decoder only (key accuracy 0.39). The shared MLP was not tuned (one setting, 40 epochs).
- 9 of 11 subjects are only partly cached (1–3 of their blocks). S25 is complete.
- eWPM depends on the simulated user's time costs. With no correct candidate, it measures correction time only.
- One seed. The LM was trained without the SpanishBCBL sentences, so it does not know the test sentences.
