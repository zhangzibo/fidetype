---
title: Pooled-guard check - can the B1 base-rate failure happen in our text guards? - results
type: experiment-results
task: diagnostic after P16-06 B1 (results 994212f)
plan: plan.md (8dde818)
updated: 2026-11-25
---

# Pooled-guard check: results

**Short answer.** The exact B1 failure (a certificate that comes **only** from user base rates) does not happen in our text guards. No guard has a per-user step fitted on labels (B1 had a per-subject Platt step). The real certificates are far above every label null. But a **weak form** of the B1 mechanism is present in the two P11-12 emg2qwerty guards: with labels permuted **inside** each user, recalibration certifies more commits than with labels permuted over the pool. So part of the score is "which user", from the personal decoders. Also, by the pre-registered per-user rule, **one user** exceeds the pooled bound in all three emg2qwerty guards, and some **sessions / days** exceed it in the single-person T12 and B2T '25 cards. By the plan rules this is a **safety finding** for 3 published emg2qwerty cards and 6 session-pooled cards. No guard, card or published number was changed.

The guarantee itself is not broken. It is a bound on the **pool** ([trust-guarantee](../../docs/trust-guarantee.md), section 4: "A bound per user, per session or per sentence type" is **not** guaranteed). The finding is that this documented limit is real and measurable in our published cards.

## Run record
| item | value |
|---|---|
| plan | `8dde818` (committed alone, before any null run) |
| code | `run.py`, `test_pooled.py` (`c380617`); full suite 1,978 passed, 45 skipped |
| library | clean copy of `src/` at `8dde818` (other agents edit the working tree) |
| emg2qwerty recalibrations | 183 (3 reproductions + 3 arms x 3 nulls x 20 seeds), full shipped recipe, 0 refused |
| compute | CPU only, below-normal priority, 3-5 processes x 1 thread, about 70 min; no GPU; `derived/p15-50` not touched |
| data written | `C:/Users/zhang/bci-data/derived/pooled-guard-check/` only |
| repo | this page and `results/summary.json`: aggregates only. No per-user value for emg2qwerty (research-only data), no text, no id |

**Reproduction checks.** E-S and E-SL recalibrated with the real labels give the shipped `config_id` (`tcfg-3875f995e4c256fb`, `tcfg-0cd6e9578e965f42`), threshold and LTT commits (71 / 16 wrong; 80 / 16). E-LFL gives the shipped threshold 0.63 and LTT commits 108 / 16 wrong, and the same confidence-model digest; its `config_id` differs (`tcfg-4b2192820e68660b` vs `tcfg-2351fc8f1e60b9e7`), most likely from the decoder label of the module-loaded callable; the decisions are the same. All per-group counts reproduce the card totals exactly (commits, wrong commits, n).

## Q1 and Q2: which guards pool, and can the score encode the user?
| id | card / guard | pool | per-user or per-session step | label-fitted per-user step (B1 type)? |
|---|---|---|---|---|
| E-S, E-SL | `emg2qwerty__p11-12-intended-{s,sl}-subset8__guard` | 8 users | personal decoder per user (fine-tuned P11-01 weights); temperatures, gate and LTT pooled | no |
| E-LFL | `emg2qwerty__p11-14-intended-lfl-subset8__guard` | 8 users | personal decoder; the learned confidence uses `kps` (key rate: typing speed differs by user) | no |
| M-CRC, M-LTT | `spanishbcbl-meg__convctc-m-async__{crc,ltt}` | 19 participants | one decoder for all participants; pooled temperatures | no |
| T-CAL, T-XS | `toronto-semg__cnn-{calib,xsession}__crc` | 19 participants | one CNN trained on day 1 of all participants (calib: + half of day 2); per-session channel scale (label-free) | no |
| S-T15 (shipped `t15-m4-13`) | `b2t25-t15__m4-13__guard` | sessions of one person | per-session day layer; dataset z-score | no |
| S-T12 | `b2t24-t12__t12v2__guard` | sessions of one person | per-session day layer; rolling per-session z-score | no |
| S-B2T | `b2t25-t15__{ours,published}__{crc,ltt}` | days of one person | per-day layers of the published RNN | no |

Not checked further (0 test commits, so no group can exceed a bound): `emg2qwerty__lda-oracle__guard`, `emg2qwerty__p11-01-crt-subset8__guard`, `toronto-semg__cnn-xsubject__crc`, `kt-semg__lda-oracle__guard`, and the shipped `willett-hw` and `kt-semg-lda` guards. The `emg2qwerty-p11-01` and `t12-v2` manifests ship no guard. **No shipped manifest guard pools users**; the shipped `t15-m4-13` guard pools sessions of one person.

**How much of the score is the user (emg2qwerty, test, committable prompts).** User base rates (share of right top-1) differ a lot, as in B1, and are stable: cal -> test correlation over the 8 users 0.88 (P11-12 decoder) and 0.94 (P11-14 decoder) (B1: 0.81). The user explains 14 % (E-S, E-SL) and 7 % (E-LFL) of the score variance (eta squared). The B1 own-user check is very different from B1: commit precision minus the commit-weighted own-user base rate is **+0.40** (E-S), **+0.45** (E-SL), **+0.40** (E-LFL). B1 neural: +0.09; B1 noise: +0.01. So the real commits carry strong within-user signal.

## Q3: label nulls (in-sample LTT / CRC commits after recalibration)
| guard | real commits | NX certified / 20 | NW certified / 20 | NP certified / 20 | median commits NX / NW / NP | NW > NP (MWU p) | NX > NP (p) | R1 | R2 | null rules |
|---|---|---|---|---|---|---|---|---|---|---|
| E-S | 71 | 16 | 20 | 19 | 9.5 / 23 / 18 | **0.0086** | 0.99 | fail (R1-ref applies) | **fail** | **fail** |
| E-SL | 80 | 20 | 20 | 20 | 20.5 / 25.5 / 20.5 | **0.0028** | 0.46 | fail (R1-ref applies) | **fail** | **fail** |
| E-LFL | 108 | **6** | 6 | 4 | 0 / 0 / 0 | 0.14 | 0.17 | **fail** (R1-ref does not apply) | pass | **fail** |
| M-CRC | 14 (val) | 20 | 20 | 20 | 14 / 14 / 14 | 1.0 | 1.0 | fail (R1-ref applies) | pass | pass |
| M-LTT | 14 (val) | 20 | 20 | 20 | 14 / 14 / 14 | 1.0 | 1.0 | fail (R1-ref applies) | pass | pass |

Null runs certify with few commits, and most of them wrong (median 0-15 wrong of 459 LTT items, at most 16). This is allowed by the guarantee: it bounds wrong commits over **all** items, so a few commits are safe with no signal at all (plan, R1-ref). The null maxima (32 / 37 / 32 commits) stay far below the real certificates (71 / 80 / 108).

- **E-S, E-SL (R2 fail).** With each user's base rate kept (NW), recalibration certifies about 5 more commits than with pooled labels (NP). This is the B1 mechanism in a weak form: the personal decoders make high-accuracy users also high-confidence users, so the threshold partly selects users.
- **E-LFL (R1 fail).** NX certifies in 6 of 20 runs (limit 4), NP in 4. The NX and NW counts are not larger than NP (p 0.17, 0.14). The R1 failure is narrow and the plan reads it as a fail.
- **M-CRC, M-LTT.** Only 14 of 437 val items have a finite commit score. The threshold step commits all 14 under every null, the same as with real labels. The certificate is label-blind here: it is "commit the rare committable items", allowed because 14 / 437 < alpha. On test, 13 of 14 (CRC) and 14 of 15 (LTT) commits are wrong. This is not a user-identity effect (R2 pass), but these entries have no evidence of signal in the commit step.
- T-CAL, T-XS, S-T15, S-T12, S-B2T: no null (plan: calibration scores not under `derived/`).

## Q4: per-group wrong-commit rate on test vs the pooled bound (alpha 0.05)
| guard | n | commits / wrong | pooled rate [CP 95 % upper] | groups (n >= 36) | rule | groups above 2 alpha (CP upper) | post hoc: groups with point rate > alpha / CP lower > alpha / heterogeneity p | outcome |
|---|---|---|---|---|---|---|---|---|
| E-S | 1,221 | 167 / 35 | 0.029 [0.040] | 8 (8) | R3 | **1 of 8** | 1 / 0 / 0.056 | **FAIL** |
| E-SL | 1,221 | 194 / 31 | 0.025 [0.036] | 8 (8) | R3 | **1 of 8** | 2 / 0 / 0.023 | **FAIL** |
| E-LFL | 1,221 | 285 / 52 | 0.043 [0.055] | 8 (8) | R3 | **1 of 8** | 1 / 0 / 0.66 | **FAIL** |
| M-CRC | 637 | 14 / 13 | 0.020 [0.035] | 19 (3) | R3 | 0 of 3 | 5 / 1 / 0.020 | pass |
| M-LTT | 637 | 15 / 14 | 0.022 [0.037] | 19 (3) | R3 | 0 of 3 | 5 / 1 / 0.025 | pass |
| T-CAL | 551 | 21 / 2 | 0.004 [0.013] | 19 (0) | R3b, p = 1.0 | - | 0 / 0 / 1.0 | pass |
| T-XS | 551 | 10 / 2 | 0.004 [0.013] | 19 (0) | R3b, p = 1.0 | - | 0 / 0 / 1.0 | pass |
| S-T15 (shipped) | 103 | 19 / 3 | 0.029 [0.083] | 9 (0) | R3b, p = 0.77 | - | 3 / 0 / 0.77 | pass |
| S-T12 | 880 | 17 / 9 | 0.010 [0.019] | 24 (20) | R3 | **9 of 20** | 0 / 0 / 1.0 | **FAIL** |
| S-B2T ours CRC | 816 | 199 / 51 | 0.063 [0.081] | 14 (12) | R3 | **12 of 12** | 10 / 0 / 0.997 | **FAIL** |
| S-B2T ours LTT | 816 | 159 / 38 | 0.047 [0.063] | 14 (12) | R3 | **9 of 12** | 6 / 0 / 0.96 | **FAIL** |
| S-B2T published CRC | 816 | 405 / 40 | 0.049 [0.066] | 14 (12) | R3 | **8 of 12** | 6 / **1** / 0.042 | **FAIL** |
| S-B2T published LTT | 816 | 364 / 33 | 0.040 [0.056] | 14 (12) | R3 | **8 of 12** | 2 / **1** / 0.023 | **FAIL** |

How to read the R3 failures:
- **emg2qwerty (E-S, E-SL, E-LFL).** One user (about 153 test prompts) has a wrong-commit rate of about 0.065 in all three guards, above alpha, while the pool is at 0.025-0.043. Its CP upper bound is above 0.10. Its CP lower bound is below alpha, so the excess is not proven for this user. It is the user with the most commits. This matches the R2 result: the threshold favours high-confidence users, and their wrong commits then weigh more.
- **S-T12.** 20 sessions of 40 trials. Every session with 1 wrong commit has CP upper 0.13; no session is above alpha as a point rate (heterogeneity p = 1.0). The failure comes from small n per session: the rule cannot pass with 1 wrong in 40. Low evidence of a real exceedance.
- **S-B2T (days of T15, published RNN outputs + our CRC / LTT).** For the "published" decoder, one day has 9 wrong commits of 50 trials (0.18; CP lower bound above alpha) while the pool meets the bound. This is a clear per-day exceedance. For "ours", the pooled CRC rate (0.063) is above alpha already (as on the card); the days are homogeneous (p 0.96-0.997).
- **M-CRC, M-LTT** pass by the rule (the 3 large participants have 0 wrong), but post hoc the wrong commits sit in 6 small participants; one has 5 wrong of 32 (CP lower above alpha).

## Outcome per guard
| outcome | guards |
|---|---|
| **FAIL: user identity in the certificate (R2) + one user above the bound (R3)** | E-S, E-SL (P11-12 cards) |
| **FAIL: NX 6 / 20 (R1) + one user above the bound (R3)** | E-LFL (P11-14 card) |
| **FAIL: groups above the bound (R3)** | S-T12 (small-n effect), S-B2T ours CRC / LTT, S-B2T published CRC / LTT (one day clearly above alpha) |
| pass | M-CRC, M-LTT (label-blind commit step, see Q3), T-CAL, T-XS, S-T15 (the shipped `t15-m4-13` guard) |

## Safety findings (report only; nothing changed)
1. **F1 - weak user-identity leak in the pooled emg2qwerty guards (E-S, E-SL).** Within-user label permutation certifies more commits than pooled permutation (MWU p 0.0086, 0.0028). The certificate is still mostly within-user signal (+0.40 to +0.45 over the own-user base rate; real 71 / 80 commits vs null median 23 / 25.5).
2. **F2 - per-user bound not met for one of 8 emg2qwerty users** in E-S, E-SL and E-LFL (point rate about 0.065 > alpha, CP upper > 0.10, not significant). The cards' scope line says "marginal over test prompts pooled over the 8 users"; a reader can take it as a per-user promise.
3. **F3 - per-day exceedance in the B2T '25 "published" CRC / LTT entries:** one day clearly above alpha (9 / 50).
4. **F4 - label-blind commit step in the SpanishBCBL CRC / LTT entries:** the same 14 commits under every label null; 13-14 of 14-15 test commits wrong.
5. The shipped `t15-m4-13` guard and the Toronto cards pass. No shipped manifest guard pools users.

> **Our take:** the B1 lesson transfers in a weak form. A pooled LTT guard over users with personal decoders partly certifies "which user" (F1), and the per-user rate then spreads around the pooled bound (F2). Two changes would close it, both outside this diagnostic: (a) add an across-user / within-user label null to `calibrate` (the NW-vs-NP check costs about 40 recalibrations), and (b) state the per-user scope on multi-user cards, or certify per user (or with a per-user stratified LTT) when each user has enough items. For T12 and the B2T days, per-session bounds need far more trials per session than the cards have.

## Caveats
- The rules follow the plan exactly. The post-hoc columns (point rate > alpha, CP lower > alpha, heterogeneity p) are not pre-registered and are not tests of the outcome.
- R3 with n about 150 (emg2qwerty) or 40 (T12) has low power. A CP upper above 0.10 is not proof of a rate above alpha.
- The MEG nulls are score-level: the temperatures were not refitted on permuted labels (plan deviation, stated before the run).
- Toronto, T15, T12 and B2T have no label null (plan).
- 8 emg2qwerty users only; one track-test session each.

## Files
- `results/summary.json`: all aggregates and rule results (no per-user value for emg2qwerty, no text, no id).
- Local only (not committed): per-run records, per-group tables and logs in `C:/Users/zhang/bci-data/derived/pooled-guard-check/`.
