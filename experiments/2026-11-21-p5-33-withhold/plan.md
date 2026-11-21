# P5-33: an offer gate that withholds on no-evidence input (pre-registration, 2026-11-21)

Roadmap: [P5-33](../../wiki/questions/roadmap-standard.md#p5-33-offer-policy-that-withholds-on-no-evidence-input-and-the-offer-control-default) (gap 152). Scope: the packaged guards `t15-m4-13` (`tcfg-1016759f08a3f9a1`) and `kt-semg-lda` (`tcfg-d8a73194fe539e72`). The `willett-hw` part is gap 150 (P14-54); it is not in this plan.

This plan is committed **before** any feature value, selection count or test count is computed. At that time only the P5-31 re-check counts are known ([results](../2026-11-21-p5-31-offer-control/results.md)).

## Problem

Under the P5-31 offer null control, both guards offer on every null input:

| Guard | Real offers (LTT) | uniform | shuffled / user nulls |
|---|---|---|---|
| `t15-m4-13` | 217 / 271 | 300 / 300 | frame-shuffled 300 / 300 |
| `kt-semg-lda` | 65 / 65 | 300 / 300 (equal-score n-best lists) | 173 / 173 (key windows drawn at random times) |

## Method

### The mechanism: an offer gate

- New optional object `OfferGate(feature, threshold)` on a `TrustGuard` (code in `fidetype.trust`).
- It acts only on a final decision OFFER. If `feature < threshold`, the OFFER becomes WITHHOLD (`ABSTAIN`, reason "offer gate").
- It never changes a COMMIT and never changes a WITHHOLD. So the commit bound, the commit threshold, the commit null controls and `config_id` stay the same. This plan checks that claim on the data (rules E2, E4).
- `recheck_offer_control` reads the gated decisions (it calls the same decision path).

### Candidate features (fixed now)

Higher value = more evidence that the signal was read.

`t15-m4-13` (logits input; `P` = the frame probabilities that the guard decodes, T x V):

| # | Name | Definition |
|---|---|---|
| T1 | `coherence` | mean over t of `P_t . P_(t+1)`, minus the mean of `P_s . P_t` over all pairs s != t. Expected value 0 under a random frame order. It reads the frame order |
| T2 | `coherence_ratio` | (adjacent mean) / (all-pairs mean) - 1 |
| T3 | `p_top1` | calibrated top-1 probability of the decision |
| T4 | `safety` | 1 - `guard_risk` of the decision |
| T5 | `peak` | mean of the largest frame probability over the frames whose argmax is not blank (0 if none) |
| T6 | `neg_entropy` | minus the mean frame entropy (nats) over the frames whose argmax is not blank (-log V if none) |
| T7 | `nb_share` | share of frames whose argmax is not blank |

`kt-semg-lda` (n-best input):

| # | Name | Definition |
|---|---|---|
| K1 | `p_top1` | as T3 |
| K2 | `safety` | as T4 |
| K3 | `margin` | (score of item 1 - score of item 2) / max(1, characters of item 1); 0 for a one-item list |
| K4 | `conf_mean` | mean character confidence of item 1 (0 if it has none) |
| K5 | `char_lm` | mean log-probability per character of the item-1 text under the packaged character LM `eng_tatoeba_6gram_mkn.npz` |
| K6 | `char_lm_best` | the largest K5 value over the n-best items |

T5-T7 are per-frame statistics. P14-49 showed that such features cannot see frame-shuffled input. They are in the list as a check of that result. K5-K6 read the language of the decoded text, not the signal. The KT key accuracy is 0.248 (manifest), so the power of K5-K6 is not known.

### Data

- **Selection set S** (calibration data that the evaluation does not use as real items): the items of the guard split that are **not** LTT items (order = `default_rng(sheet.seed).permutation(n)`, first `n_fit + n_policy` items). `t15-m4-13`: 451 of 722 val_select trials. `kt-semg-lda`: 108 of 173 bursts.
- **Selection nulls** (from S only, new seed 3305):
  - `t15-m4-13`: 300 uniform and 300 frame-shuffled inputs, same recipe as `_run_controls` (indices drawn from S).
  - `kt-semg-lda`: 300 equal-score n-best lists (same recipe, indices drawn from S), and one user null per S burst (key windows drawn at random from the pool of the same runs, same recipe as `recheck_kt.py`, rng seed 3305).
- **Evaluation set** (not used for the selection): `recheck_offer_control` on the packaged guard with the gate (LTT items + the sheet-seed controls + for `kt-semg-lda` the P5-31 user nulls). For `t15-m4-13` also the held-out val_eval set (701 trials, as in P14-05), with 300 uniform and 300 frame-shuffled inputs made from val_eval (seed 3306).

### Selection rule (fixed now)

For each guard and each single candidate f:

1. Decide every S item and every selection null with the ungated guard. Keep the feature value of each OFFER.
2. Threshold `tau_f` = the value at index `floor(0.05 m)` of the ascending values of the m real S OFFERs (so the gate keeps about 95 % of the real offers).
3. Count the gated offers on S real and on each selection null. Apply the P5-31 rule (`offer_control`, ratio 0.5, p 0.05, real = S real).
4. Choose, among the candidates that pass on S, the one with the lowest largest null offer rate. Ties: the first in the table order.

If no single candidate passes on S: tier 2. For the two single candidates with the lowest largest null offer rate, use both (AND), each with the threshold at index `floor(0.025 m)`. If tier 2 does not pass on S either: no gate for that guard. The result is then a negative result. The evaluation is still run for the best tier-1 candidate and reported as "for information only".

### Pass rules on the evaluation set (fixed now; all must hold for one guard)

- **E1** `recheck_offer_control(gated guard)` passes (every control).
- **E2** `commits_match_sheet` is true, and the LTT commit count does not change (`t15-m4-13`: 54; `kt-semg-lda`: 0). Margin: 0.
- **E3** Real offer rate on the LTT items: gated offers >= ceil(0.85 x ungated offers) (`t15-m4-13`: >= 185 of 217; `kt-semg-lda`: >= 56 of 65).
- **E4** (`t15-m4-13` only) On val_eval: the COMMIT decisions are the same as without the gate (same items, same text; margin 0); gated offers >= ceil(0.85 x ungated offers); and the P5-31 rule passes on the val_eval nulls, with real = the gated val_eval offers.

If all rules hold for a guard, the gate is wired into its packaged manifest (default on, can be switched off), with tests, and the manifest `offer_control` block shows the new re-check. If a rule fails, the guard keeps its present behaviour and the report gives the numbers.

## Not in this plan

- The default `offer_control="refuse"`: a decision for the user. This work only gives a recommendation.
- `willett-hw` (gap 150). T1 is frame-order aware, so it could also be a candidate there; that needs its own plan.

## Compute

CPU only, `python -m fidetype.utils.isolation run --class background --threads 2`. Expected: `t15-m4-13` about 0.3 s per decision (about 2,600 decisions: 15 min); `kt-semg-lda` rebuild of the n-best lists about 5 min.
