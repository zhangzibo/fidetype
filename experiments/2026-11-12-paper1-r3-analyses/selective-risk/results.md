# R3 item 2: selective-risk controllers (error among commits)

Review items: editor M3 (major), Fig. 4c comment; stats review §8 (D-M2). Script: [run.py](run.py). Config: [config.json](config.json). Numbers: [results/selective_risk.json](results/selective_risk.json), [results/tables.md](results/tables.md). Repeated-split numbers come from `repeated-splits`.

## What we did
- Target: error among commits P(wrong | commit) ≤ β with probability ≥ 1 − δ, δ = 0.1, β = 0.05 / 0.10 / 0.20.
- **SGR** (Geifman & El-Yaniv 2017, Alg. 1): binary search over the sorted calibration scores of the eligible items; exact binomial upper bound; Bonferroni δ / ⌈log₂ m⌉.
- **LTT-sel**: H0(λ): P(wrong | s ≥ λ) > β, exact binomial p-value given the number of commits, Bonferroni over the fixed grid λ = 0.05 … 1.00.
- **Joint**: max(SGR, CRC max-rule), i.e. marginal ≤ α = 0.05 and selective ≤ β.
- Data: 50 repeated deployment splits (B2T ours / published, sEMG 3 conditions); the paper's fixed clean splits (B2T split A / B, sEMG fit-B2, MEG val-B) with unified bootstrap CIs; MEG sentence-grouped splits (8 of 17 calibration sentences, R = 1,000).

## Results: operating points over 50 repeated splits (test set)

| condition | β | rule | commit rate mean [p05, p95] | splits with no commit | error among commits (pooled) | splits with EAC > β | marginal wrong-commit | eWPM |
|---|---|---|---|---|---|---|---|---|
| B2T published | 0.10 | SGR | 0.112 [0, 0.376] | 64 % | 0.069 | 0 % | 0.0077 | 18.12 |
| B2T published | 0.10 | LTT-sel | 0.072 [0, 0.335] | 76 % | 0.059 | 0 % | 0.0043 | 18.07 |
| B2T published | 0.10 | joint | 0.111 | 64 % | 0.068 | 0 % | 0.0075 | 18.12 |
| B2T published | 0.20 | SGR | 0.617 [0.455, 0.850] | 0 % | 0.142 | 0 % | **0.0878** | 18.79 |
| B2T published | 0.20 | joint | 0.418 [0.356, 0.494] | 0 % | 0.085 | 0 % | 0.0357 | 18.52 |
| B2T published | 0.05 | all | 0 | 100 % | — | — | 0 | 17.98 |
| B2T ours | 0.20 | SGR | 0.003 | 96 % | 0.208 | 2 % | 0.0007 | 10.95 |
| B2T ours | 0.05, 0.10 | all | 0 | 100 % | — | — | 0 | 10.95 |
| sEMG (all three) | all β | all | 0 | 100 % | — | — | 0 | 7.97 / 4.68 / 4.07 |
| MEG (sentence-grouped) | all β | all | 0 | 100 % | — | — | 0 | 3.20 |

Reference (CRC max-rule, marginal only): published commit 0.418, error among commits 0.085; ours 0.166, 0.221; sEMG session-cal. 0.105, 0.119; cross-session 0.016, 0.414.

## Results: the paper's fixed clean splits
- B2T ours, split A / B: every selective controller commits nothing at β ≤ 0.20 (split A has only 29 eligible calibration items).
- B2T published, split A: β ≤ 0.10 commits nothing; β = 0.20: SGR commits 0.527 (50 / 430 wrong, CP95 [0.088, 0.150]) with marginal wrong-commit 0.0613 [0.042, 0.084] > α; LTT-sel and joint give the plug-in point (0.491, 39 / 401 wrong, marginal 0.0478). Split B: similar.
- sEMG and MEG: no commits at any β.

## Interpretation
> **Our take:** A guaranteed error among commits of ≤ 0.10 (δ = 0.1) is reachable only for the published-sentence gate, and only in about a third of deployments (commit rate 11 % on average; 0 in 64 % of splits) with about 400 calibration trials. At β = 0.20 the published gate commits 42–62 %. Our own decoder, sEMG and MEG commit nothing under any selective target; the layer then equals always offer. SGR alone can break the marginal target (0.088 at β = 0.20), so the joint rule (marginal ≤ α and selective ≤ β) is the one to recommend. This matches the editor's prediction and makes the clinical claim precise: with current decoders and a few hundred calibration sentences, a certified "one wrong committed sentence in ten" is possible only for the strongest decoder. The binding constraint is the calibration size: the eligible committed set is small, and exact binomial bounds on 10–80 commits are wide.
