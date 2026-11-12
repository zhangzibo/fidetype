# R1 item 6: CRC / LTT with small calibration sets

Review items: domain review M9 (n_cal 20–50, within-day calibration); methods review Major 4 (LTT 90th percentile, calibration-conditional risk) and Minor 6 (session-start block). Analysis only (CPU, about 1 min). Date: 2026-11-11.

## Answer
1. **CRC keeps the mean at or below α at every n_cal, but the spread grows fast.** Random exchangeable splits, B2T ours: n_cal 20 / 50 / 100 / 408 → mean 0.031 / 0.034 / 0.046 / 0.048; 90th percentile 0.089 / 0.071 / 0.075 / 0.069; share of splits above α 0.22 / 0.21 / 0.38 / 0.43. Published gate and sEMG calib give the same pattern.
2. **LTT (δ = 0.1) cannot commit at n_cal 20** (the exact binomial p-value P(Bin(20, 0.05) = 0) = 0.36 > δ), so it never commits; at n_cal 50 / 100 its 90th percentile is ≤ 0.050 on all devices (largest 0.0499) and its share above α is ≤ 0.09 (≤ δ, as LTT promises for R(λ̂); here estimated on the large complement).
3. **CRC at n_cal 20 often cannot commit either.** It needs ≥ 19 items and almost no wrong top-1 among the highest scores: B2T ours never commits in 17 % of random splits and 30 % of clean deployment draws; sEMG cross-session in 61–80 %.
4. **Per-session calibration (the Discussion's "session-start block")**: B2T, calibrate on the first 20 trials of each day, test on the rest of that day: CRC wrong-commit 0.0088 (ours) / 0.0252 (published), commit rate 0.040 / 0.324; 6 of 14 days (ours) never commit; LTT never commits. sEMG, first 20 sentences per participant: CRC 0.022 (calib), 9 of 18 participants never commit.
5. **Error among commits does not change with n_cal**: about 0.22–0.25 (B2T ours), 0.06–0.10 (published), 0.12–0.20 (sEMG calib), 0.43–0.63 (sEMG cross-session), 0.82–0.93 (MEG). CRC controls the marginal rate only.

> **Our take:** a 20–50-sentence session-start block is enough for CRC to be valid on average, but it makes the layer commit rarely or never, and LTT needs at least 45 items (0.95^n ≤ δ). The Discussion should say this, and should recommend the block as a warm start for an online controller (as methods review W10 suggests).

## Protocols
| protocol | data | what |
|---|---|---|
| random | committed item tables: M2-13 (B2T), M2-16 (sEMG), G1 (MEG) | 500 random cal / test splits inside the test pool; n_cal 20, 50, 100 and the paper's size (408 / 275) |
| deploy | `clean-drift` items (clean calibration pool → whole test half) | 500 draws of n_cal items from the clean pool; plus the full pool |
| per session | `clean-drift` items | B2T: per day, sequence = that day's clean calibration trials then its test trials (file order); calibrate on the first 20 / 30, test on the rest of the day's test trials. sEMG: per participant, first 20 test sentences calibrate, the rest test (30 does not fit: about 29 per participant) |

## Files
`run.py`, `config.json`; `results/smallcal.json` (all numbers); `results/tables.md` (all rows: mean, p90, p95, share > α, commit rate, error among commits, never-commit share, eWPM).
Reproduce: `.venv\Scripts\python.exe -I experiments/2026-11-12-paper1-r1-analyses/smallcal/run.py`.
