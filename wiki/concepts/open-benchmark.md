---
title: Open benchmark v0.1
type: concept
tags: [benchmark, leaderboard, evaluation, ewpm, conformal, neuraltextstream, licences]
sources: [brain-to-text-25-copytask, toronto-semg-typing]
updated: 2026-11-18
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
- **Safe WPM @ α column (P14-05, 2026-11-16).** Committed, exactly right words per minute, with a time penalty per wrong commit, only under a certified CRC / LTT bound. Entries whose measured test rate is above α are marked `! ABOVE alpha` (B2T ours + CRC: 0.062). Best entry: published decoder + CRC, 13.42 safe WPM vs no-BCI 4.08 ([docs/safe-wpm.md](../../docs/safe-wpm.md), [results](../../experiments/2026-11-16-p14-05-safe-wpm/results.md)).

## Leaderboard v0.1 (our baselines)
Selected rows; full table in [`leaderboard.md`](../../benchmark/site/leaderboard.md).

| Track | Decoder + policy | CER | eWPM [95% CI] | No-BCI | Wrong-commit | Error among commits | Commit rate | Controls | Guarantee |
|---|---|---|---|---|---|---|---|---|---|
| MEG | ConvCTC-M async, always commit | 0.522 | 2.58 [2.32, 2.88] | 3.15 | 0.997 | 0.997 | 1.000 | no (null fail) | none |
| MEG | ConvCTC-M async, trust gate | 0.522 | 3.20 [3.01, 3.45] | 3.15 | 0.000 | n/a | 0.000 | yes | none |
| MEG | ConvCTC-M async, CRC | 0.522 | 3.20 [3.01, 3.44] | 3.15 | 0.020 | 0.929 | 0.022 | yes (null audit at the CRC threshold, P6-01) | CRC α 0.05, n_cal 437: met |
| B2T | Published sentence, always commit (**stream-scored**) | 0.031 | 19.55 [17.92, 21.21] | 4.08 | 0.194 | 0.194 | 1.000 | no (text only) | none |
| B2T | Published sentence, trust gate | 0.031 | 18.77 [17.22, 20.35] | 4.08 | 0.044 | 0.093 | 0.473 | no (text only) | none |
| B2T | Our word decoder, always commit | 0.095 | 11.45 [10.72, 12.32] | 4.08 | 0.610 | 0.610 | 1.000 | no (null fail) | none |
| B2T | Our word decoder, trust gate | 0.095 | 11.55 [10.85, 12.34] | 4.08 | 0.059 | 0.254 | 0.232 | yes | none |
| B2T | Our word decoder, CRC | 0.095 | 11.55 [10.86, 12.35] | 4.08 | 0.062 | 0.256 | 0.244 | yes (null audit at the CRC threshold, P6-01) | CRC α 0.05, n_cal 812: **NOT met** |
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

## Hallucination tracks (P15-07)

The protocol `fidetype.halluc/0.1` adds four tracks for the question "does the system invent text?": `real`, `null` (uniform log-probs), `scrambled` (frame-shuffled input) and `swapped` (signal of one trial, language side of another). Metrics: commit rate per track, wrong-commit rate, and the fluent-wrong rate (wrong commits that an LLM finds fluent; the deterministic fallback counts every wrong commit as fluent). Clopper-Pearson 95 % intervals. Code `fidetype.benchmark.hallucination`; docs [hallucination-benchmark.md](../../docs/hallucination-benchmark.md); baselines on T15 and T12 in [results](../../experiments/2026-11-16-p15-07-halluc-bench/results.md).

Baselines (3 systems x 2 sets): null and scrambled give 0 commits everywhere. On the swapped track, systems without grounding commit exactly as often as on real input (ratio 1.0): they ignore the signal. The P14-03 guard fails the swapped track on T12 (25/400). The P15-06 guard passes all tracks but never commits.

> **Our take:** the swapped track is the informative one. A fixed 0.05 pass rule lets a rarely-committing system without a signal check pass; the swapped-to-real commit ratio shows the problem directly.

## Tracks v0.2 (P6-01, 2026-11-16)
Seven tracks with fixed, versioned, licence-clean splits: `b2t25-t15` (CC0), `b2t24-t12` (CC0), `willett-hw` (CC0), `toronto-semg` (CC BY 4.0), `kt-semg` (CC BY 4.0), `spanishbcbl-meg` (CC BY-NC 4.0, **research only**), `emg2qwerty` (CC BY-NC-SA 4.0, **research only**). Definition, rules and counts: [docs/benchmark-tracks.md](../../docs/benchmark-tracks.md). Code `fidetype.benchmark.tracks`; split files `src/fidetype/benchmark/splits/tracks-v0.2/`.

- The split files hold only salted hashes per unit: id hash, split, group hash (CI cluster), fingerprint of the truth text and / or size. No text, signals or plain ids (the `halluc-v0.1` pattern).
- `python -m fidetype.benchmark verify <track> --data <path>` checks a local copy against the hashes; `select` maps a split to the local data (adapter input).
- `b2t25-t15`, `toronto-semg` (sentences) and `spanishbcbl-meg` hold exactly the v0.1 trials and splits (tested from the committed files). So v0.1 results stay valid.
- Test data is later in time than training data on every track except SpanishBCBL (split by sentence).

Side results of P6-01 ([results](../../experiments/2026-11-16-p6-01-tracks/results.md)):
- **Toronto safe WPM, exact per trial** (was an aggregate approximation): CNN session-calibrated + CRC 0.55 [0.28, 0.86] (was 0.58), cross-session 0.25 [0.06, 0.46] (was 0.27), cross-subject 0.00 (vacuous). CI over participants. The CRC rerun reproduces the committed commit and wrong-commit rates exactly.
- **Null-commit audits at the CRC / LTT thresholds** (were "missing"): MEG ConvCTC-M CRC / LTT: 0 / 637 commits on zeros MEG input (frame-shuffled 5 and 8 of 637), so both entries now pass all controls. B2T ours CRC / LTT: 0 / 300 commits on uniform and frame-shuffled input, so these two entries now pass all controls. B2T published CRC / LTT: 0 / 300 commits on null input; the shuffled and zeros CER controls stay "missing" (text-only decoder).

## Submission format v0.2 and scorer (P6-02, 2026-11-16)
- Format: [docs/benchmark-submission.md](../../docs/benchmark-submission.md). A folder with `submission.json` (schema `fidetype.benchmark.submission/0.2`: decoder, licence, policy, guarantee, regime, how the controls were made, optional declared subset), `units.jsonl` (one row per scored unit, keyed by the salted unit hash of the split file) or NTS streams, and the two required control runs.
- One command: `python -m fidetype.benchmark score <track> <submission> --data <path>` (or `--truth`). It checks the truth against the split fingerprints, validates the rows, and prints the score card. Exit code 0 only when shuffled, zeros and null-commit (<= 5 %) pass.
- Baselines ([results](../../experiments/2026-11-16-p6-02-scorer/results.md)), alpha 0.05: T12 v2 + drop-in guard: safe WPM **0.48 certified** (wrong-commit 0.010, 17 commits), CER 0.304, eWPM 6.36 vs no-BCI 4.00. Willett published RNN (81 of 254 trials): CER 0.080, guard infeasible (vacuous). KT-sEMG and emg2qwerty (research only) LDA with oracle key timing: key error 0.55 / 0.49, vacuous. Every always-commit entry fails the null-commit control, as it should.

> **Our take:** with the scorer in place, every v0.2 number now comes with its controls. The weak point is the decoders, not the measurement: only T12 certifies a commit, and it is still below gaze typing.

## Relation to the roadmap
- **P6** (benchmark + leaderboard): v0.1 delivers the metrics, the NTS submission format, licence-clean fixed splits, the static page and baselines on 3 tracks. Tracks v0.2 (P6-01) adds the Willett handwriting, B2T '24 T12, KT-sEMG and emg2qwerty tracks with hash-only splits. Scorer + baselines for the new tracks: P6-02 (done). Open for P6: replay adapters (P4), latency and ECE columns, all baselines as stream submissions, first outside submission (externally blocked).
- **P13** (benchmark hub): design done 2026-11-18 ([hub design](../questions/hub-design.md), [docs](../../docs/hub-design.md)): versioned dataset registry, replay contract, rerun levels, governance. the dataset registry, guarantee reporting and the "scored from" column are the first steps. Open: CI scoring of pull requests, per-track pages and history, intent tracks after P12.

## Related
- [Conformance suite](conformance-suite.md) (the entry gate)
- [Error metrics](error-metrics.md)
- [Roadmap to a standard](../questions/roadmap-standard.md) (P6, P13)
- [Benchmark hub design](../questions/hub-design.md) (P13-01)
- [B2T '25 trust result](../questions/b2t25-trust-result.md), [EMG Toronto trust result](../questions/emg-toronto-trust-result.md), [M2-13 conformal result](../questions/m2-13-conformal-result.md)
