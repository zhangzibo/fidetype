# R1 item 5: leakage (G9)

Review items: domain review M8.1–M8.2; methods review Minor 13–14. CPU only. Date: 2026-11-11.

## How much overlap is there?
Near variant = character edit distance ≤ 0.25 × sentence length (the MEG rule), `normalize_text` form, against the 600,000-sentence training slice of the English Tatoeba char 6-gram LM (rebuilt exactly; the slice matches the original build).

| data | sentences | exact copy in LM training | exact or near variant | LM training sentences removed |
|---|---|---|---|---|
| B2T '25 cue sentences (all 1,718 trials) | 1,717 unique | 22 | 310 | 849 (word unigram: 910 sentences removed from all Tatoeba English) |
| sEMG test sentences | 551 | 0 (held-out slice) | **295** | 2,895 (with the near variants of the 570 fit sentences) |

Tatoeba is heavily templated, so half of the short sEMG sentences have a near variant (for example a change of name or one word).

## Re-run with the cleaned LMs
| condition | policy | original eWPM / WC | clean LM eWPM / WC | paired Δ eWPM [CI] |
|---|---|---|---|---|
| B2T ours | always commit | 11.45 / 0.610 | 11.45 / 0.610 | 0 |
| | trust | 11.55 / 0.059 | 11.55 / 0.059 | 0 |
| B2T published gate | trust | 18.77 / 0.044 | 18.77 / 0.044 | 0 |
| sEMG session-cal. | always commit | 7.81 / 0.541 | 7.81 / 0.545 | [−0.02, +0.01] |
| | trust | 8.02 / 0.004 | 7.98 / 0.005 | [−0.08, −0.01] |
| sEMG cross-session | trust | 4.68 / 0.004 | 4.65 / 0.002 | [−0.05, −0.01] |
| sEMG cross-subject | trust | 4.08 / 0 | 4.09 / 0 | [−0.01, +0.03] |

CI: B2T day clusters, sEMG participant clusters (B = 2000). LM weights re-tuned on fit-A with the clean LM came out the same as the original (1.0 / 1.0 / 1.5). sEMG truth-in-10-best with the clean LM: 0.63 (calib), 0.21 (cross-session), 0.08 (cross-subject).

## Answer
1. **Leakage does not explain the main numbers.** On B2T, the cleaned char LM and word unigram changed every n-best score but only 2 of 1,628 top-1 sentences; all main numbers are identical to 3 decimals. On sEMG, removing 2,895 near-variant training sentences lowered trust eWPM by at most 0.04 and did not change any wrong-commit rate by more than 0.002.
2. **Exclusion check (original LM, items without any exact or near variant):** B2T trust 11.10 / WC 0.055 (669 trials), trust − gaze [+6.30, +7.90]; sEMG session-cal. trust 6.97 vs gaze 4.15 ([+1.79, +4.00]), cross-session 4.08 vs 4.15 ([−0.37, +0.27]), cross-subject 3.69 vs 4.15 ([−0.65, −0.24]). These subsets keep the longer, less templated sentences, so they are harder for every policy (always commit falls too); they are a different sentence mix, not a leakage effect (compare the clean-LM rows, which use all sentences).

> **Our take:** report the clean-LM rows (no change) and the overlap counts. The same-corpus style match (Tatoeba LM, Tatoeba test sentences) stays a limitation, but exact or near copies in the LM are not what makes the sEMG numbers.

## Files
`build_lms.py` (near-variant search, LM rebuilds; LMs stay outside the repo in `C:\Users\zhang\bci-data\lm\*_noB2T*`, `*_noEMG.npz`), `run.py`, `config.json`; `results/build_report.json` (counts, examples, the lists of affected sentences), `results/leakage.json`, `results/tables.md`.
Reproduce: `.venv\Scripts\python.exe -I experiments/2026-11-12-paper1-r1-analyses/leakage/build_lms.py` (about 32 min), then `... leakage/run.py` (after `baselines`; about 15 min).
