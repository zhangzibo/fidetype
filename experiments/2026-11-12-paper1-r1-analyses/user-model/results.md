# R1 item 4: user-model sensitivity (G6), symmetric offers, misspecified user, LM-assisted gaze

Review items: methods review Major 5 (asymmetry, refit vs misspecified, symmetric variant); domain review M4 (population, LM-assisted gaze baseline, robustness matrix). CPU only. Date: 2026-11-11.

All six main-table conditions (MEG also gets the new symmetric and misspecified runs). Full matrix with CIs: `results/tables.md`.

## Answer
1. **The ranking trust > always commit depends on the user model on B2T ours.** Trust is fastest under the main user, slow fallback (10 cpm) and fast selection. Always commit is fastest with a fast fallback (40 cpm: 14.97 vs 14.65), slow selection (10.55 vs 10.37), p_miss 0 (11.65 vs 11.54) and both symmetric-offer variants (11.45 vs 11.36). On the published gate, always commit is fastest in **every** variant (trust costs 0.3–1.5 eWPM) and trust buys only safety.
2. **Trust ≥ never commit (always offer) in every variant and condition** (CIs > 0 on B2T: +0.01 to +0.30 ours, +0.29 to +1.32 published; ≈ 0 on sEMG / MEG, where both policies are the same).
3. **Misspecified user (fit under main, scored under the variant, no refit)** loses ≤ 0.2 eWPM relative to refit on B2T and sEMG in all variants except the symmetric offer with p_miss 0.2. There it collapses on sEMG cross-session (2.75 vs refit 3.39), sEMG cross-subject (1.92 vs 3.33) and MEG (1.18 vs 2.75), because the always-offer policy fitted under the main user leaves many missed errors; the refit policy abstains and retypes instead.
4. **Symmetric offers** (offers also miss wrong words; no oracle retype) remove most of the trust advantage: B2T ours trust 11.36 vs always commit 11.45; sEMG cross-session 4.05 vs 4.06; MEG trust 2.75 vs gaze 3.15 (CI of trust − gaze [−0.43, −0.39]). Trust silent-error rates rise from ≤ 0.004 to 0.02–0.17.
5. **LM-assisted gaze typing beats the trust layer on MEG and on sEMG cross-session and cross-subject.** Main user: gaze + word completion gives 4.10 (MEG; trust 3.20, CI of trust − gaze+LM [−1.14, −0.64] two-way), 6.19 (sEMG; trust 4.68 cross-session [−1.99, −0.95], 4.08 cross-subject [−2.35, −1.84]). Only B2T (11.55 / 18.77 vs 5.84) and sEMG session-calibrated (8.02 vs 6.19, CI [+0.74, +2.99]) stay clearly above it. With a 1 s glance cost per letter, gaze + LM drops to 3.16 (MEG) and 4.84 (sEMG) and the MEG "parity" returns.
6. **MEG vs plain gaze typing:** parity under the main user (two-way CI [−0.11, +0.27]); trust is faster with a 10 cpm fallback ([+0.21, +0.45]) or ×0.5 selection cost ([+0.13, +0.53]); gaze is faster with a 40 cpm fallback ([−1.36, −0.89]), ×2 selection cost ([−0.31, −0.02]) and symmetric offers ([−0.43, −0.39]).

> **Our take:** the speed claims for MEG and the weak sEMG decoders do not survive a gaze baseline with a simple word-completion LM; the paper should report it next to plain gaze typing and limit the speed claim to B2T and session-calibrated sEMG. The safety result (wrong commits) does not depend on the user model. On B2T ours, "trust is faster than always commit" is model-dependent; "trust is at least as fast as always-offer" is robust.

## Variants and models
| variant | change from `UserConfig.aac_gaze()` |
|---|---|
| fallback 10 / 40 cpm | `fallback_chars_per_min` 10 / 40 (main 20) |
| selection ×0.5 / ×2 | `select_a_s`, `select_b_s_per_bit`, `word_scan_a_s`, `word_scan_b_s_per_bit`, `word_select_s`, `nav_s` all scaled |
| p_miss 0 / 0.2 | `p_miss_unflagged` (main 0.05) |
| symmetric offer | `SymmetricUser` (`policies.py`): an OFFER without the target makes the user fix the closest candidate word by word, missing each wrong word with `p_miss_unflagged` (as for COMMIT); no oracle choice of fix / repeat / retype; `allow_full_retype` False for all actions |
| misspecified | trust and never-commit fitted under the main user, scored under the variant |

**LM-assisted gaze (assumptions).** Letter-by-letter gaze typing at the fallback rate; before each letter the keyboard shows the 3 most frequent vocabulary words with the typed prefix (unigram, no sentence context; counts ≥ 2). If the intended word is shown and selection is faster than typing the rest of the word and its space, the user selects it at word_scan_time(3) + word_select_s (4.5 s at main costs, close to the 4.7 s measured for one word choice in Cai et al. 2024). No time to look at the list (optimistic, favours the baseline); variant `glance`: 1 s per look. Unigram corpora: B2T = the BCI word unigram (all Tatoeba English); sEMG = Tatoeba English without the 5,000 held-out sentences (the sEMG test pool); MEG = Tatoeba Spanish without the SpanishBCBL targets. Completion share of words: see `user-model-*.json` (`gaze_lm_completion_share`).

## Files
`run.py`, `config.json`; `results/user-model-*.json` (points, rankings, CIs of eWPM differences, silent-error differences); `results/tables.md`.
Reproduce: `.venv\Scripts\python.exe -I experiments/2026-11-12-paper1-r1-analyses/user-model/run.py --conds emg-calib` (and the other conditions), then `report.py`.
