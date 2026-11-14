# P12-03 continuous control: pre-declared plan

Written and committed **before any decoding run**. The only data step before this plan is the NWB to NPZ conversion (`convert_mc_rtt.py`) and a look at the bin counts, the speed percentiles and the target grid (needed to fix the bin size, the clamp rule and the target radius below). No decoder was fitted.

## Question
Can a simple causal decoder plus a control trust layer (FEP-0005 draft) give continuous 2D velocity output with (1) calibrated conformal intervals, (2) a gain/hold policy that never moves on no-signal input, and (3) honest numbers on public data?

## Data
| Set | Licence | Use |
|---|---|---|
| NLB MC_RTT, DANDI 000129 v0.241017.1444, `sub-Indy_desc-train_behavior+ecephys.nwb` | CC-BY-4.0 | Main evaluation |
| BrainGate long-term unsupervised recalibration, Dryad 10.5061/dryad.1jwstqk6g | CC0 1.0 | Planned. The Dryad API returned 401 (download needs a bearer token). Not in this run unless the user downloads it. If it is added later, the same metrics apply. |

MC_RTT: one monkey (Indy), self-paced reaches to random targets on an 8 x 8 grid (spacing 15 mm), 649.1 s, 130 sorted units, finger velocity and cursor position at 1 kHz. Only the NLB *train* file is used (the test file has no behaviour). Raw and derived files stay in `C:/Users/zhang/bci-data/`; the repository gets aggregate numbers only.

Preprocessing (fixed): 20 ms bins (50 Hz update rate); spike counts per unit; target = mean finger velocity (x, y) in the bin, mm/s; cursor and target position at the bin end, mm; frame = the task plane as recorded (x right, y up).

## Splits (fixed)
- **Main split** (blocked by time, no shuffling): fit = bins [0, 40 %), scale = [40, 50 %), calibration = [50, 70 %), test = [70, 100 %).
- **Rotations** (robustness): 5 contiguous folds of 20 %. For fold k: test = fold k, calibration = fold k-1 (cyclic), fit + scale = the other 3 folds in time order (scale = the last 20 % of their bins). Report mean and range over the 5 rotations.
- Nothing from the calibration or test block is used to fit the decoder or the scale model. The test block is used only for the metrics below.

## Decoder (fixed, our own code, numpy only)
- **Primary:** causal linear (Wiener) filter = ridge regression on sqrt spike counts of the current and the 9 previous bins (200 ms history, no future bins), features standardised on the fit block. Ridge lambda from {1, 10, 100, 1000, 10000} by 5-fold blocked CV inside the fit block (R²).
- **Secondary (optional, may be dropped for time; if dropped, the results say so):** steady-state Kalman filter (state = velocity, linear Gaussian, least-squares fit).

## Control trust layer (fixed reference configuration)
Fitted on the fit, scale and calibration blocks only.
1. **Scale model** sigma(t): ridge regression of log(||residual|| + 1 mm/s) on [||v_hat||, sqrt(total spike count of the last 200 ms)], fitted on the scale block.
2. **Conformal radius** r(t) = q * sigma(t), q = the ceil((n+1)(1-alpha))-th smallest normalised score ||v - v_hat|| / sigma on the n calibration bins. Levels 1 - alpha = 0.80, **0.90 (primary)**, 0.95. Baseline: plain split conformal (sigma = 1).
3. **Conformal shrinkage gain:** v_s = v_hat * max(0, 1 - r / ||v_hat||) (the point of the interval ball closest to zero). If the interval covers the true velocity, ||v_s|| <= ||v_true||.
4. **No-signal reference gate:** v_ns = decoder output on all-zero input. HOLD if ||v_hat - v_ns|| <= r(t).
5. **Signal gate:** HOLD if the total spike count of the last 200 ms < 0.5 x the 0.1th percentile of that total on the calibration block (no labels used).
6. **Clamps:** speed <= v_max = 99.5th percentile of true speed on the fit block; change per tick <= a_max * dt, a_max = 99.5th percentile of |dv/dt| on the fit block.
7. **Dead-man / hand-off:** decision time-to-live 3 ticks (60 ms); authority ramp 0 -> 1 over 1.0 s after an engage (the test block starts with one engage).

## Metrics (test block; main split first, then the rotations)
1. **Decoding:** R² (mean of the x and y R², each 1 - SSE / SST on the test block) and Pearson r (mean of x, y), for the raw decoder output and for the gated output.
2. **Conformal coverage** at 0.80 / 0.90 / 0.95: fraction of test bins with ||v - v_hat|| <= r(t); normalised and plain. Mean radius (mm/s).
3. **Over-speed rate:** fraction of test bins with ||v_out|| > ||v_true||. The gain rule bounds it by the miscoverage when the intervals are valid.
4. **Motion and direction:** fraction of bins with motion (||v_out|| > 0); mean cosine(v_out, v_true) over bins with motion and true speed > 20 mm/s; mean gain ||v_out|| / ||v_hat||.
5. **Paths (offline, open loop):** segments = intervals between target changes, 0.2 s to 5 s long. Integrate the velocity from the true cursor position at the segment start. For true, raw and gated velocity: path efficiency = |p_end - p_start| / path length; endpoint error to the true end position; reached = the path enters a 7.5 mm radius (half the grid spacing) around the segment target; time-to-target = first entry time (median over reached segments). *Caveat:* open-loop replay; a real user corrects errors in closed loop.
6. **Controls** (same fitted configuration; test block): (a) **shuffled spikes** = the time bins of the count matrix permuted (seed 0); (b) **zero input** = all counts 0; (c) **time-reversed** counts. For each: R² raw and gated, mean output speed raw and gated, motion fraction, over-speed rate. Also the zero-input control **without** gates 4-5 (shrinkage only), to show the failure the gates prevent.
7. **Latency** (informative): per-tick compute time of decoder + layer, median and p99, CPU background class.

## Pre-declared criteria
| # | Criterion | Pass if |
|---|---|---|
| C1 | Raw decoder works | test R² (raw) >= 0.3 on the main split |
| C2 | Calibration | coverage at 0.90 within [0.87, 0.93] on the main split (normalised scores) |
| C3 | Speed bound | over-speed rate at 0.90 <= 0.10 + 0.02 on the main split |
| C4 | No motion on zero input | gated mean speed <= 1 % of the mean true speed **and** motion fraction <= 0.01 |
| C5 | Controls carry no information | raw R² <= 0.05 for shuffled and time-reversed input |
| C6 | Rotations | C2 holds in at least 4 of 5 rotations |

Descriptive only (no pass rule): the gated R² and path metrics against raw (we expect a lower gated R², because shrinkage trades speed for safety), and the gated motion on shuffled / reversed input (hypothesis: the gated mean speed is less than half the raw mean speed).

Time-series bins are not exchangeable (autocorrelation, drift within the session). The coverage numbers will show how much that matters. We report every number, including the failed criteria.

## Not in this run
- Click (discrete intent) on real data: MC_RTT has no click. Click goes through FEP-0003; synthetic tests only.
- Closed-loop use, human data (BrainGate is blocked on the download token), multi-day drift.
