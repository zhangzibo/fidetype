---
title: A1 trust-gated zero-shot image identification on THINGS-EEG2 - pre-registration
type: experiment-plan
task: P16-07 (gap 207), experiment A1
updated: 2026-11-24
---

# A1: does the trust gate keep its error bound when an EEG decoder names images of new concepts? (pre-registration)

Written and committed **before** any decoder run and before any test number exists. This commit starts no job. The local GPU runs another task (P15-50); A1 waits for it.

## Question
An EEG decoder (ATM-S, Li et al. 2024) maps one EEG response to a CLIP image embedding. It then picks one of 200 images of concepts that it never saw in training. Published top-1 accuracy is low (28.64 % at 80-trial averaging). The trust gate must decide per input: **COMMIT** (name one image), **OFFER** (show a short set of images that holds the true one with probability 1 - alpha), or **ABSTAIN**. A1 asks:

1. Is the gate **safe** on new concepts? When it commits, is it wrong at most alpha of the time? Does it stay silent on inputs that carry no image information?
2. Is it **useful**? Does it commit on at least 5 % of inputs? Are its sets smaller on real EEG than on null EEG?

## Data and licence (checked 2026-11-24 on the official pages; see references/README.md)
| item | source | licence | use |
|---|---|---|---|
| THINGS-EEG2 (Gifford et al. 2022, NeuroImage 264:119754), 10 subjects; we use subjects 1 and 2 | OSF https://osf.io/3jk45/ (all components: "CC-By Attribution 4.0 International") | CC BY 4.0 | official 17-channel files (reference only) and `image_metadata.npy` |
| 63-channel, 250 Hz re-preprocessing of THINGS-EEG2 + CLIP ViT-H-14 image and text features | Hugging Face dataset `LidongYang/EEG_Image_decode`, commit `dbe34bb2407164f70883c661c76664f0d596e522` | CC BY 4.0 (dataset card) | **primary EEG input** and the candidate embeddings |
| THINGS images (Hebart et al. 2019) | OSF image set component, `LICENSE.txt` | images: research use only, no redistribution | not needed for A1 (the features above are precomputed); never committed |
| ATM code | https://github.com/ncclab-sustech/EEG_Image_decode (commit 49cb3a2) | MIT (c) 2023 DongyangLi | architecture reference; our model code is a re-implementation with attribution |
| NICE code | https://github.com/eeyhsong/NICE-EEG (commit a7709d8) | MIT (c) 2023 Yonghao Song | not used in A1 (fallback decoder for a later run) |

Why the Hugging Face EEG and not the OSF EEG: ATM-S and NICE use 63 channels at 250 Hz, 0-1 s. OSF offers 17 or 63 channels at 100 Hz only. The Hugging Face files come from the ATM preprocessing code (`EEG-preprocessing/` in the ATM repo: epochs -0.2 to 1.0 s, 250 Hz, baseline, multivariate noise normalisation per session, first 50 samples dropped). The loader checks the shapes: train `[16540, 4, 63, 250]`, test `[200, 80, 63, 250]`.

**Data safety.** The `.npy` files are Python pickles (the ATM code writes them with `pickle.dump`). We read them with a restricted unpickler that allows only NumPy array classes, in an isolated Python (`-I`). We then store plain float32 `.npy` arrays (no pickle) in `C:/Users/zhang/bci-data/derived/a1-things-eeg2/`. The `.pt` feature files are read with `torch.load(weights_only=True)`. Pre-check done (no EEG, no decoder): image-to-text top-1 over the HF features is 0.920 (test, 200-way) and 0.777 (train, 1654-way), and 0.005 / 0.009 when shifted by one. So the image and concept orders agree.

## Splits (fixed now)
- **Concepts.** The 1654 training concepts are ranked by `sha256("fidetype-a1-2026-11-24/" + concept)`. The first 200 are **val**, the next 300 are **cal**, the remaining 1154 are **fit** (amended, see "Amendments"). The 200 test concepts are disjoint from all of them (the loader asserts this). The same split is used for both subjects.
- **Units.** One unit is the mean of 4 EEG repetitions of one image.
  - fit / val / cal: one unit per image (its 4 repetitions). cal = 3000 units, val = 2000 units.
  - test: 20 units per image. Unit g = file repetitions 4g .. 4g+3 (the file order of repetitions is a seeded shuffle across the 4 sessions, so each unit mixes sessions as a training image does). 4000 test units.
  - decoder training uses single trials (fit: 11,540 images x 4 = 46,160 trials), as ATM does.
- **cal sub-splits** (by concept, same hash order): the first 100 cal concepts are **order** (1000 units), the other 200 are **certify** (2000 units).
- **Galleries (200-way, as on test).** A test unit is scored against the 200 test images. A val or cal unit is scored against its own image plus 199 other concepts of its split, each with one image (seeded: `[subject, 2026, unit index]`). So every score is a 200-way identification over new concepts.

## Decoder (one run per subject, seed 0)
- **Model:** our re-implementation of ATM-S (MIT code, attribution in the file): channel-token Transformer (each of 63 channels = one token, Linear 250 -> 250, sinusoidal position, a learned subject token, 1 layer, 4 heads, FF 256, dropout 0.25) -> the first 63 tokens -> temporal-spatial conv (40 filters, kernel 25, avg-pool 51 / 5, spatial conv over 63 channels, BN, ELU, dropout 0.5) -> 1440 -> projection to 1024 (Linear, GELU residual, dropout 0.5, LayerNorm).
- **Loss:** symmetric InfoNCE to the CLIP image embedding (weight 0.99) and the concept text embedding (0.01), learned logit scale (start 1/0.07). Our code.
- **Recipe:** AdamW, LR 3e-4, batch 1024, 40 epochs (as ATM Table 8). Checkpoint every epoch; resume from the latest.
- **Epoch choice:** the epoch with the best **val** 200-way top-1 (ties: the earlier epoch). The ATM paper takes the best **test** epoch; we never do that. So our accuracy can be lower than the published number.

## Scores and gate (fitted before any test unit is scored)
- **Similarity:** cosine(EEG embedding, image embedding) over the 200 gallery images.
- **Primary score:** `p_top1` of softmax(similarity / T). T is fitted on val units by NLL (`fidetype.trust.TemperatureScaler`). Secondary (reported only): margin = top-1 minus top-2 cosine.
- **alpha = 0.10, delta = 0.10.** (A project default of 0.05 needs at least 45 error-free commits per certification; with about 5 % commits that is not reachable here. alpha = 0.05 is reported as a descriptive row.)
- **COMMIT** (top-1 image) if `p_top1 >= lambda_hat`. `lambda_hat` comes from `fidetype.trust.precision_bound.precision_ltt` on the commit-threshold grid 1.00, 0.99, ..., 0.00: order items = the order units, test items = the certify units, `target_precision = 0.90`, `delta = 0.10`. If nothing is certified, the gate never commits.
- **OFFER** if not COMMIT and the split-conformal set (LAC score `1 - p`, threshold from `fidetype.trust.conformal.conformal_quantile` on all 3000 cal units, level `1 - alpha`) has at most **10** images. Else **ABSTAIN**.
- The gate parameters (T, `lambda_hat`, conformal threshold) are written to `gate.json` before the test units are scored. The test run reads `gate.json` and changes nothing.

**Assumption, stated now.** The guarantee of LTT and conformal needs cal units and test units to be exchangeable. We treat images as the exchangeable unit. Images of one concept are correlated, and the cal concepts come from the training partition, the test concepts from the test partition. So the design gives no exact guarantee for test concepts; rule (ii) checks it on the test with image-cluster statistics.

## Null inputs (built from test units; 4000 per type; seeded `[subject, 7, type]`)
| id | null | what it keeps | what it removes |
|---|---|---|---|
| N1 | **trial-shuffled**: each of the 63 channels comes from a random test unit (any image) | per-channel waveforms, the evoked response | the cross-channel pattern of one image |
| N2 | **time-reversed** unit | channel covariance, power spectrum | the time course after stimulus onset |
| N3 | **spectrum-matched noise**: FFT phase randomisation with the same random phases for all channels | per-channel power spectrum and cross-channel covariance | any time locking to the stimulus |

## Metrics (test, per subject)
- commit rate = commits / units; **wrong-commit rate** = wrong commits / commits (the precision form; the marginal form wrong commits / units is also reported).
- Bounds: one-sided Clopper-Pearson 95 % upper on unit counts, **and** an image-cluster bootstrap 95 % upper (resample the 200 test images, 10,000 times, seed 0), because the 20 units of one image are correlated.
- Conformal: set size, coverage, OFFER / ABSTAIN rates.
- Decoder: 200-way top-1 and top-5 for 4-trial units and for the 80-trial average (one unit per image; comparable in form to ATM Table 8).

## Pass rules (fixed now; per subject)
| id | rule | pass if |
|---|---|---|
| **V1** (gate for all) | the decoder works | 80-trial-average test top-1 >= 10 % (chance 0.5 %) |
| **(i)** nulls are silent | for each of N1, N2, N3: null commit rate <= alpha, and the CP 95 % upper <= 2 alpha and the cluster-bootstrap upper <= 2 alpha | all three nulls |
| **(ii)** commits are right | real test wrong-commit rate (precision form) <= alpha, CP 95 % upper <= 2 alpha, cluster-bootstrap upper <= 2 alpha, **and** commit rate >= 5 % | all |
| **(iii)** sets are informative | per test image, the mean set size over its 20 units, real vs N1: one-sided Wilcoxon signed-rank test, real < N1, p < 0.01 (200 pairs) | p < 0.01 |
| V2 | conformal coverage on the test | coverage >= 1 - 2 alpha (0.80) |

The draft rule (ii) said "wrong-commit <= alpha". We fix it to the precision form (error among commits), because a gate that commits rarely meets the marginal form even if most commits are wrong.

## Robustness checks (reported; they qualify outcome A)
- **R1 early vs late (drift).** Session of each test repetition: we reconstruct it from the ATM preprocessing seed (20200220; file position p holds original repetition `perm80[p]`, session = `perm80[p] // 20`, with `perm80 = RandomState(20200220).permutation(80)`, the NumPy form of `sklearn.utils.shuffle`). **S0 check** (data only, no decoder): per test image, the mean correlation of repetition pairs from the same reconstructed session is higher than from different sessions (one-sided Wilcoxon over 200 images, p < 0.01). If S0 fails, R1 is "not run (session order unknown)". If S0 passes: early units = 4-repetition means within sessions 1-2 (10 per image), late = sessions 3-4. R1 passes if the wrong-commit rate is <= alpha with CP upper <= 2 alpha in **both** halves. The commit-rate difference is reported.
- **R2 category-cluster hold-out.** k-means (k = 8, seed 0, our code) on the CLIP text embeddings of all 1854 concepts. For each cluster k: refit `lambda_hat` and the conformal threshold on cal units whose concept is **not** in k (same order / certify roles), evaluate on test units whose concept **is** in k. Pool the counts over k. R2 passes if the pooled wrong-commit rate <= alpha with CP upper <= 2 alpha. The decoder is not retrained per cluster (it saw all fit concepts); this tests the gate only.

## Outcomes
| outcome | condition | meaning |
|---|---|---|
| **A** | V1, (i), (ii), (iii) pass on **both** subjects | The gate is safe and useful for zero-shot image identification from EEG. Narrow: 2 subjects, one decoder, within-subject |
| **A-one** | the same on one subject only | Promising; subject-dependent |
| **B** | (i) passes and the error part of (ii) passes, but commits < 5 % on a subject | Safe but too conservative; the decoder is too weak for this gate |
| **C** | (i) fails, or the error part of (ii) fails, on any subject | **Not safe**: the calibration from training-partition concepts does not transfer to test concepts (or nulls commit). A negative result we report as such |
| **D** | (i), (ii) pass, (iii) fails | Commits are safe but the sets carry no more information than on null EEG |
| **N** | V1 fails on a subject | No valid test on that subject |

R1 or R2 failing adds the qualifier "with drift caveat" / "with category caveat". V2 failing is reported next to the outcome.

## Amendments (before any run or result)
- 2026-11-24, while writing the code, before any decoder run: **val grows from 100 to 200 concepts** (fit from 1254 to 1154). Reason: the plan scores val units in a 200-way gallery of "other concepts of its split", which needs at least 200 val concepts. No data had been scored; no other rule changes.
- 2026-11-24, rule detail: if the gate makes **no** commit, the error part of (ii) (and of R1 / R2) passes, because there is no wrong commit; the commit part then fails, so the outcome is B ("safe but too conservative"), not C.
- 2026-11-27, implementation only, before any epoch was trained: the first launch stopped in the first forward pass. The MIOpen BatchNorm kernel does not compile on this ROCm build (`miopenStatusUnknownError`). The run now sets `torch.backends.cudnn.enabled = False`, so PyTorch uses its native kernels (as the T12 runs do). The model, loss, recipe, splits and rules do not change. The runner also writes its exit code to `a1.log` and ends with `TerminateProcess` (ROCm exit hang). No data had been scored.

## Order and stop rules
1. Commit this plan (this commit, alone). 2. Commit the code and CPU tests (synthetic data). 3. CPU: convert the pickles to float32 arrays; S0 check. 4. GPU (after P15-50 frees the GPU): train subject 1, then subject 2. 5. Score val and cal, fit the gate, write `gate.json` (committed to `results/` before step 6). 6. Score test and nulls, apply the rules, write `results/summary.json` (aggregates only) and `results.md`.
- No change of splits, alpha, rules or recipe after this commit. No early stop on a test value. Test units are scored only after `gate.json` is committed.
- **GPU cap:** 6 h local. If the cap is reached, the remaining subject is "not run (cap)".
- Leave-one-subject-out and NICE are **not** part of A1. They need all 10 subjects (about 104 GB at 250 Hz) and get their own plan.

## Compute estimate (our estimate, not measured)
| part | where | estimate |
|---|---|---|
| download (subjects 1-2 at 250 Hz, features, OSF reference files) | network | 23.6 GB, about 30 min |
| pickle -> float32 conversion, S0 check | CPU | about 10 min per subject, peak RAM about 13 GB |
| training, 40 epochs x 46,160 trials, small model (about 3 M parameters) | local RX 7800 XT | 0.5-1.5 h per subject |
| scoring val / cal / test / nulls (about 26,000 units) | GPU or CPU | minutes |
| **total GPU** | | **about 1-3 GPU-h** for 2 subjects (cap 6 h); no rented GPU needed |

## Where it may honestly fail
- 4-trial units are much noisier than the 80-trial averages of the published number; top-1 can be near 5-10 %. Then the gate may certify no threshold (outcome B).
- cal concepts come from the training partition. If test images differ in kind (they were recorded with 80 repetitions and chosen separately), the error bound can break (outcome C). This is the main point of A1.
- Removing 500 concepts from decoder training (val + cal) lowers accuracy against ATM's all-concept training.
- One seed per subject; two subjects. The session reconstruction (R1) relies on the seed in the ATM code.
- The 63-channel 250 Hz files are a third-party re-preprocessing (CC BY 4.0), not the official OSF release.
