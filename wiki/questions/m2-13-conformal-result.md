---
title: "M2-13 result: conformal risk control for the wrong-commit limit"
type: question
tags: [trust, conformal, risk-control, wrong-commit, b2t25, meg, ewpm]
sources: [conformal-risk-control, learn-then-test, brain-to-text-25-copytask]
updated: 2026-11-11
---

# M2-13 result: does the 0.05 wrong-commit target now hold?

**Short answer:** yes in expectation, with CRC, on exchangeable data. Not for every session. Not under drift.

All tables: [experiment results](../../experiments/2026-11-11-m2-13-conformal/results.md). Method: [conformal risk control](../concepts/conformal-risk-control.md).

## Setup in brief
- The same trust pipelines as [M6-06](b2t25-trust-result.md) (B2T '25, 816 test trials) and the [M1-15 full-r1](m1-15-full-r1-r3-result.md) MEG streams (637 test trials). Only `commit_p` changes.
- 200 random calibration / test splits of each test set; n_cal = 100 or 408. α = 0.05, δ = 0.1.

## Main table (n_cal 408)
| data | method | wrong-commit mean | p95 | commit rate | eWPM |
|---|---|---|---|---|---|
| B2T, our decoder | old gate | 0.0586 | 0.071 | 0.233 | 11.57 |
| | CRC | **0.0483** | 0.071 | 0.194 | 11.53 |
| | LTT | **0.0345** | 0.056 | 0.156 | 11.52 |
| B2T, published gate | old gate | 0.0441 | 0.059 | 0.471 | 18.77 |
| | CRC | **0.0478** | 0.076 | 0.479 | 18.78 |
| | LTT | **0.0345** | 0.061 | 0.427 | 18.70 |
| MEG full-r1 | old gate | 0.0000 | 0 | 0.000 | 3.23 |
| | CRC | 0.0186 | 0.031 | 0.019 | 3.22 |
| | LTT | 0.0207 | 0.035 | 0.021 | 3.22 |

Gaze typing alone: 4.08 eWPM (B2T), 3.15 (MEG).

## What we learn
1. **CRC fixes the mean.** The old gate exceeded 0.05 on our decoder (0.059). CRC gives 0.046–0.048 on both B2T decoders, also with only 100 calibration trials.
2. **The cost is small.** With CRC at 408 calibration trials: −0.3 % eWPM (ours), +0.1 % (published). LTT: −0.4 % at 408, −0.9 % / −1.4 % at 100.
3. **The tail is wide.** With CRC, 41–45 % of splits are above 0.05 on test, and the 95th percentile is 0.071–0.076. LTT cuts the 95th percentile to 0.056–0.061 and the mean to 0.035.
4. **Drift breaks it.** Calibrated on the earlier half of each day, CRC gave 0.0625 on the later half (our decoder).
5. **CRC spends its budget.** On MEG all commits are wrong. CRC still commits 1–2 % of trials, because 0.019 < 0.05. It gains no eWPM. Use `combine="max"` with an eWPM-tuned threshold, or a lower α, if the budget should not go to useless commits.

> **Our take:** For Paper 1, state the claim as "expected wrong-commit ≤ 0.05 under per-session calibration (CRC); with LTT, mean 0.035 and 95th percentile 0.056", not as "wrong-commit ≤ 0.05". The drift result supports adaptive, in-session re-calibration as the next step.

## Related
- [Conformal Risk Control](../sources/conformal-risk-control.md), [Learn then Test](../sources/learn-then-test.md)
- [B2T '25 trust result](b2t25-trust-result.md), [Trust core v0 results](trust-core-v0-results.md)
