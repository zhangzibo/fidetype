# R3 item 4: B2T word decoder re-tuned on fit-A only

Review item: stats review M4(c). Script: [run.py](run.py). Numbers: [results/retune.json](results/retune.json), [results/tables.md](results/tables.md).

## What we did
- The paper tuned the word-decoder grid (LM weight 0.5 / 1.0, edit penalty 4 / 8 / 12, word bonus 3 / 6) on a random 400 of the 812 fit trials. 187 of the 401 clean calibration trials of split A, and 189 of 401 of split B, were in that tuning set.
- We re-ran the same tuning procedure (same grid, same criterion: lowest pooled WER, then highest truth-in-10-best; raw streams) on the 411 fit-A trials of each split only.

## Results
- Split A and split B: the fit-A tuning selects **the same grid point as the paper** (LM weight 1.0, edit penalty 12, word bonus 3). It ranks first of 12 in both splits (fit-A WER 0.157 / 0.162).
- The decoder is therefore identical, and every clean CRC / LTT / plug-in row of split A and B is unchanged (no re-run needed; the script re-runs the rows only if the choice changes).

## Interpretation
> **Our take:** The overlap of the tuning set with the clean calibration set had no effect on the decoder choice. The paper can state: "Re-tuning the word-decoder grid on fit-A only selected the same setting in both splits, so the clean rows are unchanged." The MEG checkpoint selection on validation CER (stats M4(c)) was not re-done here (GPU).
