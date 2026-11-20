---
title: P11-13 intended-text scoring for the emg2qwerty track - results
type: experiment
task: P11-13
updated: 2026-11-19
---

# P11-13: intended-text scoring for the emg2qwerty track (results)

Code: `698bbe8` (scorer target option, tests, docs, [cards.py](cards.py)). Cards and regenerated leaderboard: committed with this page. Aggregates: [results/results.json](results/results.json), log `results/run.log`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page and the committed files hold pooled aggregates only: no per-user value, no text, no id. The P11-12 decisions and guard files (`C:\Users\zhang\bci-data\derived\p11-12\`) were read only. Submission folders: `C:\Users\zhang\bci-data\derived\p11-13\` only. CPU only; no new decoding: the cards rescore the cached P11-12 decisions.

## Outcome
**The emg2qwerty track now has a versioned scoring target. The P11-12 sentence arm S has its first track score card: certified, safe WPM v0.1 4.10 [1.99, 6.56] (target `intended_text`) vs no-BCI 3.09 on the same target. All three scorer controls pass. Arm SL has a second card: 5.08 [2.54, 7.95]. The track scorer gives the same safe-WPM value, commits, wrong commits, words, correction time and no-BCI reference as P11-12. Only the bootstrap CI differs a little (cluster labels, see below).**

## 1. Scorer change (`fidetype.benchmark`)
| Item | What |
|---|---|
| Manifest field | `target` (optional; `emg2qwerty` only): `raw_keys` (default) or `intended_text` |
| Versions | `raw-keys/1` (normaliser `keycodes`), `intended-text/1` (normaliser `keycodes_intended`) |
| Rule `intended-text/1` | `registry.keycodes_to_intended_text`: a character key appends, `Backspace` removes the last character if any, `Enter` is ignored, then runs of spaces are joined and the ends stripped. A test checks that it equals the P11-11 `resolve` on 2,000 random key sequences (Backspace-heavy) |
| Both sides | The same normaliser is applied to the truth and to every output text, so the no-BCI reference, CER and safe WPM all use the target text |
| Card | A manifest with `target` gives a `target` block (name, version, normaliser, rule) and `rerun.scorer.target`. A manifest without `target` gives the old card form |
| Leaderboard | Each target gets its own table with its own no-BCI row inside the track. An `intended_text` row carries `[target: intended_text]` in its name. Cards without a `target` block count as `raw_keys`. One table, as before, when every entry uses the default |
| Docs | [benchmark-submission.md](../../docs/benchmark-submission.md) (text space, manifest), [benchmark-tracks.md](../../docs/benchmark-tracks.md) (what every entry reports) |

Regression: the two committed P11-09 cards rescored with the new scorer (`hub.recipe.rescore` on the local submission folders) are equal in every top-level field except `notes`. The only note difference is the FEP-0010 note that the P11-09 runner adds after scoring; this was so before the change. A unit test checks that a manifest without `target` gives a byte-equal card on a track with and without targets.

## 2. Cards (declared subset: the 8 P11-01 test users, 1,221 prompts)
| Measure | Arm S (primary) | Arm SL |
|---|---|---|
| Card | [`emg2qwerty__p11-12-intended-s-subset8__guard`](../../benchmark/results/v0.2/emg2qwerty__p11-12-intended-s-subset8__guard.json) | [`emg2qwerty__p11-12-intended-sl-subset8__guard`](../../benchmark/results/v0.2/emg2qwerty__p11-12-intended-sl-subset8__guard.json) |
| Status / certification | `scored` / `certified` | `scored` / `certified` |
| Safe WPM v0.1 [95 % CI] | **4.10 [1.99, 6.56]** | **5.08 [2.54, 7.95]** |
| No-BCI reference (gaze, intended text) | 3.09 | 3.09 |
| Commits / wrong commits | 167 / 35 | 194 / 31 |
| Wrong-commit rate (alpha 0.05) | 0.029 (met) | 0.025 (met) |
| Error among commits | 0.210 | 0.160 |
| CER of the top-1 intended text | 0.277 [0.168, 0.392] | 0.277 (same top-1) |
| eWPM (simulated user) vs no-BCI | 5.28 [4.37, 6.67] vs 3.09 | 5.28 [4.37, 6.68] vs 3.09 |
| Controls (shuffled / zeros / null commit) | pass / pass / pass (CER 1.000 / 1.000; zero-input commits 0.000) | pass / pass / pass |
| Policy config | `tcfg-3875f995e4c256fb` | `tcfg-0cd6e9578e965f42` |

## 3. Check against P11-12
| Quantity | Track scorer (arm S) | P11-12 (arm S) | Same |
|---|---|---|---|
| Safe WPM v0.1 value | 4.0952 | 4.0952 | yes |
| Commits / wrong | 167 / 35 | 167 / 35 | yes |
| Right words committed / all words | 548 / 4,985 | 548 / 4,985 | yes |
| No-BCI WPM | 3.0924 | 3.0924 | yes |
| Neural / correction minutes | 119.75 / 14.06 | 119.75 / 14.06 | yes |
| 95 % CI | [1.99, 6.56] | [1.99, 6.60] | no (small) |

Arm SL: value 5.0845, 194 / 31, all the same; CI [2.54, 7.95] vs [2.67, 7.96].

Why the CI differs: both use a percentile cluster bootstrap over the same 8 users (B = 2000, seed 0). P11-12 labels the clusters `u0` ... `u7`; the track scorer labels them by the split group hash. The labels sort in a different order, so the same random draws pick different users. Check (scratch script): the scorer trial scores with the P11-12 labels give exactly the P11-12 CIs ([1.9886, 6.6044] and [2.6697, 7.9606]). So the difference is the cluster label order only, not the data or the rule. The card CI is the one the track scorer gives for every entry.

> **Our take:** the first certified, non-vacuous EMG safe WPM now sits on the leaderboard, in its own `intended_text` table. It is above gaze typing (3.09), but the lower CI bound (1.99) is below it: 8 users give wide intervals. The raw-key P11-09 entries stay in the `raw_keys` table; the two tables are not ranked against each other.

## Limits
- Declared subset: 8 of 104 track test sessions (the only clean ones for the P11-01 decoder).
- The eWPM user model keeps the track rate (301.33 keys/min) for both targets. Safe WPM uses the measured `neural_s` of each prompt.
- Offline decisions on full prompt windows; no latency claim (gap 37).
- Arm X (word prefixes) needs the proposed safe-WPM v0.2; the scorer computes v0.1 only, so arm X gets no card.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q tests/test_benchmark_scorer.py` |
| Score (local; needs the P11-12 decisions and the local truth) | `.venv\Scripts\python.exe -I experiments/2026-11-20-p11-13-intended-text-cards/cards.py score` |
| Cards | `.venv\Scripts\python.exe -I experiments/2026-11-20-p11-13-intended-text-cards/cards.py cards --code-ref 698bbe8`, then `python -m fidetype.benchmark leaderboard --results benchmark/results/v0.1 benchmark/results/v0.2 --out benchmark/site` |
| Check | `python -m fidetype.benchmark.leaderboard --check` |
