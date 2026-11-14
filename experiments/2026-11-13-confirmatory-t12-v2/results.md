---
title: "Confirmatory test v2 of the Paper 1 frozen configuration on participant T12: results"
type: experiment
task: M3-28
updated: 2026-11-13
---

# Confirmatory test v2 on T12: results

Pre-registration: [preregistration.md](preregistration.md), commit `f9741df` (pushed before the v2 decoder decoded any trust-pool trial). All numbers: [results/tables.md](results/tables.md), `results/trust.json`, `results/decoder.json`, `results/lm-tune.json`, `results/dryrun-trust.json`. Frozen trust config of this run: `results/trust-config-t12.json` (`tcfg-9fb4c81c5931e00c`). Log: `results/run.log`.

## Outcome: **uninformative** (again)

The decoder is much better than in M3-27, but the frozen configuration committed **1 of 400** test trials (the commit was right). The informative condition needs at least 21 commits (pre-registration Sec. 7). C1, C2 and C3 pass. So by the pre-registered rule the outcome is "uninformative": the LTT bound is still not tested on a second participant.

| criterion | result | pass |
|---|---|---|
| C1 pooled wrong-commit ≤ 0.05 | 0/400 = 0.000, CP95 [0.000, 0.009] | yes |
| C2 no test session with CP lower bound > α | 0 of 10 sessions above α | yes |
| C3 control commits ≤ 1 % | frame-shuffled 0/400, uniform 0/400 (one-sided CP95 upper 0.0075 each) | yes |
| I informative: ≥ 21 test commits | 1/400 | **no** → uninformative |

**Our pre-registered prediction was wrong.** From the validation dry run we predicted "not confirmed" (C3 fails by commits on the uniform controls). On the trust pool this did not happen. Reason: the frozen recipe fits the policy grid on fit-A. On the trust-pool fit-A it chose `commit_max_risk` 0.1 (a strict guard limit); on the validation dry run it had chosen 1.0 (no guard limit). With the strict limit the layer committed almost nothing, on real streams and on controls alike.

## Decoder v2 (our own causal GRU-CTC)

| set | n | greedy PER | word CER | WER | sentence exact | truth in n-best |
|---|---|---|---|---|---|---|
| decoder validation (v2) | 880 | 0.294 | 0.306 | 0.427 | 0.095 | 0.145 |
| test sessions (v2) | 400 | **0.269** | 0.272 | 0.387 | **0.0775** (31/400) | — |
| test sessions (M3-27) | 400 | 0.542 | 0.551 | 0.751 | 0.0075 (3/400) | — |

- Run `t12-v2-final`: best validation greedy PER 0.2929 at epoch 102 of 120 (status `done`), checkpoint SHA-256 `5317b060…`. About 97 s per epoch on the RX 7800 XT; 3 h 16 min training.
- What helped (validation PER only, pre-registration Sec. 4.5): causal rolling normalisation over the 20 previous trials (0.580 → 0.510 at epoch 10), then GRU hidden 1024 + patch 32 (0.391 at epoch 10). Lr 0.02 with Adam ε 0.1 collapsed (blank only).
- Word trigram term (Tatoeba, KN, β 2.0): validation sentence exact 0.068 → 0.095.
- Target "val PER clearly below 0.30": reached only just (0.293). Overfitting is large (train-subset PER 0.16 at epoch 20; validation CTC loss rose after epoch 20 while PER still fell).

## Trust layer on the test sessions

| rule | λ | wrong-commit [CP95] | commit rate | EAC | eWPM {session bootstrap} |
|---|---|---|---|---|---|
| LTT max (primary) | 0.30 | 0.000 [0.000, 0.009] | 0.0025 (1/400) | 0/1 | 7.14 {6.63, 7.65} |
| plug-in | 0.30 | 0.000 [0.000, 0.009] | 0.0025 | 0/1 | 7.14 |
| same policy, no commits | +inf | 0.000 | 0.000 | — | 7.13 |
| joint LTT β 0.10 / 0.20 | +inf (infeasible) | 0.000 | 0.000 | — | 7.13 |
| always commit top-1 (reference) | — | 0.9225 [0.892, 0.947] | 1.000 | 369/400 | 6.67 |
| gaze typing alone | — | 0 | — | — | 4.11 |

- **Fit (frozen recipe):** frame temperature 2.47; sentence temperature 20.0 (the upper limit again); conformal q 0.910; policy grid `commit_p` 0.30, `commit_max_risk` 0.1, offer k 1.
- **LTT:** feasible with λ̂ 0.00 on 240 calibration trials, because no calibration trial was eligible for a commit (loss 0 at every λ). The max rule kept 0.30.
- **Guard AUROC** (guard risk vs. wrong top-1, test): 0.792 (M3-27: 0.966 on a decoder that was almost always wrong).
- **Speed:** +3.02 eWPM [2.56, 3.49] over gaze typing alone (7.14 vs 4.11). The gain comes from the offer path (the user accepts a right top-1 offer), not from commits (+0.001 eWPM from commits).
- **Controls:** 0/400 commits on frame-shuffled and uniform streams; intent mismatch 1/400 (one wrong commit; this control is not in C3, and a stream-level layer is not expected to catch it).
- **Empty-text commits (new secondary):** 0 on the test trials and on all controls.

## Validation dry run (before the pre-registration) against the test run

| item | validation dry run | test run |
|---|---|---|
| fitted `commit_max_risk` | 1.0 | 0.1 |
| LTT λ̂ / calibration commit rate | 0.30 / 0.046 | 0.00 / 0.000 |
| "test" commits (wrong) | 22 (11) | 1 (0) |
| uniform-control commits (empty text) | 335 (320) | 0 (0) |
| frame-shuffled-control commits | 6 | 0 |

> **Our take:** The frozen recipe is not stable across fit sets of 240 trials. One discrete grid choice (`commit_max_risk` 1.0 vs 0.1) moves the layer from "commits 5 % with 50 % EAC and fails the uniform control" to "commits nothing". Both runs keep the pooled wrong-commit rate below α, but the dry run shows that the frozen configuration **can** commit on no-signal input, mostly empty texts. Our pre-registration's explanation ("an empty candidate gets guard risk 0") is a reading of the code that we did not test: in the test run the uniform streams committed nothing even with the strict limit, so another part of the policy also blocks them. This needs a direct check. The LTT claim of Paper 1 still rests on one participant (T15).

> **Our take:** The decoder is now the smaller problem; the word LM is the larger one. Test PER 0.27 gives only 7.75 % right sentences with our licence-clean Tatoeba LMs. T15 (PER 0.097) gave 39 %. Willett et al. used a large word n-gram. An informative T12 test needs about 10× more eligible trials: a stronger word LM (large licence-clean corpus) or a different trust-pool design (more calibration and test trials, e.g. the Dryad `sentences` blocks).

## Deviations from preregistration.md

1. **Pre-registration hash in `config.json`.** After commit `f9741df` we wrote its hash into `config.json` (`preregistration_commit`). Sec. 8 allows this; no other file changed before the test run.
2. **Prediction wrong (not a protocol deviation).** Sec. 7.1 predicted "not confirmed". The outcome is "uninformative" (see above). We report it as found.
3. **Shared code changed by a parallel task.** Commit `2ac7b0e` (M4-10, LRU-bounded caches in `src/fidetype/lm/phoneme_words.py`, "decisions unchanged") landed while this task ran; the validation dry runs may have used its uncommitted form, the test run used the committed form. The trust-core files were byte-identical to tag `paper1-v4-frozen-config` (checked by `run.py`).
4. **Pilot dry run with wrong frame times.** The pilot dry run (`results/pilot-p3-*`, decoder-validation data only) used frame times for a 14-bin patch although the pilot model used 32 bins. We fixed `run.py` before the final runs (frame time = end of the decoder's patch, from the checkpoint config). The test run used the fixed code.
5. **Not done:** time masking, layer normalisation, other LMs (time budget). The pilot `t12-v2-p1-roll` stopped at epoch 11 and `t12-v2-p2-roll-opt` at epoch 4 by hand (decision clear).

## Files

- Repo: `preregistration.md`, `config.json`, `t12.py`, `prep.py`, `train_decoder.py`, `decode.py`, `run.py`, `wordlm.py`, `lm_tune.py`, `results/`.
- Outside the repo: `C:\Users\zhang\bci-data\derived\2026-11-13-confirmatory-t12-v2\` (normalised features, texts, log-probabilities, test records, ledger); `C:\Users\zhang\bci-data\runs\t12-v2-*\` (pilots and final decoder; `t12-v2-final\best.pt`); queue `C:\Users\zhang\bci-data\runs\t12v2-queue.ps1` + `t12v2-jobs.json`; word LM cache `C:\Users\zhang\bci-data\lm\eng_tatoeba_word3_kn.pkl`.

Rerun (repo root): `.venv\Scripts\python.exe -I experiments/2026-11-13-confirmatory-t12-v2/prep.py`; GPU queue `t12v2-queue.ps1` (training); `decode.py --run t12-v2-final --parts val,pool`; `lm_tune.py`; `run.py --stage decoder`, `--stage dryrun`, `--stage trust` (refuses to overwrite `trust.json`), `--stage tables`.
