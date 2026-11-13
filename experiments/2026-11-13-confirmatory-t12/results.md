---
title: "Confirmatory test of the Paper 1 frozen configuration on participant T12: results"
type: experiment
task: M3-27
updated: 2026-11-13
---

# Confirmatory test on T12: results

Pre-registration: [PROTOCOL.md](PROTOCOL.md), commit `a7cf6244` (pushed before any decoding). All numbers: [results/tables.md](results/tables.md), `results/trust.json`, `results/decoder.json`, `results/prep.json`. Frozen trust config: `results/trust-config-t12.json` (`tcfg-fe35888dac333cff`). Log: `results/run.log`.

## Outcome: **uninformative**

The frozen configuration (guard + LTT max, α 0.05, δ 0.1) passed all three safety criteria, but it **committed no test trial**. By the pre-registered rule (PROTOCOL.md, Sec. 7) the outcome is "uninformative": safety holds trivially, and the test says nothing about the commit rule.

**The cause is the decoder, not the trust layer.** Our T12 decoder gets the right sentence first for 3 of 400 test trials (0.75 %). The T15 decoder of Paper 1 got 39 %. With almost no right top-1 sentences, the correct behaviour of a safe layer is to commit nothing, and it did.

| criterion | result | pass |
|---|---|---|
| C1 pooled wrong-commit ≤ 0.05 | 0/400 = 0.000, CP95 [0.000, 0.009] | yes |
| C2 no test session with CP lower bound > α | 0 of 10 sessions above α; 0 with lower bound > α | yes |
| C3 control commits ≤ 1 % | frame-shuffled 0/400, uniform 0/400 (one-sided CP95 upper 0.0075 each) | yes |
| test commit rate > 0 | 0/400 | **no** → uninformative |

## Data and splits (as pre-registered)

- Willett et al. 2023 / B2T '24 `competitionData` (CC0; Zenodo record 8047896, MD5 checked). 24 sessions (2022-04-28 to 2022-08-25).
- Decoder train 7,900 trials, decoder validation 880 (the last train block of each session), trust pool 880 (the last block of each session).
- Trust pool: fit-A = sessions 1-8 (240), calibration = sessions 9-14 (240), test = sessions 15-24 (400). N = 24 gave the expected 8 / 6 / 10.
- T12 speech rate (decoder-train go periods): 304.0 characters/min.

## Decoder (our own causal GRU-CTC)

| set | n | greedy PER | word CER | WER | sentence exact | truth in n-best |
|---|---|---|---|---|---|---|
| decoder validation | 880 | 0.471 | 0.491 | 0.673 | 0.015 | 0.031 |
| test sessions | 400 | 0.542 | 0.551 | 0.751 | 0.0075 | — |

- Final model: run `t12-gru-r2`, best validation PER 0.470 at epoch 150 (the maximum; status `done`), checkpoint SHA-256 `f41117e7…`. About 65 s per epoch on the RX 7800 XT.
- The word route is the B2T '25 route with the B2T '25 tuned values (no re-tuning on T12).
- Train-subset greedy PER 0.33 (epoch 44, 120 trials, no augmentation) against validation 0.51 at the same epoch. So part of the error is a gap between the train blocks and the later held-out block of the same session.

> **Our take:** This decoder is far below the published T12 results (Willett et al. report a 23.8 % WER with a 125,000-word vocabulary). Likely causes: (1) one fixed normalisation per session (pre-registered, causal) instead of the per-block z-scoring that the field uses against drift inside a session; (2) a small model and only one learning-rate change; (3) our licence-clean word route (CMUdict + Tatoeba unigram + char 6-gram) does not fit Switchboard / OpenWebText sentences. The T15 test of Paper 1 used the published online logits, so it never needed our own decoder.

## Trust layer on the test sessions

| rule | λ | wrong-commit [CP95] | commit rate | eWPM {session bootstrap} |
|---|---|---|---|---|
| LTT max (primary) | 0.30 | 0.000 [0.000, 0.009] | 0.000 | 4.58 {4.27, 4.99} |
| plug-in | 0.30 | 0.000 [0.000, 0.009] | 0.000 | 4.58 |
| same policy, no commits | +inf | 0.000 | 0.000 | 4.58 |
| joint LTT β 0.10 / 0.20 | +inf (infeasible) | 0.000 | 0.000 | 4.58 |
| always commit top-1 (reference) | — | 0.9925 [0.978, 0.998] | 1.000 | 3.92 |
| gaze typing alone | — | 0 | — | 4.11 |

- **Fit:** frame temperature 2.09; sentence temperature 20.0 (the upper limit of the fit: the n-best scores carry almost no information); the conformal threshold is infinite (the set always contains "other"). The policy grid chose `commit_p` 0.30, `commit_max_risk` 0.1 and offer k = 1.
- **LTT:** feasible with λ̂ = 0.00 on 240 calibration trials, because no calibration trial was eligible for a commit (so the loss is 0 at every λ). The max rule kept the grid value 0.30.
- **The guard works on this decoder:** guard AUROC (guard risk vs. wrong top-1) is 0.966 on the test sessions. The guard and the `commit_max_risk` rule block every commit.
- **Speed:** the layer offers the top candidate on every trial. It is +0.47 eWPM [0.13, 0.87] faster than gaze typing alone; this gain comes from the offer path and the simulated user model, not from commits. The paired gain from commits is 0 (no commits).
- **Controls:** no commits on frame-shuffled, uniform or intent-mismatch streams (0/400 each, both rules).

## What this test does and does not show

- It shows that the frozen configuration stays safe with a weak decoder: no wrong commits on real data and no commits on no-signal streams. It also shows that the guard separates wrong from right top-1 sentences on a second participant (AUROC 0.966).
- It does **not** test the LTT bound on a second participant. The bound becomes testable only when a fair share of trials is eligible for a commit. The Paper 1 claim "LTT max keeps wrong commits ≤ α across later sessions" is still supported by one participant only.

## Deviations from PROTOCOL.md

1. **Learning rate (allowed by Sec. 4.3, validation PER only).** First run (`runs/t12-gru`, lr 2e-3, warm-up 500): training loss stuck at about 3.17 from epoch 2, validation PER 0.79 at epoch 2 and 0.84-0.98 in epochs 3-17 (CTC blank collapse). Stopped at epoch 17. Second run (`runs/t12-gru-r2`): lr 5e-4, warm-up 1,000 steps, all else unchanged. The trust pool was not decoded before the decoder was final.
2. **Implementation detail of the planned model.** MIOpen GRU backward fails on this ROCm build (`miopenStatusUnknownError`; the MIOpen dropout kernel does not compile). So cuDNN/MIOpen is off and the 5 GRU layers are separate single-layer GRUs with dropout 0.4 between them (the same model as planned). The Gaussian input smoothing is causal (past bins only). The protocol did not state the kernel side; we chose causal so that the stream claim `latency = 0` stays true.
3. **Training length.** The second run never early-stopped. It ran to the 150-epoch maximum (best epoch = 150). This is within the protocol.
4. **Code fixes before the test run** (dry run on decoder-validation data, `--stage dryrun --limit 60`): empty-session handling in `rec_summary` and `gaze_ewpm`, and `--limit` now takes an even sample over all sessions instead of the first items (the first two dry runs in `run.log` used the old slice). All three are reached only with `--limit`. **After the test run:** the `tables` stage printed non-ASCII text to a cp1252 console and failed after writing `tables.md`. The fix only removed the print; no number changed.
5. **Shared code changed by a parallel task.** During this run, the working tree held an uncommitted, speed-only change by another task to `src/fidetype/lm/phoneme_words.py` (`PronLexicon.nearest` vectorised; the old version kept as `nearest_bruteforce`). The trust-core files were byte-identical to the tag (checked by `run.py`). We checked that `nearest` equals `nearest_bruteforce` on 150 random segments (0 mismatches), so the word route gives the same output as the B2T '25 code path.
6. **Added, not pre-registered:** the "always commit top-1" reference row, the train-subset PER check, and the dry-run files `results/dryrun-*.json` (decoder-validation data, not the trust pool; code check only).

## Next steps

- An informative confirmatory test needs a T12 decoder with a right top-1 sentence for a fair share of trials (T15: 39 %). Options: per-block normalisation inside the decoder-train data, with a causal running estimate for the held-out block; a larger GRU (hidden 1024, patch 32); a better licence-clean word LM.
- The test sessions have now been decoded once. A second attempt must be a new pre-registration (v2) that says so. Only aggregate outcomes were seen, and the layer committed nothing, so the information leak is small. Alternatives are the Dryad `sentences` data (more blocks), or the `competitionHoldOut` blocks once their labels are available.

## Files

- Repo: `PROTOCOL.md`, `config.json`, `t12.py`, `prep.py`, `train_decoder.py`, `decode.py`, `run.py`, `results/`.
- Outside the repo: `C:\Users\zhang\bci-data\raw\b2t24\` (raw); `C:\Users\zhang\bci-data\derived\2026-11-13-confirmatory-t12\` (normalised features, texts, log-probabilities, test records, provenance ledger `ledger-test.jsonl`); `C:\Users\zhang\bci-data\runs\t12-gru\` (run 1), `...\t12-gru-r2\` (final decoder).

Rerun (repo root): `.venv\Scripts\python.exe -I experiments/2026-11-13-confirmatory-t12/prep.py`; GPU `C:\Users\zhang\bci-data\runs\t12-queue.ps1` (train + decode); then `run.py --stage decoder`, `--stage trust` (refuses to overwrite `trust.json`), `--stage tables`.
