---
title: B1 calibrated "good encoding moment" detector on Penn RAM FR1 iEEG - pre-registration
type: experiment-plan
task: P16-06 (gap 206), experiment B1
updated: 2026-11-24
---

# B1: can a calibrated gate say "this word will likely be remembered" from iEEG, with a bound on wrong flags? (pre-registration)

Written and committed **alone**, **before** any iEEG data is downloaded or analysed. This commit starts no job. B1 runs on the CPU only. The GPU is not used.

**What was seen before this plan.** Metadata from the OpenNeuro API (file names, sizes, subject and session lists), the dataset `README`, `CHANGES`, `dataset_description.json`, `participants.tsv`, and the format files of one session that is **not** in the B1 subject set (`sub-R1001P ses-0`: `events.tsv`, `events.json`, `acq-bipolar_ieeg.json`, `acq-bipolar_channels.tsv`). From that events file: 300 `WORD` events in 25 lists; 53 of the 300 words match a `REC_WORD` of the same list. No iEEG sample was read.

## Question
Intracranial encoding classifiers detect a **state**: "the word shown now will likely be recalled later". Published accuracy is modest (mean AUC 0.61 in Ezzyat et al. 2018; see [the wiki page](../../wiki/questions/beyond-words.md#memory-state)). B1 asks:

1. Is a calibrated gate **safe**? When it flags a "good encoding moment", is the share of wrong flags at most the certified bound? Does the certificate fail to appear when the labels carry no signal (permuted labels) and when the input is noise?
2. Is it **useful**? Does it flag at least 5 % of words, with a precision above the base recall rate?

B1 reads a memory **state**, not memory **content**. No result of B1 can say what a person remembers.

## Data and licence (checked 2026-11-24 on the official API; see references/README.md)
| item | source | licence | use |
|---|---|---|---|
| Penn RAM "Delayed Free Recall of Word Lists" (FR1), BIDS 1.7.0, snapshot 3.1.0 (2024-04-22), DOI `10.18112/openneuro.ds004789.v3.1.0` | OpenNeuro https://openneuro.org/datasets/ds004789 | **CC0** (`dataset_description.json`: `"License": "CC0"`) | iEEG + word events |
| whole snapshot | same | same | 280 subjects, 7,425 files, **618.8 GB** (618,808,962,711 bytes). Not downloaded |
| B1 subset (below) | same | same | **bipolar EDF + events / channels / electrodes files only** of 30 subjects, 99 sessions: **56.79 GB** (56,790,482,460 bytes of bipolar EDF; the text files add < 0.1 GB) |

The README asks users to re-reference monopolar files. We use the files labelled `acq-bipolar` (already re-referenced by the data owners, "according to a paired scheme"). 23 of the 280 subjects have no bipolar EDF. The README holds a contact address; we never copy it.

**Data safety and privacy.** Files go to `C:/Users/zhang/bci-data/raw/penn-ram-fr1/` (outside the repo). The EDF header fields "patient" and "recording" are never copied (our EDF reader drops them). Only aggregate numbers go into the repo: no per-word, per-channel or per-electrode-location output. Subject codes appear only in the local run logs, not in committed results (committed results use the hash rank 1..30).

## Subjects (fixed now)
- **Eligible:** subjects with at least 3 sessions that have a bipolar EDF: **74** subjects (49 with 3, 18 with 4, 2 with 5, 3 with 6, 2 with 8 sessions; counted from the API file tree on 2026-11-24).
- **Chosen:** the first **30** eligible subjects ranked by `sha256("fidetype-b1-2026-11-24/" + subject_id)`. The list is written by the download script and the order never changes. Bipolar EDF per subject: 0.60 - 3.11 GB.
- If a chosen session fails to download or to parse (header error, no `WORD` events), that session is dropped; if a subject then has fewer than 3 sessions, the subject is replaced by the next subject in the hash order. Every replacement is logged and reported.

## Labels (fixed now)
- **Unit:** one `WORD` event (not `PRACTICE_WORD`). Lists with no `REC_START` event are dropped.
- **Label:** `recalled = 1` if the word's `item_name` (upper case, stripped) equals the `item_name` of a `REC_WORD` event of the **same list** in the same session; else 0. Repeats count once; intrusions and `REC_WORD_VV` are ignored. This is the standard "subsequent memory" label (the events file has no recalled column, so we derive it).

## Alignment (check A0; data only, labels not used)
The format file shows that `sample` and `onset * fs` differ by a near-constant offset (282,341 - 282,349 samples in `sub-R1001P ses-0`). So the events time base needs a check.
- **Primary index:** the `sample` column is the EDF sample index of the event.
- **A0 check, per session:** mean over channels of the absolute event-related potential (0 - 500 ms after the index, baseline -200 - 0 ms) for `WORD` events, against the same statistic at 300 random times inside the session (seeded `[rank, session, 0]`). A0 passes if, across all sessions, the `WORD` statistic is larger in a one-sided Wilcoxon signed-rank test, p < 0.01.
- If A0 fails with `sample`, we repeat A0 once with `round(onset * fs)` and use it if it passes. If neither passes, B1 stops with outcome **N** ("event timing not usable").

## Features (Ezzyat et al. 2018, Methods; our own code)
Per bipolar channel and word:
1. Line-noise filter: 4th-order Butterworth band-stop 58 - 62 Hz, zero phase (`scipy.signal`, BSD).
2. Morlet wavelet power at **8 frequencies, log-spaced 3 - 180 Hz**, wave number 5, on the window **0 - 1366 ms** after word onset, with a 1000 ms buffer of real signal on both sides (the buffer is cut after convolution). Each session's own sampling rate is used (500, 1000 or 1600 Hz).
3. `log10` power, mean over time in the window -> 8 features per channel.
4. z-score each feature over the words of its own session (mean and SD from that session).
Channels with any NaN, or SD = 0 in any session of the subject, are dropped for that subject. Features = 8 x channels.

## Splits per subject (fixed now)
Sessions are sorted by session number. With n sessions (n >= 3):
- **train:** sessions 1 .. n-2 (in BIDS numbering: the first n-2 sessions).
- **cal:** session n-1.
- **test:** session n.
One frozen decoder per subject is trained on train and scores both cal and test. So cal and test scores come from the same model; the only difference between them is the next-session drift, which is what a deployed system meets. (With n = 3 the decoder sees one session only; Ezzyat trained on at least 3. Our AUC can be lower; this is stated now.)
- **cal sub-split by list:** the lists of the cal session are ranked by `sha256("fidetype-b1/" + subject + "/" + session + "/" + list)`; the first third (rounded down) are **order** lists, the rest are **certify** lists.

## Decoder (one per subject)
- L2-penalised logistic regression, **our NumPy / SciPy code** (L-BFGS). Objective `0.5 * ||w||^2 + C * sum_i c_i * logloss_i`, **C = 2.4e-4** (Ezzyat's value), class weights `c_i` inverse to class frequency in the training words (`n / (2 n_class)`). The intercept is not penalised (LIBLINEAR penalises it; this is our only known deviation).
- **Score:** the decoder logit.
- **Calibration:** per subject, Platt scaling (2-parameter logistic of the logit) fitted on that subject's **order** words only -> `p_recall`.

## Gate (fitted on cal only, before any test word is scored)
- **alpha = 0.10, delta = 0.10.**
- `b_order` = pooled recall rate of all order words (30 subjects).
- **G+ (primary), "good encoding moment":** FLAG if `p_recall >= lambda+`. Wrong flag = the word is not recalled. Target precision `tau+ = b_order + 0.10`. `lambda+` from `fidetype.trust.precision_bound.precision_ltt` on the grid 1.00, 0.99, ..., 0.00: `order_items` = order words, `test_items` = certify words, pooled over subjects (`PrecisionItem(can_commit=True, p_top1=p_recall, wrong=not recalled)`), `target_precision = tau+`, `delta = 0.10`. If no threshold is certified, the gate never flags.
- **G- (secondary), "poor encoding moment"** (the trigger type of Ezzyat's closed loop): the same on `p_forget = 1 - p_recall`; wrong flag = the word is recalled; `tau- = (1 - b_order) + 0.05`.
- **OFFER (secondary):** binary split-conformal set (LAC score, `fidetype.trust.conformal.conformal_quantile` on all certify words, level 1 - alpha). Reported only: share of singleton sets, coverage.
- `lambda+`, `lambda-`, `tau+`, `tau-`, the Platt parameters and the conformal threshold are written to `gate.json` and committed to `results/` **before** the test sessions are scored. The test step reads `gate.json` and changes nothing.

**Assumption, stated now.** The LTT guarantee needs exchangeable cal and test words. Cal and test are different sessions (next-day drift) and words in one list are correlated. So the design gives no exact guarantee on test; rules (ii) and (iv) check it on test with subject-cluster statistics.

## Null controls
| id | null | how | role |
|---|---|---|---|
| **N1** | **label-permuted, end to end** | permute `recalled` within each session (all sessions, also test), then run the **whole** pipeline (decoder, Platt, LTT, test). 20 seeds `[k, 2026]`, k = 0..19 | the certificate's validity: with no signal, LTT should certify nothing in at least 1 - delta of runs |
| **N2** | **time-reversed** epoch | reverse the time axis of each test epoch (window + buffers) before the wavelet step; frozen decoder and gate | invariance check (see below) |
| **N3a** | **spectrum-matched noise, per epoch** | FFT phase randomisation of each test epoch, the same random phases on all channels (keeps each channel's power spectrum and the cross-channel covariance); seeded `[rank, 7, 3]` | invariance check (see below) |
| **N3b** | **spectrum-matched noise, session mean** | Gaussian noise shaped to each channel's **mean** power spectrum over the test session's word epochs, common random phases across channels; one noise epoch per word, labels kept; features z-scored over the noise session as in the pipeline; seeded `[rank, 7, 4]` | safety on input with no word-specific information |
| **N4** | **shuffled signal** | each test word gets the features of a random other word of the same session (seeded `[rank, 7, 5]`); labels kept; frozen decoder and gate | precision must fall to the base rate |
| **N5** | **uniform score** | `p_recall` = `b_order` for every test word | trivial reference: no flag unless `lambda+ <= b_order` |

**Why N2 and N3a are not safety nulls here.** The Ezzyat features are log power averaged over the window. Time reversal and per-epoch phase randomisation keep each channel's power spectrum, so they keep these features (up to wavelet edge effects). We therefore predict, now, that N2 and N3a give nearly the same flags as real input. They test where the information is (in time-averaged power, not in the time course), not whether the gate is safe. N3b and N4 remove the word-specific information and are the safety nulls for this feature set.

## Baselines and controls (reported; they qualify the outcome)
- **B0 behaviour only:** the same pipeline on serial position (12 one-hot) + list number (linear) instead of iEEG features. If B0's G+ certifies and flags at least as many test words as the neural G+, the outcome gets the qualifier "behaviour explains it".
- **B0+N:** neural + behaviour features (reported only).
- **P0 pre-stimulus window:** the same features on -1000 - 0 ms before word onset (reported only; pre-stimulus state is known to predict memory, so this is a description, not a confound test).

## Metrics (test, pooled over 30 subjects; per-subject values in the local log only)
- AUC per subject (test session), mean and SD; one-sample t-test against 0.5.
- G+: flag rate (flags / words), **wrong-flag rate** among flags (1 - precision), precision minus the test base rate. Same for G-.
- Bounds: one-sided Clopper-Pearson 95 % on word counts, **and** a subject-cluster bootstrap 95 % (resample the 30 subjects, 10,000 times, seed 0), because words of one subject are correlated.
- Comparison with the published numbers (reported only): Ezzyat 2018 mean AUC 0.61 (NoStim lists of closed-loop sessions, N = 29 stimulation targets); Li, Pazdera & Kahana 2024 scalp-EEG mean AUC 0.59 / 0.60.

## Pass rules (fixed now)
| id | rule | pass if |
|---|---|---|
| **A0** | event timing | as above |
| **V1** | the decoder works | mean test AUC over subjects >= 0.55 and one-sample t-test p < 0.01 |
| **(i)** | certificate is valid with no signal | N1: at most **4 of 20** permuted runs certify any G+ threshold (4 = the 95 % quantile of Binomial(20, 0.10)) |
| **(ii)** | real flags keep the bound | G+ wrong-flag rate on test <= `1 - tau+`, and the subject-cluster bootstrap 95 % upper <= `1 - tau+ + 0.10` |
| **(iii)** | the gate is useful | G+ flag rate >= 5 % of test words, and the subject-cluster bootstrap 95 % lower bound of (precision - test base rate) > 0 |
| **(iv)** | noise does not flag | N3b: flag rate <= alpha, CP 95 % upper <= 2 alpha, cluster-bootstrap upper <= 2 alpha; N4: precision among flags <= test base rate + 0.05 (point) |

If G+ certifies no threshold, (ii) and (iv) pass (no flag, no wrong flag) and (iii) fails: outcome B. If the real flag rate is itself <= alpha, the N3b part of (iv) is weak; we then also report the N3b / real flag-rate ratio.

## Outcomes
| outcome | condition | meaning |
|---|---|---|
| **A** | A0, V1, (i), (ii), (iii), (iv) pass | A calibrated memory-state gate is safe and useful on new sessions. Narrow: 30 subjects, one decoder family, iEEG in epilepsy patients |
| **B** | (i), (ii), (iv) pass, (iii) fails | Safe but too weak: "detector too weak to certify" at this AUC. An honest negative |
| **C** | (i), (ii) or (iv) fails | **Not safe**: the certificate breaks across sessions, appears with no signal, or noise flags |
| **N** | A0 or V1 fails | No valid test |

G- results, OFFER sets, B0, B0+N, P0, N2, N3a and N5 are reported next to the outcome. The qualifier "behaviour explains it" (B0) is added where it applies.

## Order and stop rules
1. Commit this plan (this commit, alone). 2. Commit the code and CPU tests on synthetic data (`b1data.py`, `b1feat.py`, `b1gate.py`, `test_b1.py`). 3. Download the 30-subject subset (sizes checked against the OpenNeuro API). 4. A0 check. 5. Features, train, cal, fit the gate; commit `results/gate.json`. 6. Score test and nulls; write `results/summary.json` (aggregates only) and `results.md`.
- No change of subjects, splits, alpha, delta, features, C or rules after this commit, except by a dated amendment committed **before** the step it changes, with the reason. No early stop on a test value.
- **Download cap:** 60 GB for this plan. **CPU only**, low priority, at most 4 worker threads (other jobs run on the machine).

## Compute estimate (our estimate, not measured)
| part | where | estimate |
|---|---|---|
| download, 30 subjects, bipolar EDF + text files | network | 56.8 GB, about 0.5 - 1.5 h |
| EDF read + filter + wavelets (99 sessions, about 300 words each, about 100 channels, 8 frequencies, 3.4 s windows) | CPU | about 0.5 - 1 h (I/O bound) |
| decoders, Platt, LTT, nulls (N1: 20 x 30 decoders) | CPU | minutes |
| **total** | | **about 1 - 3 h CPU, no GPU, $0**; disk 57 GB raw + < 1 GB derived |

## Risks and where it may honestly fail
- **Weak signal.** At AUC about 0.6, few words reach a calibrated precision of `b + 0.10`. Outcome B is likely. That is still a result: it measures how often an honest memory-state detector may speak.
- **Training on 1 - 2 sessions.** Most subjects have 3 sessions, so the decoder sees one session. AUC may fall below V1 (outcome N).
- **Session drift.** Cal and test are different days. The bound may not hold (outcome C). This is the main safety question.
- **Behaviour confound.** Serial position (primacy) predicts recall. B0 says how much the iEEG adds.
- **Event timing.** `sample` vs `onset` differ; A0 guards this.
- **Mixed hardware.** Six or more clinical sites, 500 - 1600 Hz; per-session z-scoring and per-subject decoders absorb most of it.
- **Population.** Epilepsy patients with clinical electrode placement. No claim for healthy people or scalp EEG.
- **Labels.** "Recalled in this list's free recall" is a narrow memory measure.
