---
title: Open benchmark v0.1
type: concept
tags: [benchmark, leaderboard, evaluation, ewpm, conformal, neuraltextstream, licences]
sources: [brain-to-text-25-copytask, toronto-semg-typing]
updated: 2026-11-11
---

# Open benchmark v0.1

## What it is
The **Fidetype open benchmark** scores neural text entry from [NeuralTextStream](../../spec/neuraltextstream-v0.1.md) files. It is milestone M5 (tasks M5-01 to M5-03). The scorer needs no decoder code. It ships no data and no weights.

- Code: `src/fidetype/benchmark/` (`python -m fidetype.benchmark`).
- How to submit: [`benchmark/README.md`](../../benchmark/README.md).
- Leaderboard (generated): [`benchmark/site/index.html`](../../benchmark/site/index.html), [`leaderboard.md`](../../benchmark/site/leaderboard.md).
- Licence note: [`LICENSES/DATA.md`](../../LICENSES/DATA.md).

## Parts
| Part | Module | Content |
|---|---|---|
| Registry | `registry.py` | Datasets (source URL, licence, version, checksum, download steps, non-commercial flag) and tracks (split file, normaliser, CI unit, user model) |
| Splits | `splits.py`, `splits/v0.1/*.json` | Fixed splits as trial ids + cluster labels + SHA-256 of the truth text. No text |
| Prepare | `prepare.py` | Rebuilds the local truth from the user's downloaded data and checks it against the split hashes |
| Submission | `submission.py` | NTS stream per trial + final `hypothesis` event with `fidetype.action` (commit / offer / abstain) + `submission.json` manifest (weights licence, guarantee block) |
| Scorer | `scoring.py`, `harness.py` | CER / WER, eWPM with the documented user model, no-BCI reference, wrong-commit (marginal), error among commits, commit rate, controls, cluster bootstrap CIs, guarantee reporting, conformance gate (trust-ready) |
| Leaderboard | `leaderboard.py` | Static page + JSON + Markdown from `benchmark/results/v0.1/` |

## Tracks
| Track | Modality | Licence | Test set | CI unit | User input rate |
|---|---|---|---|---|---|
| `spanishbcbl-meg-async` | MEG | CC BY-NC 4.0, research only | 637 trials, 17 sentences, 19 participants | sentence x participant (two-way) | 152 chars/min |
| `b2t25-t15-copytask` | intracortical | CC0 | 816 trials, 14 days (cal 812: first half of each day) | day | 159.27 chars/min |
| `toronto-semg-composed` | forearm sEMG | CC BY 4.0 | 551 composed sentences, 19 participants (cal 570) | participant | 75.76 chars/min |

> **Our take:** the cluster unit matters. MEG repeats 17 sentences over 19 people; a trial bootstrap would give CIs that are too narrow. B2T test trials come later in each day than the cal trials, so the split is not exchangeable. This is on purpose: it shows drift (see the CRC row below).

## Why these metrics
- **eWPM next to the no-BCI reference (always).** A decoder that types slower than gaze typing alone is no help ([M2-14](../questions/trust-core-v0-results.md)).
- **Two error rates.** The marginal wrong-commit rate (wrong commits / all trials) is what CRC and LTT control. **Error among commits** (wrong / commits) says how much a user can trust one committed text. On MEG the CRC gate commits on 2% of trials, but 93% of those commits are wrong. The marginal rate alone hides this.
- **Controls are required.** Shuffled and zeros input must give a higher CER (paired CI above 0), and zeros input must not commit (≤ 5%). The MEG history shows why: the first decoder used only a text prior ([decoder M1 results](../questions/decoder-m1-results.md)).
- **Guarantee column.** Each entry states method, α, δ and n_cal, and the board shows the measured test rate next to it.

## Leaderboard v0.1 (our baselines)
Selected rows; full table in [`leaderboard.md`](../../benchmark/site/leaderboard.md).

| Track | Decoder + policy | CER | eWPM [95% CI] | No-BCI | Wrong-commit | Error among commits | Commit rate | Controls | Guarantee |
|---|---|---|---|---|---|---|---|---|---|
| MEG | ConvCTC-M async, always commit | 0.522 | 2.58 [2.32, 2.88] | 3.15 | 0.997 | 0.997 | 1.000 | no (null fail) | none |
| MEG | ConvCTC-M async, trust gate | 0.522 | 3.20 [3.01, 3.45] | 3.15 | 0.000 | n/a | 0.000 | yes | none |
| MEG | ConvCTC-M async, CRC | 0.522 | 3.20 [3.01, 3.44] | 3.15 | 0.020 | 0.929 | 0.022 | no (null missing) | CRC α 0.05, n_cal 437: met |
| B2T | Published sentence, always commit (**stream-scored**) | 0.031 | 19.55 [17.92, 21.21] | 4.08 | 0.194 | 0.194 | 1.000 | no (text only) | none |
| B2T | Published sentence, trust gate | 0.031 | 18.77 [17.22, 20.35] | 4.08 | 0.044 | 0.093 | 0.473 | no (text only) | none |
| B2T | Our word decoder, always commit | 0.095 | 11.45 [10.72, 12.32] | 4.08 | 0.610 | 0.610 | 1.000 | no (null fail) | none |
| B2T | Our word decoder, trust gate | 0.095 | 11.55 [10.85, 12.34] | 4.08 | 0.059 | 0.254 | 0.232 | yes | none |
| B2T | Our word decoder, CRC | 0.095 | 11.55 [10.86, 12.35] | 4.08 | 0.062 | 0.256 | 0.244 | no (null missing) | CRC α 0.05, n_cal 812: **NOT met** |
| EMG | CNN session-calibrated, always commit | 0.123 | 7.81 [6.60, 9.01] | 4.27 | 0.541 | 0.541 | 1.000 | no (null fail) | none |
| EMG | CNN session-calibrated, trust gate | 0.123 | 8.02 [6.90, 9.15] | 4.27 | 0.004 | 0.095 | 0.038 | yes | none |
| EMG | CNN cross-subject, trust gate | 0.479 | 4.08 [3.83, 4.36] | 4.27 | 0.000 | n/a | 0.000 | yes | none |

How the rows were scored:
- **B2T published, always commit:** a full stream submission (816 NTS files, `tools/benchmark/make_b2t25_published.py`), scored end to end. It reproduces the committed M6-06 numbers exactly for CER (0.0309), WER (0.0431) and wrong-commit (0.194); eWPM 19.55 vs 19.61 differs only by the user-model random draws.
- **Trust / CRC / LTT rows on MEG and B2T:** `committed-per-trial`. The committed per-trial arrays (time, words, wrong commit, commit score) are rescored with the benchmark bootstrap; CRC and LTT thresholds are calibrated here on the committed cal items. The plug-in trust rows match the earlier results (B2T 0.059 / 11.55; published 0.044 / 18.77; MEG 3.20).
- **Always-commit rows and all EMG rows:** `committed-aggregate` (point values and bootstrap CIs copied from the committed `trust.json` / `harness-async.json`). CER on these rows has no CI.
- Script: `tools/benchmark/import_baselines.py`. We did not rerun the decoders (GPU busy; B2T rerun about 45 min CPU).

> **Contradiction (with M2-13):** M2-13 reported CRC test wrong-commit 0.0483 on B2T. That is a mean over 200 random cal/test splits (exchangeable). The fixed benchmark split (cal = earlier half of each day) gives 0.062 > α. Both are right: the guarantee holds for exchangeable data and fails under within-day drift. The board shows the fixed-split number.

> **Our take:** conformance is an honest weak spot. Our committed MEG streams (M1-09) predate the M5-10 adapter and reach only `core`, so the MEG entries do not pass the trust-ready entry gate. Rerunning `infer.py` (now via the adapter) fixes this.

## Relation to the roadmap
- **P6** (benchmark + leaderboard): v0.1 delivers the metrics, the NTS submission format, licence-clean fixed splits, the static page and baselines on 3 tracks. Open for P6: replay adapters (P4), Willett handwriting and KT-sEMG tracks, latency and ECE columns, all baselines as stream submissions, first outside submission (externally blocked).
- **P13** (benchmark hub): the dataset registry, guarantee reporting and the "scored from" column are the first steps. Open: CI scoring of pull requests, per-track pages and history, intent tracks after P12.

## Related
- [Conformance suite](conformance-suite.md) (the entry gate)
- [Error metrics](error-metrics.md)
- [Roadmap to a standard](../questions/roadmap-standard.md) (P6, P13)
- [B2T '25 trust result](../questions/b2t25-trust-result.md), [EMG Toronto trust result](../questions/emg-toronto-trust-result.md), [M2-13 conformal result](../questions/m2-13-conformal-result.md)
