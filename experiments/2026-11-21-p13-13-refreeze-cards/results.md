---
title: P13-13 frozen trust configs for the pre-P5-23 trust cards - results
type: experiment
task: P13-13
updated: 2026-11-21
---

# P13-13: refit and freeze the 30 pre-P5-23 trust cards (results)

Gap 85. Code: [run.py](run.py). Counts and ids: [results/results.json](results/results.json). Frozen configs: [results/configs/](results/configs/) (15 files, numbers and settings only). Card writer: `tools/benchmark/add_rerun_recipes.py --refrozen`. Check: `fidetype.benchmark.hub.recipe.config_id_problems`, tests in `tests/test_hub_cli.py`. Design: [hub-design.md section 12.8](../../docs/hub-design.md#128-frozen-configs-for-the-pre-p5-23-trust-cards-p13-13).

This page and `results.json` hold counts, thresholds and ids only: no text, no per-unit data. The build-step files were read only (`C:\Users\zhang\bci-data\derived\p6-02b-v02-entries\`). Logs and per-stage files are in `C:\Users\zhang\bci-data\derived\p13-13\` (not committed). The `spanishbcbl-meg` data is research only (CC BY-NC 4.0).

Run: 2026-11-21 15:50 to 16:04, CPU only (isolation class `background`, 2 threads). No GPU. Stage times: meg 171 s, toronto 166 s, b2t 456 s.

## Outcome
**Pass. All 30 trust cards now record a `config_id`. For every card, a refit with the build-step settings, frozen, written to disk and loaded back, gives the same decisions as the card. No headline number changed. No card needs a reason.**

| Count | Value |
|---|---|
| Trust cards without a `config_id` before (P13-11) | 30 (15 v0.1, 15 v0.2) |
| Inputs available locally | 30 |
| Refit and frozen | 30 (15 configs; each v0.1 card and its v0.2 card share one config) |
| Same decisions as the card | 30 |
| Same commit threshold as the card | 30 |
| Mismatches | 0 |
| Cards left with a reason | 0 |

## What was run
1. **Refit.** Each TrustPipeline was refitted as in its build step (`experiments/2026-11-17-p6-02b-v02-entries/run.py`, stages `b2t`, `meg`, `toronto`): same data, split, seed, decoder, LM weight and harness settings.
2. **Threshold.** `b2t25-t15` and `spanishbcbl-meg`: one plug-in pipeline per decoder. The cards use three thresholds on its commit score: plug-in grid `commit_p`, CRC lambda, LTT lambda (alpha 0.05, delta 0.1). The CRC and LTT lambdas were recomputed from the refit calibration scores (as `tools/benchmark/import_baselines.py`). They replace the grid `commit_p` in the frozen config, and the config records the risk-control result (`combine: replace`). `toronto-semg`: the trust and CRC pipelines were fitted separately. The CRC pipeline has CRC inside its fit (`combine: max`), so the frozen config is the fitted pipeline itself.
3. **Freeze.** `FrozenTrustConfig.from_pipeline`. The file `results/configs/<name>.json` holds `config_id`, the cards it backs and the config. The script loads the file back and checks the id.
4. **Decide from the file.** The script builds a new pipeline from the loaded config only. It then decides every test unit for the real input and for the two controls (shuffled, zeros). It compares the action, the top-1 text and the score with the card's v0.2 submission rows. For v0.1, it compares the commit decisions with the committed per-trial scores (`b2t`, `meg`) or the commit count with the card's commit rate (`toronto`, aggregates only).

## Checks
Calibration scores of the refit against the committed v0.1 items (`b2t` ours / published 812 each, `meg` 437): equal, max abs difference 0.0.

| Config (`results/configs/`) | `config_id` | `commit_p` | Commits real (card) | Commits shuffled / zeros | v0.1 check |
|---|---|---|---|---|---|
| `p13-13-b2t25-t15-ours-trust` | `tcfg-4ba03bcde2ca2cd7` | 0.5 | 189 (189) | 0 / 0 | 816 trials, 0 differ |
| `p13-13-b2t25-t15-ours-crc` | `tcfg-9c8e8262e92b4da5` | 0.48927 | 199 (199) | 0 / 0 | 816 trials, 0 differ |
| `p13-13-b2t25-t15-ours-ltt` | `tcfg-29d158260e0d503a` | 0.54 | 159 (159) | 0 / 0 | 816 trials, 0 differ |
| `p13-13-b2t25-t15-published-trust` | `tcfg-3c03e78a91ba60a9` | 0.7 | 386 (386) | 0 / 0 | 816 trials, 0 differ |
| `p13-13-b2t25-t15-published-crc` | `tcfg-3824599997d61b6e` | 0.67171 | 405 (405) | 0 / 0 | 816 trials, 0 differ |
| `p13-13-b2t25-t15-published-ltt` | `tcfg-2c25a97b2e5364a9` | 0.72 | 364 (364) | 0 / 0 | 816 trials, 0 differ |
| `p13-13-spanishbcbl-meg-convctc-m-async-trust` | `tcfg-3222ca89560b8def` | 0.5 | 0 (0) | 0 / 0 | 637 trials, 0 differ |
| `p13-13-spanishbcbl-meg-convctc-m-async-crc` | `tcfg-59f2fac9381cbda8` | 0.10239 | 14 (14) | 0 / 0 | 637 trials, 0 differ |
| `p13-13-spanishbcbl-meg-convctc-m-async-ltt` | `tcfg-078f5c49dc4cf0f5` | 0.0 | 15 (15) | 0 / 0 | 637 trials, 0 differ |
| `p13-13-toronto-semg-cnn-calib-trust` | `tcfg-85083946606c4c71` | 0.7 | 21 (21) | 0 / 0 | 21 = rate 0.0381 x 551 |
| `p13-13-toronto-semg-cnn-calib-crc` | `tcfg-27d57285bb044879` | 0.7 (CRC 0.44803, max) | 21 (21) | 0 / 0 | 21 = rate 0.0381 x 551 |
| `p13-13-toronto-semg-cnn-xsession-trust` | `tcfg-4f186d334bef2f50` | 0.3 | 10 (10) | 1 / 0 | 10 = rate 0.0181 x 551 |
| `p13-13-toronto-semg-cnn-xsession-crc` | `tcfg-d8bacbc6d4316e4d` | 0.3 (CRC 0.20359, max) | 10 (10) | 1 / 0 | 10 = rate 0.0181 x 551 |
| `p13-13-toronto-semg-cnn-xsubject-trust` | `tcfg-8d787ba942383efd` | 0.3 | 0 (0) | 0 / 0 | 0 = rate 0 |
| `p13-13-toronto-semg-cnn-xsubject-crc` | `tcfg-8b5f62b08c397f27` | inf (CRC inf, max) | 0 (0) | 0 / 0 | 0 = rate 0 |

On all three inputs (real, shuffled, zeros) of every card: 0 action differences, 0 top-1 text differences, 0 score differences (max abs score difference 0.0 at 6 decimals). The shuffled-control commit of the `toronto-semg` cross-session cards (1 of 551) is in the card too.

## Card changes
Only the `rerun.policy` block and `rerun.amended` changed, in 30 cards (checked key by key by the tool): `config_id_reason` was replaced by `config_id` and `config_id_source` (the config file). No metric, guarantee, control or safe-WPM number changed. The leaderboard pages (`benchmark/site/`) were rebuilt.

## Future cards
`config_id_problems` flags a trust card (any policy other than always-commit) that has no `config_id`, unless its reason is one of `TRUST_CARD_REASONS` (a new submission that names no config, or "refit does not reproduce the card"). With a `config_id`, the source file must exist, and its frozen config must give the same id. `tests/test_hub_cli.py` runs it on every committed card and on synthetic cards.

## Limits
- The `toronto-semg-composed` v0.1 cards have aggregates only, so their check is the commit count, not per-trial decisions. The v0.2 cards for the same pipelines were checked per unit.
- The configs freeze the fitted numbers. A rerun at level `replay` (adapter, trust policy and scorer from raw data) is still P13-10.
