# P12-03 continuous control: results

Plan: [plan.md](plan.md) (committed in `208b1c8` before any decoding run). Code: `run_control.py` (pre-declared), `run_explore.py` (**post-hoc**), `tables.py`. Numbers: `results/metrics.json`, `results/explore.json`, `results/zero_no_gates.json` (aggregate only; no recordings in the repository).

Data: NLB MC_RTT train file (DANDI 000129 v0.241017.1444, CC-BY-4.0), one monkey, 649.1 s, 130 units, 20 ms bins (32,455 bins). Test block of the main split: 9,737 bins (195 s). BrainGate (CC0) is **not** in this run: the Dryad file API needs a bearer token (HTTP 401).

## Summary
- The causal Wiener decoder reaches **R² 0.478** (Pearson 0.707) on the test block.
- Split-conformal intervals are **calibrated**: coverage 0.810 / 0.905 / 0.962 at 0.80 / 0.90 / 0.95. In 5 of 5 rotations the 0.90 coverage is in [0.877, 0.923].
- **All six pre-declared criteria pass. But the declared configuration never moves.** At level 0.90 the interval radius (mean 88.6 mm/s) is larger than most decoded speeds (mean 45.8 mm/s). The conformal shrinkage gain is then 0 on every tick. The plan had no utility criterion; that was a flaw of the plan.
- The no-signal problem is real in control form: on all-zero input the decoder drifts at **13.3 mm/s**. The decoder's own `std` does **not** flag it (sigma on zero input 9.5 mm/s, *lower* than on real test input: median 31.4, mean 45.6 mm/s). Without the no-signal gates, shrinkage at level 0.1-0.7 moves on 100 % of zero-input ticks (post-hoc). With the gates: 0 motion at every level.
- A post-hoc level sweep shows a steep trade-off. A per-tick speed bound at a useful coverage level does not fit a decoder with R² near 0.5.

## Pre-declared criteria
| # | Criterion | Result | Pass |
|---|---|---|---|
| C1 | raw R² >= 0.3 (main) | 0.478 | yes |
| C2 | coverage at 0.90 in [0.87, 0.93] (main, normalised) | 0.905 | yes |
| C3 | over-speed at 0.90 <= 0.12 (main) | 0.000 | yes (trivially: no motion) |
| C4 | zero input: gated mean speed <= 1 % of true mean speed and motion fraction <= 0.01 | 0.000 mm/s, 0.000 | yes (also trivially without gates at 0.90; see below) |
| C5 | raw R² <= 0.05 on shuffled and time-reversed input | -0.133 / -0.317 | yes |
| C6 | C2 in >= 4 of 5 rotations | 5 / 5 | yes |

Descriptive hypothesis (gated speed on shuffled / reversed input below half the raw speed): holds (0 vs 29.7 / 44.8 mm/s), again because nothing moves.

## Main numbers
| Measure | Main split | Rotations mean (min-max) |
|---|---|---|
| Raw R² | 0.478 | 0.474 (0.441-0.500) |
| Raw Pearson r | 0.707 | 0.696 (0.666-0.724) |
| Coverage 0.80 (normalised) | 0.810 | 0.802 (0.778-0.824) |
| Coverage 0.90 (normalised) | 0.905 | 0.898 (0.877-0.923) |
| Coverage 0.95 (normalised) | 0.962 | 0.949 (0.932-0.966) |
| Coverage 0.90 (plain, sigma = 1) | 0.908 | 0.901 (0.884-0.912) |
| Mean radius 0.90, normalised (mm/s) | 88.6 | 83.1 (78.6-87.6) |
| Radius 0.90, plain (mm/s) | 120.9 | 110.0 (104.2-118.8) |
| Mean decoded speed (mm/s) | 45.8 | 48.2 (47.5-48.7) |
| Mean true speed (mm/s) | 56.5 | 55.0 (51.6-57.6) |
| Gated R² / motion fraction / over-speed (level 0.90) | 0.000 / 0.000 / 0.000 | same in all rotations (motion <= 0.001) |
| No-signal output speed (mm/s) | 13.3 | 13.7 (10.9-15.9) |
| v_max (99.5th pct of fit speed, mm/s) | 351.8 | 363.8 (353.9-380.2) |
| Ridge lambda (CV) | 10,000 | |

Reasons on the main test block (9,737 ticks): `no_signal_reference` 9,716, `uncertain` 21, (`handoff` 50 during the 1 s ramp). The normalised scale model narrows the interval (88.6 vs 120.9 mm/s for plain conformal) at the same coverage. That is not enough.

## Controls (main split, level 0.90)
| Input | Raw R² | Raw mean speed (mm/s) | Gated mean speed | Gated motion fraction | Over-speed |
|---|---|---|---|---|---|
| Shuffled spikes (time bins permuted) | -0.133 | 29.70 | 0.000 | 0.000 | 0.000 |
| Zero input | -0.021 | 13.32 | 0.000 | 0.000 | 0.000 |
| Time-reversed spikes | -0.317 | 44.79 | 0.000 | 0.000 | 0.000 |
| Zero input, gates off (shrinkage only) | | 13.32 | 0.000 | 0.000 | 0.000 |

Rotations: raw R² shuffled -0.171 to -0.096, reversed -0.323 to -0.303; largest gated mean speed on any control 0.0005 mm/s.

**Post-hoc, zero input with shrinkage only (no quality gate, no reference gate):**

| Level | 0.1 | 0.3 | 0.5 | 0.7 | 0.8 | 0.9 |
|---|---|---|---|---|---|---|
| Motion fraction | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 0 |
| Mean speed (mm/s) | 9.30 | 6.16 | 3.74 | 1.33 | 0 | 0 |
| Drift per 10 s (mm) | 93 | 62 | 37 | 13 | 0 | 0 |

So at any level that moves on real data, the uncertainty alone does not stop zero-input drift. The explicit gates (signal quality; no-signal reference) do.

## Paths (offline, open loop; main split, 167 target segments of 0.2-5 s)
| Velocity | Path efficiency | Endpoint error (mm, median) | Reached (7.5 mm) | Time-to-target (s, median) |
|---|---|---|---|---|
| True (integrated finger velocity) | 0.851 | 0.0 | 0.988 | 0.64 |
| Raw decoder | 0.656 | 29.6 | 0.108 | 0.67 |
| Gated (level 0.90) | 0.000 | 54.3 | 0.000 | n/a |

Open-loop replay is a hard test: there is no user to correct the drift, so a raw decoder with R² 0.48 reaches only 11 % of targets. Closed-loop numbers would be much higher. They need a closed-loop data set (BrainGate) or a simulator with a user model.

## Post-hoc level sweep (not pre-declared)
Layer without the no-signal reference gate (`no_ref`; the quality gate still runs), main split [rotations mean]:

| Level | Motion | Gated R² | Pearson | Over-speed | Mean cos (moving, true > 20 mm/s) | Shuffled motion | Shuffled speed (mm/s) | Zero motion |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 0.96 [0.96] | 0.332 [0.352] | 0.673 | 0.489 [0.504] | 0.770 | 0.937 | 17.32 | 0 |
| 0.2 | 0.91 [0.90] | 0.232 [0.264] | 0.620 | 0.398 [0.411] | 0.780 | 0.849 | 12.11 | 0 |
| 0.3 | 0.83 [0.83] | 0.152 [0.186] | 0.545 | 0.319 [0.328] | 0.785 | 0.751 | 8.45 | 0 |
| 0.4 | 0.72 [0.73] | 0.085 [0.117] | 0.438 | 0.248 [0.248] | 0.799 | 0.636 | 5.44 | 0 |
| 0.5 | 0.58 [0.60] | 0.039 [0.064] | 0.310 | 0.174 [0.177] | 0.816 | 0.489 | 3.01 | 0 |
| 0.6 | 0.40 [0.44] | 0.014 [0.028] | 0.185 | 0.102 [0.111] | 0.825 | 0.319 | 1.24 | 0 |
| 0.7 | 0.18 [0.25] | 0.002 [0.008] | 0.071 | 0.044 [0.057] | 0.834 | 0.098 | 0.21 | 0 |
| 0.8 | 0.03 [0.07] | 0.000 [0.001] | 0.012 | 0.005 [0.014] | 0.874 | 0.002 | 0.00 | 0 |
| 0.9 | 0.00 [0.00] | 0.000 [0.000] | 0.000 | 0.000 [0.000] | n/a | 0.000 | 0.00 | 0 |

With the reference gate (`full`) motion is lower at each level (0.93 at 0.1, 0.44 at 0.5, 0.12 at 0.7) and the other columns change little (`results/explore.json`). The over-speed rate stays at or below 1 - level at every level, as the theory says (for example 0.174 <= 0.5 at 0.5). The direction of the moving output improves with the level (cos 0.77 -> 0.87). Open-loop path metrics are poor at every level (reached <= 0.03).

## Latency (informative)
Streaming decoder step + layer push per tick, CPU background class with other agents on the machine: median 0.09-0.10 ms; p99 0.20 ms (first run) and 1.66 ms (second run, more load); max 16.7 ms. Far below the 20 ms tick.

## Interpretation
> **Our take:** the trust layer is safe here, but useless at the declared level. Conformal shrinkage gives a strong per-tick guarantee ("not faster than the true velocity with probability 1 - alpha"). For a linear decoder on 130 sorted units the per-tick residual is about as large as the movement itself, so a high-level guarantee means no motion. Three ways forward, all for later work: (1) a better decoder (Kalman with a position state, or a nonlinear model; we did not check published MC_RTT baselines here); (2) calibrate the bound on **displacement over a horizon** (0.25-0.5 s), where noise averages out and which is what a user feels (FEP-0005 open question 1); (3) treat the level as a deployment dial with a documented risk (the sweep table is the evidence a deployer needs).

> **Our take:** the no-signal result transfers from text (M2-18) and intents (FEP-0003) to control. A decoder that drifts on zero input, with an uncertainty model that is *more* confident on zero input, will move a cursor while the amplifier is off. Only explicit no-signal inputs (signal quality, a no-signal reference, a dead-man) stop it. FEP-0005 makes these MUST rules.

## Deviations from the plan
- The secondary Kalman decoder was dropped for time (the plan allowed this).
- A bug in the first run gave NaN endpoint errors (15 bins with NaN cursor position). Fix: carry the last valid position forward. Only the path metrics changed; the reported numbers are from the fixed run (`run_control.py` as committed).
- The level sweep and the zero-input-without-gates table are post-hoc (labelled above).
