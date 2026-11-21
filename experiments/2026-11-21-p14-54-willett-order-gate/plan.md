# P14-54: a frame-order-aware offer gate for both `willett-hw` guards (pre-registration, 2026-11-21)

Roadmap: [P14-54](../../wiki/questions/roadmap-standard.md#p14-54-frame-order-aware-no-signal-gate-or-offer-check-for-willett-hw) (gap 150). This is the `willett-hw` part of gap 152 (P5-33).

This plan is committed **before** any feature value of this work is computed on the `willett-hw` data. At that time only these counts are known: the P5-31 re-check ([results](../2026-11-21-p5-31-offer-control/results.md)), the P14-41 / P14-49 test decisions ([P14-49 results](../2026-11-20-p14-49-willett-gate-blocked-lm/results.md)) and the P5-33 result on `t15-m4-13` ([results](../2026-11-21-p5-33-withhold/results.md)).

## 1. Problem

| Guard | `config_id` | Real LTT offers | uniform | frame-shuffled | time-shuffled (user) |
|---|---|---|---|---|---|
| built-in readout (P14-41) | `tcfg-39aac48688b8bd12` | 40 / 40 | 0 / 300 | **297 / 300 (FAIL)** | 6 / 106 |
| LM readout (P14-49, gate C5) | `tcfg-26ae951a20a0cddd` | 40 / 40 | 0 / 300 | **289 / 300 (FAIL)** | 0 / 106 |

Gate C5 and the guard read only per-frame statistics, so they cannot see the frame order (P14-49).

## 2. Mechanism (reused, not new)

The P5-33 `OfferGate(feature, threshold)` of `fidetype.trust.offer_gate`. It acts only on a final OFFER: if `feature < threshold`, the OFFER becomes WITHHOLD. It never changes a COMMIT or a WITHHOLD, so the commit bound, the commit controls and `config_id` do not change. The feature is computed on the frame log-probabilities that the guard decodes (`TrustGuard._last_lp`, after the frame temperature of the guard).

## 3. Candidate features (fixed now)

Higher value = more evidence that the signal was read. `P` = the frame probabilities (T x 98) of the guard.

| # | Name | Definition | Reads the order |
|---|---|---|---|
| W1 | `coherence` | mean over t of `P_t . P_(t+1)`, minus the mean of `P_s . P_t` over all pairs s != t | yes |
| W2 | `coherence_ratio` | (adjacent mean) / (all-pairs mean) - 1 | yes |
| W3 | `nb_coherence` | W1 on the 97 non-blank columns only (blank column left out, rows not normalised again). **New** in this work: the `willett-hw` frames are about 98 % blank (P14-49: median non-blank share 0.016), so the blank column can dominate W1 | yes |
| W4 | `peak` | as P5-33 T5 | no (check) |
| W5 | `neg_entropy` | as P5-33 T6 | no (check) |
| W6 | `nb_share` | as P5-33 T7 | no (check) |

W4-W6 are per-frame statistics. They are in the list as a check of the P14-49 result (expected: they fail on frame-shuffled input). The P5-33 features `p_top1` and `safety` are not candidates here: they are decision scores, and P14-49 / P5-31 show that the guard already offers on frame-shuffled frames at the same scores (they also need a full decision of each uniform input, see section 5).

## 4. Data (val only for the selection)

- Inputs: the P14-41 / P14-48 val and test log-probabilities (`derived/p14-41/lp_*.npz`; the `p14-48` files are byte-identical). Read only.
- Guards: built-in = `derived/p14-41/willett-hw.guard.json` (SHA-256 `b16963ed...`); LM = `derived/p14-49/willett-hw.lm2.guard.json` (SHA-256 `97a6c219...`) with `decode_fn` = the packaged gated LM readout (`ftp.load("willett-hw").lm_readout().decode_fn()`), as in `recheck_willett.py`.
- **Selection set S**: the 66 non-LTT val positions of calibrate's order (`default_rng(sheet.seed = 0).permutation(106)[:26 + 40]`). The same S for both guards (both sheets: seed 0, 26 fit, 40 policy).
- **Selection nulls** (from S only; new generator `default_rng(5454)`, drawn in this order): `idx` = 300 positions drawn from S; then 300 uniform inputs (recipe of `_run_controls`: `log(1/V) + 0.05 N(0,1)` logits, the length of `inputs[idx[k]]`); then 300 frame-shuffled inputs (a random permutation of the frames of `inputs[idx[k]]`). User nulls: the 66 time-shuffled val inputs (`lp_val_timeshuf`) at the S positions.
- **Evaluation** (not used for the selection):
  - V: `recheck_offer_control(gated guard, lp_val_real, null_inputs=lp_val_timeshuf)`: the 40 LTT items and the sheet-seed controls (300 uniform, 300 frame-shuffled; drawn from all 106 val inputs, so some come from S frames in a new order; this is the P5-31 check that the done-when names), and 106 time-shuffled user nulls.
  - T: the 80 test sentences x five inputs (real, time-shuffled, zero, frame-shuffled, uniform), with the P14-41 generators (`item_rng("test", i, kind)`, seed 0): the inputs of the P14-41 / P14-49 test decisions.

## 5. Selection rule (fixed now; separately for each guard)

1. Decide each S item, each frame-shuffled and each user null with the ungated guard. Keep the action and the features (`collect_offer_features`).
2. Uniform nulls (exact fast path): the built-in decoder takes about 10 s per uniform input (P14-41). An OFFER needs `feature >= threshold`, so a uniform input whose candidate feature is below the threshold cannot be a gated OFFER. Each uniform input is decided in full only if one candidate feature reaches its threshold. The features of an undecided uniform input are computed with the same transform as the guard. Check: the first 5 uniform inputs are always decided in full, and their features from the guard must equal the fast-path features (relative tolerance 1e-6). If the check fails, every uniform input is decided in full.
3. Tier 1: threshold `tau_f` = the **smallest** value of f over the m real S OFFERs (so every real S offer stays). A smaller loss of real offers is needed than in P5-33, because the done-when allows only 4 / 80 real inputs gated on test.
4. Count the gated offers on S real and on each selection null (uniform, frame-shuffled, user). Apply the P5-31 rule (`offer_control`, ratio 0.5, p 0.05, rate 0.05; real = the gated S offers).
5. Choose, among the candidates that pass on S, the one with the lowest largest null offer rate. Ties: the first in the table order.
6. If no candidate passes: tier 1b, the same with the threshold at index `floor(0.05 m)` of the ascending real S offer values. If none passes: tier 2, the AND of the two tier-1 candidates with the lowest largest null offer rate, each at its tier-1 threshold. If none passes: no gate for that guard (negative result). The evaluation is then still run for the best tier-1 candidate and reported "for information only".

## 6. Pass rules (fixed now; all must hold for a guard)

| Id | Set | Rule |
|---|---|---|
| R1 | V | `recheck_offer_control(gated guard)` passes every control (uniform, frame-shuffled, user) |
| R2 | V | `commits_match_sheet` is true; LTT commits 0 (unchanged). Margin 0 |
| R3 | V | real LTT offers kept: gated >= ceil(0.90 x 40) = 36 |
| R4 | T | time-shuffled, zero and uniform input: the gated guard emits (COMMIT or OFFER) on at most 4 / 80 each |
| R5 | T | real input gated: at most 4 / 80 real test inputs change from OFFER to WITHHOLD by the offer gate |
| R6 | T | frame-shuffled test input: the P5-31 rule passes (null = gated frame-shuffled offers / 80, real = gated real offers / 80) |
| R7 | T | commits on every test input are the same as without the gate (0 for both guards). Margin 0 |

Gap 150 closes only if R1-R7 hold for **both** guards. If all rules hold for one guard, its gate is wired into the manifest (section 7) and the other guard is reported as a negative result with numbers.

Uniform test inputs use the fast path of section 5 step 2 (with the same 5-input check). Every other test input and every V input is decided in full.

## 7. If a guard passes: packaging

- Manifest `willett-hw.json`: `trust.offer_gate` (built-in guard) and `readouts.lm.trust.offer_gate` (LM guard), as 9ce8006 did for `t15-m4-13`. The `offer_control` block shows the gated re-check (`results/recheck-*-gated.json`); the P5-31 counts stay under `before_gate`.
- `PretrainedDecoder.guard(readout="lm")` applies the readout gate by default; `offer_gate=False` switches it off. The parser checks `readouts.<r>.trust.offer_gate`. The guard files do not change (same bytes, same `config_id`).
- Tests: `tests/test_pretrained_offer_control.py` (manifest = re-check JSON, gate on by default, off with `False`), `tests/test_trust_offer_gate.py` (`nb_coherence`).

## 8. Not in this plan

- The default `offer_control="refuse"` (a decision for the user).
- `kt-semg-lda` (gap 152).
- Any change to gate C5 (gap 151 = P14-55).

## 9. Compute

CPU only (no GPU), `python -m fidetype.utils.isolation run --class background --threads 2`, detached, log and DONE file in `C:\Users\zhang\bci-data\derived\p14-54\`. Expected: LM guard about 10 min in all; built-in guard about 75 min (the V re-check decides 300 uniform inputs in full, about 1 h, as in P5-31). Peak memory about 1.2-1.6 GB per process.

Script: [run.py](run.py) (stages `select`, `eval`; argument `builtin` or `lm`). Outputs: `results/*.json` (counts and thresholds only). Per-item files stay in `derived/p14-54/`.
