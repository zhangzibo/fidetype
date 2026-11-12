# R1 item 7: fix-check numbers

Review items: domain review section 6 (rows 1, 4, 6) and M6.1–M6.2. CPU only. Date: 2026-11-11.

## 1. B2T '25 trials and days: the exact description
- The file has **1,718 trials from 15 post-implant days** (25, 27, 34, 46, 48, 69, 74, 76, 81, 83, 88, 90, 95, 223, 244).
- **90 trials use the 50-word vocabulary**: all 50 trials of day 25 and 40 of the 70 trials of day 27.
- The analysis uses the other **1,628 trials (125,000-word vocabulary) from 14 days** (27 to 244).
- Each day's 125k trials are split in file order: first half → fit (**812**), second half → test (**816**). Test trials per day: 15 (day 27) to 104 (day 76).
- One sentence occurs in both fit and test. 64 of the 1,628 cue sentences occur verbatim somewhere in Tatoeba English; 22 unique cues have an exact copy in the 600,000-sentence char-LM training slice (see `leakage`).
- Suggested text: "The file holds 1,718 trials from 15 days. We use the 1,628 trials with the 125,000-word vocabulary (14 days); the 90 trials with the 50-word vocabulary (day 25 and part of day 27) are excluded."

## 2. MEG: harness CER 0.522 vs M1-09 beam + LM 0.475
Same test streams (637 instances), one factor at a time:

| setting | frame T | LM weight | insertion bonus | CER pooled | CER mean over instances |
|---|---|---|---|---|---|
| trust harness (RETUNED, n_best 10) | 3.296 | 0.5 | 1.0 | **0.522** | 0.522 |
| raw stream | 1.0 | 0.5 | 1.0 | 0.483 | 0.481 |
| lower LM weight | 3.296 | 0.25 | 1.0 | 0.565 | 0.567 |
| no insertion bonus | 3.296 | 0.5 | 0.0 | 0.477 | 0.475 |
| M1-09 val choice (lm 0.25, bonus 0) | 3.296 | 0.25 | 0.0 | 0.477 | 0.475 |
| M1-09 val-tuned beam exactly | 3.285 | 0.25 | 0.0 | 0.477 | **0.475** |

- **Cause: the insertion bonus of 1.0 on frame-calibrated streams.** The temperature (3.3) flattens the frame posteriors, so a per-character bonus of 1.0 adds spurious characters. The M1-09 grid tuned the bonus to 0 on calibrated streams; the harness kept the RETUNED bonus 1.0 that was tuned on raw streams. With bonus 0 the harness gives 0.475. The CER definition (pooled vs mean over instances) changes the value by ≤ 0.002.
- In the harness top-1 accuracy is 2 / 637 (0.0031) with bonus 1.0 and 3 / 637 (0.0047) with the M1-09 setting.
- With the M1-09 beam in the harness, trust eWPM is 3.137 (always commit 2.581), vs 3.203 with the harness beam (see `ablation`, `lm_retuned`). A lower CER did not help the trust layer.
- Suggested text: "The trust harness decodes with insertion bonus 1.0 (top-1 CER 0.522); the decoder table uses the validation-tuned bonus 0 (0.475). All MEG trust numbers use the harness setting."

## 3. sEMG key decoder: balanced accuracy and chance
Day-2 presses, 27 classes (26 letters + space), 14,929 presses.

| run | accuracy | balanced accuracy | letter accuracy | space accuracy | top-5 |
|---|---|---|---|---|---|
| session-calibrated (`calib`) | 0.299 | **0.367** | 0.375 | 0.151 | 0.772 |
| cross-session (`xsession`) | 0.168 | **0.240** | 0.249 | 0.010 | 0.571 |
| cross-subject (`xsubject`) | 0.209 | **0.226** | 0.228 | 0.172 | 0.672 |
| linear, cross-session | 0.162 | 0.175 | 0.177 | 0.132 | 0.525 |
| permuted labels (control) | 0.022 | 0.032 | 0.034 | 0.000 | 0.137 |

- **Chance levels: uniform 1/27 = 0.037** (letters only 1/26 = 0.038); **majority class (space) = 0.338**. Balanced-accuracy chance = 1/27 = 0.037.
- All plain accuracies are below the majority rate, because the CNNs rarely predict space; balanced accuracy is the fair metric. The permuted-label control (0.022 accuracy, 0.032 balanced) is at or below uniform chance; it is a control, not "the chance level".

## Files
`run.py`, `config.json`; `results/fixchecks.json`; `results/tables.md` (per-day trial table, MEG decomposition, sEMG table).
Reproduce: `.venv\Scripts\python.exe -I experiments/2026-11-12-paper1-r1-analyses/fixchecks/run.py` (MEG part about 8 min).
