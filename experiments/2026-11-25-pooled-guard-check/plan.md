---
title: Pooled-guard check - can the B1 base-rate failure happen in our text guards? - pre-registration
type: experiment-plan
task: diagnostic after P16-06 B1 (results 994212f)
updated: 2026-11-25
---

# Pooled-guard check (pre-registration)

Written and committed **alone**, before any null run or per-user count. CPU only. No GPU. No shipped guard, card or published number changes because of this check.

## Why
B1 (`experiments/2026-11-24-b1-memory-state-gate/results.md`, diagnosis) found a failure mode: a gate calibrated on a **pool** of subjects with **different base rates**, with a per-subject calibration step, certified on label-permuted and noise input. The score had learned each subject's base rate, not moment-level signal. This check asks if the same failure can happen in our text guards that pool calibration data over users (or over sessions of one person).

## Questions
1. Which shipped or published text guards pool calibration data over users or sessions?
2. For each: is a per-user (per-session) step or feature present that can let the commit score encode the user?
3. Does an across-user label null still certify (B1 failure)?
4. Does any user exceed the bound while the pool meets it?

## Guards in scope (from the manifests and the benchmark cards; fixed now)
| id | guard / card | pool | method | test commits (card) |
|---|---|---|---|---|
| E-S | `emg2qwerty__p11-12-intended-s-subset8__guard` (P11-12 arm S) | 8 users | drop-in LTT, `p_top1` | 167 |
| E-SL | `emg2qwerty__p11-12-intended-sl-subset8__guard` (arm SL) | 8 users | drop-in LTT, learned score | 194 |
| E-LFL | `emg2qwerty__p11-14-intended-lfl-subset8__guard` (P11-14 L-FL) | 8 users | drop-in LTT on an external learned confidence | 285 |
| M-CRC, M-LTT | `spanishbcbl-meg__convctc-m-async__{crc,ltt}` | 19 participants | CRC / LTT on the harness score | 14 / 15 |
| T-CAL, T-XS | `toronto-semg__cnn-{calib,xsession}__crc` | participants | CRC | 21 / 10 |
| S-T15 | shipped `t15-m4-13` guard (`tcfg-1016759f08a3f9a1`; card `b2t25-t15__m4-13__guard`) | sessions of one person | drop-in LTT | 19 |
| S-T12 | `b2t24-t12__t12v2__guard` | sessions of one person | drop-in LTT | 17 |
| S-B2T | `b2t25-t15__{ours,published}__{crc,ltt}` | days of one person | CRC / LTT | from the cards |

Pooled guards with **0 test commits** (`emg2qwerty__lda-oracle__guard`, `emg2qwerty__p11-01-crt-subset8__guard`, `toronto-semg__cnn-xsubject__crc`, `kt-semg__lda-oracle__guard`, the shipped `willett-hw` and `kt-semg-lda` guards) are listed only: with no commit, no user can exceed a bound. The `emg2qwerty-p11-01` and `t12-v2` manifests ship no guard; `toronto-semg-cnn` is planned only.

## Nulls (label nulls; the existing input-level nulls stay as they are)
Label = "the committable top-1 is right". Items with no committable output (gate, empty n-best) keep their label and take no part.

| null | what it does | keeps |
|---|---|---|
| **NX** across-user swap (primary) | a random derangement of the users; user u's items get labels drawn without replacement (with replacement if too few) from user pi(u)'s labels | the label mix, but on the wrong user |
| NW within-user permutation | labels permuted inside each user (the B1 N1 analogue) | each user's base rate |
| NP pooled permutation | labels permuted over all items | nothing per user |

20 runs per null (seeds 1-20).

**Recalibration.**
- E-S, E-SL, E-LFL: the **full shipped recipe** again (`fidetype.trust.calibrate`, same arguments, same seed-0 split, same null-control inputs), on texts built from the permuted labels: label right -> truth = the decoder's top-1; label wrong -> the original truth if it was wrong, else the truth of another calibration prompt of the same user that differs from the top-1. For E-LFL the P11-14 confidence model is fitted again on the tuning items with the permuted labels (P11-14 `Learned.fit`), as P11-14 did. The library code is a clean copy of `src/` at the commit of this plan (other agents edit the working tree).
- M-CRC, M-LTT: score level. The calibrated harness score of each val item is kept (from `items-meg-async.json`); the commit loss is permuted and the shipped threshold step (`crc_threshold` / `ltt_threshold`, same alpha, delta and grid) is run again. Deviation from a full refit: the temperatures are not refitted on permuted labels. A refit on labels without signal can only make the score less sharp, so this is the less strict choice.
- T-CAL, T-XS, S-T15, S-T12, S-B2T: no null. Their calibration-item scores are not stored under `derived/`, and a full rerun needs data outside it (Toronto logits) or a long phoneme-word decode (T15). Per-group breakdown only.

**Certified run:** the recalibration returns a guard (no `NullControlError`) with a finite commit threshold **and** at least 1 in-sample commit on the LTT (CRC: calibration) items.

## Pass rules (per guard)
- **R1 (primary):** NX certifies in **<= 4 of 20** runs (the share B1's N1 allowed).
- **R1-ref:** the guarantee is on wrong commits over **all** items, so a few top-score commits can be certified with no signal at all. If NP also certifies in > 4 of 20, an R1 failure is read as "loss type, not user identity", and R2 decides.
- **R2 (user identity leaks):** fail if the in-sample commit counts of NW (or of NX) are larger than those of NP: one-sided Mann-Whitney p < 0.01 over the 20 + 20 runs.
- **R3 (per group):** for every user / participant / session with **n >= 36** test items, the Clopper-Pearson 95 % (two-sided) upper bound of its wrong-commit rate on the real test decisions is **<= 2 alpha** (0.10 for alpha 0.05). (n >= 36 is the smallest n where 0 wrong gives an upper bound <= 0.10.)
- **R3b:** if no group of a guard has n >= 36, R3 is replaced by a permutation test of heterogeneity: statistic = largest group wrong-commit rate; group labels permuted over the test items 10,000 times; fail if p < 0.01.
- **Outcome:** a guard **passes** if (R1, or R1-ref with R2 pass) and R2 and R3 (or R3b) hold. Guards without a null are judged on R3 / R3b only. A failure is reported as a **safety finding**. The guard, its card and its published numbers do not change.

## Descriptive outputs (not rules)
- Per-group base rate (share of right top-1) on calibration and test; spread; cal -> test correlation over groups (B1: r = 0.81).
- How much of the commit score is the group: eta squared of the score on the group (committable items).
- The B1 own-group check: commit precision vs the commit-weighted own-group base rate.
- Question 2 (per-user features) from the code and the cards: personal decoders, per-session normalisation, per-session day layers, per-session calibration.

## Data and privacy
- Read only: `C:/Users/zhang/bci-data/derived/` (P11-09, P11-11, P11-12, P11-14, P6-01, P6-02, P6-02b, P14-05, M4-13 files) and the Spanish BCBL val `labels.jsonl` (participant ids only). Never `derived/p15-50`.
- Write only: `C:/Users/zhang/bci-data/derived/pooled-guard-check/`.
- The repo gets aggregates only: counts and ranges, no per-user value for emg2qwerty (research-only licence), no text, no id.

## Compute
CPU only, below-normal priority, at most 3 worker processes with 1 thread each. Expected: about 1 min per emg2qwerty recalibration, 180 recalibrations, about 1 h wall time.
