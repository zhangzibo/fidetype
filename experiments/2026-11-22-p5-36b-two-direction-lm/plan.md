---
title: P5-36b two-direction LM-beam direction score against rev_out - pre-registration
type: experiment
task: P5-36
updated: 2026-11-22
---

# P5-36b: a two-direction LM-beam direction score against `rev_out` (pre-registration, 2026-11-22)

Roadmap: [P5-36](../../wiki/questions/roadmap-standard.md#p5-36-frame-order-integrity-check-in-the-trust-layer) (gap 181; the gap stays open until its done-when is met). Earlier work: [P14-57](../2026-11-21-p14-57-direction-aware-offer/results.md) (a frame statistic at threshold 0: real offers removed 11 / 80 and 17 / 80) and [P5-36](../2026-11-22-p5-36-frame-order/results.md) (route 1, the frame-time check, passes but sees 0 / 80 `rev_out`; route 2, `lm_direction` of the **greedy** text at threshold 0, removes 10 / 80 real offers; val 10 / 66, limit 3).

We commit this plan, [run.py](run.py), [launch.py](launch.py), the library code and the synthetic tests **before** any val or test number of this work is computed. The synthetic tests ran before this commit; they use no real data. The only timing known before the run is synthetic (section 6).

## 1. The idea

The P5-36 `lm_direction` feature scores the **greedy** CTC text. The greedy text has CER 0.305 on test, so for about 1 in 7 sentences the noise hides the direction. The LM-beam readout fixes most of the noisy characters (test CER 0.174). Here we decode the frames **twice** with the LM-beam readout, forward and time-reversed, and compare the two full decode scores. A forward English LM should give a much better decode of the forward frames of real input; for `rev_out` the two decodes change places.

## 2. The statistic (fixed before the run)

New offer-gate feature `lm_beam_direction` (`src/fidetype/trust/offer_gate.py`, logits input, needs `readout=`):

`D(x) = (S(x) - S(rev x)) / ((n(x) + n(rev x)) / 2 + 1)`

| Symbol | Meaning |
|---|---|
| `x` | the `(T, V)` frame log-probabilities that the guard's decoder sees (`guard._last_lp`, after the guard's frame scaler; the same frames as every other logits offer feature) |
| `rev x` | `x` with its rows in reverse order |
| `S(.)` | the total score of the **best beam** of the packaged `willett-hw` LM readout (`m.lm_readout()`, `LMBeam`, settings `lm_weight` 0.5, `bonus` 1.0, `beam` 8, `prune_logp` -8.0), **without** its no-signal gate (`hyps(x, 1, use_gate=False)[0].score`): acoustic log-prob + 0.5 x LM log-prob + 1.0 x tokens, with the end marker `</s>` |
| `n(.)` | the number of tokens of that best beam |
| LM | `eng_tatoeba_6gram_mkn_noE2Q_noWillett` (Tatoeba, every Willett text blocked; P15-38): the LM of the readout |

Properties (known before the data):

- The normaliser is the same for `x` and `rev x`. The beam search is deterministic. So `D(rev x) = -D(x)` **exactly**: `rev_out` gets minus the value of its real input. This is a check of the run (C1, section 4), not an assumption.
- Per-character normalisation (about nats per token) keeps the scale comparable between short and long sentences. A per-frame variant `(S(x) - S(rev x)) / T` is recorded **for description only**; no rule uses it.
- The acoustic part alone is almost symmetric (a CTC path read backward is a path of the reversed text), so `D` mostly measures how much better the LM likes the best forward decode than the best backward decode, after the beam has used the acoustic evidence.

## 3. Objects (fixed)

| Object | Value |
|---|---|
| Built-in guard | `load("willett-hw").guard()`, `tcfg-39aac48688b8bd12`, offer gate `coherence >= 0.004183` |
| LM guard | `load("willett-hw").guard(readout="lm")`, `tcfg-26ae951a20a0cddd`, offer gate `coherence >= 0.002821` |
| Data | Willett handwriting 2021 (T5), CC0 1.0. P14-41 log-probs (`derived/p14-41/lp_{val,test}_*.npz`, read only). S = the 66 non-LTT val positions (`default_rng(0).permutation(106)[:66]`); LTT = the other 40 val positions; test = the 80 last-block sentences (the P14-57 test set) |
| `rev_out` | `lp[::-1]` (the P14-57 form) |
| Gate set under test | the shipped `coherence` gate AND `lm_beam_direction >= tau` (an `OfferGate`: it changes OFFER to WITHHOLD only; no `config_id` change; P5-33 design). Both guards never commit, so the commit path does not matter |

## 4. The threshold fit (val S only, per guard) and the rules

### 4.1 Fit (pre-stated rule)

1. Decide the 66 S val real inputs with the packaged guard (coherence gate only). The m real S offers are the fit set.
2. `tau = OfferGate.fit("lm_beam_direction", D values of the m offers, keep=0.95)`: the value at index `floor(0.05 m)` of the ascending values (index 3 if m = 66). The gate withholds an offer iff `D < tau`.

Why this rule meets the target: it removes **at most `floor(0.05 m)` (3 of 66) real val offers** (fewer only with ties). Every larger threshold removes more than that. Because `D(rev_out) = -D(real)`, the `rev_out` offers are `#{real: D <= -tau}`, which does not increase when `tau` increases. So this `tau` is the threshold that **minimises the `rev_out` val offers** under the real-loss target. Reported on val: `tau`, the real val offers removed, the `rev_out` val offers with both gates. `tau` may be negative; then it is reported as such and used unchanged.

### 4.2 Test rules (single readout; per guard)

| Id | Kind | Rule (pass iff) |
|---|---|---|
| **B1** | primary | `rev_out` (80 test inputs): offers with both gates **<= 4 / 80** |
| **B2** | primary | real test offers removed by the `lm_beam_direction` gate **<= 4 / 80** (reference: coherence gate only) |
| **B3** | secondary | real LTT offers with both gates **>= 36 / 40** (the P14-54 R3 limit; P14-57 D4 real part) |
| **B4** | secondary | P14-54 test nulls (time-shuffled d = 0, zero, frame-shuffled, near-uniform; 80 each): emits with both gates **<= 4 / 80** each. Only the inputs that were coherence-only offers in the P14-57 records (`derived/p14-57/p57.jsonl`) can change; they are made again (stored log-probs or the P14-54 recipe and seed) and must repeat their P14-57 action and `coherence` (1e-6) |
| **B5** | secondary | the P14-55 nulls keep their results (P14-57 D3 rules): for time-shuffled d = 1..10 (800), frame-shuffled (800), near-uniform (800), `rev_in` (80), `do_nothing` (27), `lines` (80): offers with both gates <= the P14-55 offers, and CP95 <= 0.05 (first three) or <= `floor(0.05 n)` (others), and the P5-31 `offer_control` rule against the new real test offers. The P14-55 inputs that were offers (for either guard) are made again from their recipes and seeds (time-shuffled and `rev_in`: the decoder on the raw sentence) and must repeat their P14-55 action and `coherence` |

Checks (must hold, else the result is not valid):

- **C1** antisymmetry: `|D(real) + D(rev_out)| <= 1e-9` on 66 / 66 val and 80 / 80 test pairs, per guard.
- **C2** equivalence: the guard with both gates gives the same action as "coherence action, then withhold if `D < tau`" on the 80 real, 80 `rev_out` and 40 LTT inputs (200 / 200), per guard.
- `coherence` of `rev_out` equals real (1e-9), 80 / 80 (known from P14-55; repeated).

The P14-54 V re-check (`recheck_offer_control`, about 45 min per guard in P14-57) is **not** run again. Reason: its three controls had 0 offers with the coherence gate alone (manifest `offer_control`: uniform 0 / 300, frame-shuffled 0 / 300, time-shuffled 0 / 106, both guards); an added offer gate can only remove offers, and both guards have 0 LTT commits (offer-only). So only its real part can change, and B3 measures that part directly.

### 4.3 Done-when (gap 181)

The done-when reads: the check is in the trust layer (met by P5-36 route 1), tested on synthetic reversed streams (met by P5-36), and the P14-57 `rev_out` test set gives <= 4 / 80 offers with <= 4 / 80 real offers removed. This plan meets the last part **iff B1 and B2 pass for both guards** (with C1 and C2 valid). B3-B5 are secondary: a failure there is reported and gives a new gap, but it does not undo B1 / B2. If B1 or B2 fails, the result is negative ("numbers say why not") and the gap stays open with this evidence.

### 4.4 Reported (descriptive)

`D` on the real test offers (min / 5 % / median / 95 % / max), the per-frame variant, the real test offers with `D < 0`, `n(x) - n(rev x)`; the cost (section 5).

## 5. Cost

Per decision with the gate: two extra beam searches (forward and reversed frames). Reported on the 80 real test inputs: time of the two searches (`t_beam2`, min / 5 % / median / 95 % / max), time of the coherence-only guard decision (`t_decide`), their median ratio, and ms per frame. The gate is lazy (library change): it computes `lm_beam_direction` only for an OFFER that has passed the earlier gates, so a WITHHOLD costs nothing extra. Measured on this machine with 1 thread, background priority, while other jobs run: the times are indicative only.

## 6. Shipping and library code

- Library (opt-in, no default change): `lm_beam_direction`, `beam_score` in `fidetype.trust.offer_gate`; `OfferGate(..., readout=)` (not saved; `lm_name` names the LM); `TrustGuard.offer_readout` (analysis); lazy per-gate features in `TrustGuard._apply_offer_gate` (same decisions as before: the first failing gate gives the reason). Synthetic tests: `tests/test_trust_beam_direction.py` (antisymmetry, sign on English-like phrases, the guard gate withholds every reversed synthetic input, lazy features, file round trip).
- **No packaged gate, guard file, manifest or `config_id` changes.** The manifest loader reads one offer gate per trust block and a saved gate has no readout. If B1 and B2 pass for both guards, we propose a new gap to ship it (list support in the manifest, the readout wiring, the model card, the P14-56 offer-control blocks re-checked).

## 7. Compute

CPU only (`CUDA_VISIBLE_DEVICES`, `HIP_VISIBLE_DEVICES` = -1), `python -m fidetype.utils.isolation run --class background --threads 1`, detached by `launch.py`, keep-awake; working-set limit 3,000 MB; log, `DONE` / `FAILED` / `STOP` and per-item JSONL (restart skips finished items) in `C:\Users\zhang\bci-data\derived\p5-36b\`. Synthetic timing before the run: two beam searches on a `(3793, 98)` synthetic matrix (the median test length) take 0.46 s. About 700 decisions with the feature (val 264, test 320 plus the both-gate decisions, LTT 80, nulls about 50), plus the decoder for about 22 null inputs: estimate 30-60 min. **Cap: 3 h.** If the run is not done after 3 h, it is stopped and the finished parts are reported; no input set is reduced after the start.

Outputs in git: `results/fit.json`, `results/results.json` (counts, thresholds and summary values only) and `results/run.log`. No log-probs, text or per-item records in git.

## 8. Not in this plan

Shipping the gate (section 6); other decoders or LMs; other beam settings; a backward LM; reuse of the LM guard's own forward decode (a possible speed-up).
