---
title: B1 amendment 1 - fill-ins from writing the code, before any iEEG sample is analysed
type: experiment-plan-amendment
task: P16-06 (gap 206), experiment B1
plan: plan.md (commit 97c412b, unchanged)
updated: 2026-11-24
---

# B1 amendment 1 (2026-11-24)

Committed **alone**, **before** any iEEG sample is analysed and before the one-subject dry run. The plan (`plan.md`) stays as it was committed. This page only fills in details that the plan leaves open, and records one change of the step order. No subject, split, alpha, delta, feature, C or pass rule changes.

## What was seen before this amendment
- The plan's metadata (see the plan).
- The download of the plan's file set ran while the code was written (see "Step order"); at this commit about 41 of the 56.8 GB are on disk. Before this commit we read only **headers and text files**, never an iEEG sample:
  - the EDF header fields that the reader needs (signal labels, samples per record, physical and digital ranges) of the downloaded sessions. The header fields "patient" and "recording" were not read;
  - a structure check of the events files and EDF headers of the sessions on disk (70 of 99): per session, the number of `WORD` events, the number of lists with `WORD` and with `REC_START` events, the number of `WORD` events with `sample = -1`, the sampling rate (500 / 1000 / 1600 Hz), the channel count, and the channel labels that all sessions of a subject share;
  - for one B1 session (hash rank 1 or later; not named here), the count of each `trial_type`, which includes the count of `REC_WORD` events, and the `sample` and `onset` values of its `WORD` events.
- No recall rate, no label per word, no feature and no decoder output was computed on B1 data.

## Step order (change)
The plan lists: 2. commit the code, 3. download. The user approved the download on 2026-11-24 and asked for it first. So the download ran while the code was written. No downloaded iEEG sample was analysed before the code and this amendment were committed. The order of all later steps (A0, features, gate fit, `gate.json` commit, test) is as in the plan.

## Fill-ins
| # | plan item | fill-in |
|---|---|---|
| F1 | subject hash `sha256("fidetype-b1-2026-11-24/" + subject_id)` | `subject_id` is the BIDS label with its prefix, e.g. `sub-R1001P`. This reproduces the plan's numbers exactly (74 eligible; 30 chosen; 99 sessions; 56,790,482,460 bytes of bipolar EDF). Without the prefix the numbers are different (104 sessions, 62.85 GB). |
| F2 | cal list hash `sha256("fidetype-b1/" + subject + "/" + session + "/" + list)` | `subject` = `sub-<code>`, `session` = `ses-<n>`, `list` = the decimal list number of the events file. Example key: `fidetype-b1/sub-R1001P/ses-2/7`. Order lists = the first `floor(n_lists / 3)` in hash order. |
| F3 | `rank` in seeds | The position (1..30) of the subject in the final hash-ordered list, after any replacement. `session` in seeds = the BIDS session number. |
| F4 | A0 statistic | Per session, on the raw signal in physical units (no line filter). For each event, the epoch -200 .. +500 ms is baseline-corrected by its own -200 .. 0 ms mean. ERP = mean over events, per channel. Statistic = mean over channels of the mean over 0 .. 500 ms of `abs(ERP)`. Events whose epoch is outside the EDF are skipped. |
| F5 | A0 random times | 300 integer sample indices, uniform between the first and the last `WORD` index of the session (the task period), seed `[rank, session, 0]`. The test is `scipy.stats.wilcoxon(word, random, alternative="greater")` over the paired session values. |
| F6 | words near the edges, words with no index | A word is kept only if the segment -2000 .. +2366 ms (P0 window and main window, each with its 1000 ms buffer) is inside the EDF. A word with `sample = -1` (no EDF index in the events file; one checked session has 72 such words of 180) is dropped by the same rule, also when A0 would use `onset`. The number of dropped words is reported. |
| F7 | line-noise filter | `scipy.signal.butter(4, [58, 62], "bandstop", fs=fs, output="sos")` and `sosfiltfilt`, on the whole continuous channel. |
| F8 | Morlet wavelet | Complex Morlet with `sigma_t = 5 / (2 pi f)`, unit energy, cut at `+- min(1 s, 5 sigma_t)`, linear (not circular) convolution by FFT in single precision. Because of the cut, a window value uses only signal inside its 1000 ms buffers. So we compute the main window and the P0 window on one segment (-2000 .. +2366 ms); this gives the same values as separate 3.366 s epochs (a unit test checks this). Power = `abs(.)^2`; `log10`, then the mean over the window samples. |
| F9 | channels of one subject | One decoder per subject needs the same channels in all its sessions. We use the bipolar channel labels that all sessions of the subject share (in the checked sessions, all sessions of a subject have the same labels). The EDF annotation signal is not a channel. A channel is dropped for the subject if any z-scored feature of it is not finite in any session (SD = 0 gives a non-finite value). This includes the test-session null features. |
| F10 | sessions with few lists | Some sessions have fewer than 25 lists (down to 3 in the checked files). If the cal session of a subject has fewer than 3 lists, it has no order list. Then the Platt step of that subject is fitted on all its cal lists, its cal words count as order words for `b_order` and the LTT ordering, and it has no certify words. This keeps the certify words independent of the fit for every other subject. The number of such subjects is reported. |
| F11 | decoder | `scipy.optimize.minimize(method="L-BFGS-B")`, start at 0, `maxiter` 5000. Platt: unregularised maximum likelihood, L-BFGS-B. |
| F12 | N2, N3a, N3b | Applied to the line-filtered 3.366 s test epoch (-1000 .. +2366 ms), then the same wavelet step. Their features are z-scored over the transformed test session, as the pipeline does for real input. N3a: one random phase offset per epoch and frequency bin, added to the phase of every channel (seed `[rank, 7, 3]`; DC and Nyquist unchanged). N3b: per epoch, one complex Gaussian spectrum `Z` with `E abs(Z)^2 = 1`, the same for all channels (seed `[rank, 7, 4]`); channel noise = inverse FFT of `sqrt(S_c) * Z`, with `S_c` = the channel's mean power spectrum over the test session's epochs. |
| F13 | N4 | For each test word `i`, `j` is uniform over the other words of the same session (independent draws, seed `[rank, 7, 5]`). Word `i` gets the frozen-decoder score of word `j` (the same as giving it the features of `j`). |
| F14 | N1 | One generator `default_rng([k, 2026])` per seed. It permutes the labels session by session, subjects in rank order, sessions in session order. `b_order`, `tau+` and the gate are recomputed from the permuted labels. "Certifies any G+ threshold" = the LTT certified set is not empty. |
| F15 | B0, B0+N | B0 features (12 one-hot serial positions + list number) are z-scored per session like the neural features. The same C, class weights, Platt step and gates. B0+N = the neural and the B0 columns side by side. |
| F16 | bootstrap "95 %" bounds | We use the stricter reading: the two-sided 95 % percentile interval. "Upper" = 97.5th percentile, "lower" = 2.5th percentile, of 10,000 subject-cluster resamples (seed 0). The one-sided 95th / 5th percentiles are reported next to them. Resamples with zero flags have no wrong-flag rate and no precision. They are left out of those two statistics, and their number is reported. |
| F17 | Clopper-Pearson | One-sided 95 % (`fidetype.utils.binomial.cp_upper` with `delta = 0.05`). |
| F18 | V1 t-test | Two-sided `p < 0.01` (the stricter reading; with the mean >= 0.55 condition the direction is fixed). The one-sided p is reported. |
| F19 | qualifier "behaviour explains it" | Applies if the B0 G+ gate certifies a threshold and flags at least as many test words as the neural G+ gate. |
| F20 | `gate.json` | Holds the alpha, delta, C, A0 result, index mode, `b_order`, `tau+`, `tau-`, `lambda+`, `lambda-`, the conformal threshold and the Platt parameters (keyed by rank) for the neural, B0, B0+N and P0 inputs, plus the SHA-256 of the local decoder weights. The test step checks that `results/gate.json` is committed and unchanged, refits the decoders and checks them against the saved weights, and uses the Platt parameters and thresholds from `gate.json`. |
| F21 | compute | 4 worker processes, 1 BLAS thread each, below-normal priority, no GPU (`CUDA_VISIBLE_DEVICES` and `HIP_VISIBLE_DEVICES` empty; no torch import). |

## Dry run
After this commit and before the real run, the code runs once on one subject (rank 1) into a scratch folder that is deleted afterwards. It stops after the gate fit. It scores no test session. If it shows a problem that needs a change of method, a second amendment is committed before the real run.
