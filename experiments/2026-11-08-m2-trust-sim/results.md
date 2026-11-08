# M2: trust core on simulator data (2026-11-08)

Run: `uv run python experiments/2026-11-08-m2-trust-sim/run.py` (about 12 min on CPU). Full tables: [results/tables.md](results/tables.md). Raw numbers: `results/metrics.json`.

## Setup
- Data: the noisy-decoder simulator, presets best/median/worst x `confidence_temperature` 0.5/1.0/2.0. Each condition has 120 calibration, 120 validation and 120 test sentences (template sentences).
- Decoder: `fidetype.trust.testing.ReferenceDecoder` (segment beam with a 5-gram Witten-Bell character LM). The LM is trained on other template sentences. **The LM is in-domain, so the LM-fused CER (0.03-0.06) is optimistic.**
- Policies: (a) COMMIT greedy CTC; (b) COMMIT LM top-1; (c) trust policy, fitted on validation for max eWPM with wrong-commit <= 0.05; (d) (c) without calibration; (e) (c) without the guard.
- Simulated user: default `UserConfig` (152 chars/min, p_detect_error 0.9, select-and-correct on). The time costs are assumptions, not measurements.

## Results (test set, 120 sentences each)
| condition | eWPM a | eWPM b | eWPM c | eWPM d | eWPM e | wrong-commit b | wrong-commit c |
|---|---|---|---|---|---|---|---|
| best/T=0.5 | 17.25 | 23.82 | 21.26 | 23.17 | 21.09 | 0.38 | 0.07 |
| best/T=1.0 | 17.45 | 23.89 | 22.30 | 23.02 | 22.20 | 0.29 | 0.07 |
| best/T=2.0 | 17.32 | 22.52 | 21.01 | 19.99 | 21.03 | 0.35 | 0.02 |
| median/T=0.5 | 15.76 | 23.42 | 19.69 | 19.90 | 19.63 | 0.42 | 0.03 |
| median/T=1.0 | 15.62 | 23.89 | 21.88 | 22.65 | 21.60 | 0.32 | 0.03 |
| median/T=2.0 | 15.44 | 22.86 | 20.19 | 21.38 | 20.17 | 0.38 | 0.08 |
| worst/T=0.5 | 13.61 | 22.59 | 19.74 | 21.62 | 19.50 | 0.44 | 0.02 |
| worst/T=1.0 | 13.68 | 22.16 | 20.14 | 20.54 | 20.08 | 0.41 | 0.03 |
| worst/T=2.0 | 13.65 | 21.39 | 19.58 | 20.37 | 19.58 | 0.47 | 0.09 |

## Findings
1. **The LM matters most.** LM top-1 (b) beats greedy (a) by 6-9 eWPM in every condition.
2. **The trust policy cuts wrong commits by about 5-20x** (0.29-0.47 to 0.02-0.09) and costs 1.5-3.7 eWPM (7-16 %) against (b). With this user model (90 % of wrong commits caught, cheap corrections), always-commit is faster. The trust policy pays off only if a silent or a wrong commit costs more than the model charges. The Pareto table shows the trade-off at limits 0.02/0.1/0.2/1.0.
3. **The validation limit does not hold exactly on test.** Wrong-commit on test is up to 0.09 against a 0.05 target (120 validation sentences; the grid fit has no finite-sample guarantee).
4. **Calibration works.** The frame temperature recovers the inverse of the simulator distortion (fitted 1.99-2.01 for T=0.5, 0.50-0.51 for T=2.0). Character ECE falls from 0.16-0.39 to 0.012-0.021. Sentence ECE falls from 0.25-0.34 to 0.09-0.16. The fitted sentence temperature is large (6-9): raw n-best scores are very over-confident.
5. **Conformal coverage in the n-best sense is 0.83-0.99** (target 0.9). The n-best misses the truth in 28-37 % of sentences, so strict coverage is only 0.57-0.71. Recall is the bottleneck, not the set.
6. **The guard catches null input.** On shuffled and uniform streams, the trust policy commits 0 % fluent text. Always-commit top-1 commits 98-100 % fluent text. On real input the guard AUROC for a wrong top-1 is only 0.57-0.71; the n-best inconsistency signal alone does better (0.65-0.88).
7. **Ablations are not clean.** Without calibration (d) eWPM is often *higher* than (c). Without the guard (e) eWPM is about the same as (c). On this data, the policy thresholds absorb most of what calibration and the guard add.

> **Our take:** The headline claim for Paper 1 should be "a large cut in wrong and hallucinated commits for a modest speed cost", not "higher eWPM". The eWPM result depends on the user time model. We need real or literature-based time costs (Cai et al. 2024) before we report eWPM numbers.

## Cross-check with `fidetype.lm` CTC prefix beam (median/T=1.0)
| policy | eWPM | wrong-commit | CER | miss rate | guard AUROC |
|---|---|---|---|---|---|
| b top-1 commit | 20.42 | 0.758 | 0.080 | 0.733 | 0.462 |
| c trust | 16.27 | 0.000 | 0.075 | 0.708 | 0.431 |

The LM agent's beam (default settings) misses the truth in 73 % of n-best lists here, against 28 % for the reference decoder. Then the trust policy cannot commit, and eWPM falls. The guard AUROC is below 0.5. The guard needs re-tuning for this decoder's `"frame"` confidences. Re-tune the beam (prune_topk, bonus) before the next run.

## Limitations
- Simulator data only. Template sentences only. In-domain LM.
- User time costs are assumptions.
- One seed per condition. 120 test sentences: an eWPM difference below about 1 is likely noise.
