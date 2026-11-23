---
title: P5-37 fixed threshold 0 for lm_beam_direction on the willett-hw pool - pre-registration
type: experiment
task: P5-37
updated: 2026-11-22
---

# P5-37 (option A): fixed threshold 0 for `lm_beam_direction` on the 781 pool sentences (pre-registration, 2026-11-22)

Roadmap: [P5-37](../../wiki/questions/roadmap-standard.md#p5-37-fixed-threshold-0-rule-for-the-lm_beam_direction-offer-gate) (gap 189). Earlier work: [P5-36b](../2026-11-22-p5-36b-two-direction-lm/results.md) (`dab694f`, `a7bfbc8`). Data audit: [results.md](results.md) of this folder (`5d74a8e`): no clean unused `willett-hw` data exists. The user chose **option A** (2026-11-22): the decoder's training pool, with the bias stated in advance.

We commit this plan, [run.py](run.py) and [launch.py](launch.py) **before** any gate number on the pool is computed. Before this commit, the code ran only on 2 val sentences (already-used data) as a code test (`run.py smoke`).

## 1. What is stated in advance

- **The data is decoder-seen.** P15-08 trained the `willett-hw` decoder on every pool sentence, with labels. Frames are probably cleaner there than on new data, so `D` is probably larger. So this test is **optimistic** for both primary rules.
- **A fail is final** for the fixed-threshold-0 idea on `willett-hw`: if the rule fails on decoder-seen data, it fails on new data too, as far as we can tell. Gap 189 then closes as a negative result.
- **A pass is weak evidence.** It does not show that the rule holds on new data. On a pass: gap 181 stays open, and gap 190 (P14-60, ship the gate) does **not** start on this pass alone.

## 2. Objects (fixed)

| Object | Value |
|---|---|
| Built-in guard | `load("willett-hw").guard()`, **`tcfg-39aac48688b8bd12`** (manifest, checked 2026-11-22), offer gate `coherence >= 0.004183090472992479` |
| LM guard | `load("willett-hw").guard(readout="lm")`, **`tcfg-f498c0637536daec`** (P14-59: `lo_new` 0.566 shipped, coherence refit; `dedf60c`, `75404c0`), offer gate `coherence >= 0.003485725778021531` |
| Feature | `lm_beam_direction` (P5-36b, unchanged): `D(x) = (S(x) - S(rev x)) / ((n(x) + n(rev x)) / 2 + 1)` on the guard's frames, with the packaged LM readout without its gate (`beam` 8, `lm_weight` 0.5, `bonus` 1.0, `prune_logp` -8.0; LM `eng_tatoeba_6gram_mkn_noE2Q_noWillett`) |
| Rule | **fixed `tau` = 0**, no fit. Gate set under test: the shipped `coherence` gate AND `lm_beam_direction >= 0` (an `OfferGate`: OFFER to WITHHOLD only; no `config_id` change) |
| Data | Willett handwriting 2021 (T5, CC0 1.0), the P15-08 **pool**: every usable sentence that is not in a test block or a val block (P14-41 `items.json` block map). **N = 781** (all of them, no sampling; audit `5d74a8e`). Log-probs made again with `m.log_probs(x, session)` (the P14-41 path) |
| `rev_out` | `lp[::-1]` of each real pool input (781 per guard) |

With `tau` 0: a real offer is removed iff `D(x) < 0`; its `rev_out` is offered iff `D(x) <= 0` (because `D(rev x) = -D(x)` and `coherence` is equal).

## 3. Rules (per guard)

| Id | Kind | Rule (pass iff) |
|---|---|---|
| **P1** | primary | `rev_out` offers with both gates **<= 39 / 781** (`floor(0.05 x 781)` = 39) |
| **P2** | primary | real pool offers removed by the direction gate **<= 39 / 781** (reference: coherence gate only) |
| S0 | secondary | `rev_out` emits (offer or commit) with both gates <= 39 / 781 |
| S1 | secondary | null inputs, 781 each, made from each pool sentence: time-shuffled raw input (d = 0), zero raw input, raw input reversed before the decoder (`rev_in`), frame-shuffled log-probs, near-uniform log-probs (P14-41 recipes; seeds `sha256("p5-37|<session>|<trial>|<kind>")`). For each set: emits with both gates <= 39 / 781, emits with both gates <= emits with the coherence gate only, and the P5-31 `offer_control` rule (rate 0.05) against the real pool offers with both gates. CP95 upper bounds are reported |

Checks (must hold, else the result is not valid): **C0** the decoder path gives the stored P14-41 val log-probs again (5 val sentences, max abs difference <= 1e-4); **C1** `|D(real) + D(rev_out)| <= 1e-9` and `coherence` equal (1e-9) on 781 / 781, per guard; **C2** the guard with both gates gives the same action as "coherence action, then withhold if `D < 0`" on the 1,562 real and `rev_out` inputs, per guard. For the null inputs the both-gate decision runs only for a coherence-only OFFER (an offer gate cannot change any other action); C2 tests that property on the real and `rev_out` inputs.

**Verdict:** a guard passes iff P1 and P2 pass and C0-C2 hold. Gap 189's done-when (as amended by option A) is met, as weak evidence, iff **both** guards pass. S0 and S1 are secondary: a fail is reported and gives a new gap, but it does not change the primary verdict.

## 4. Reported (descriptive only, no rule)

- `D` of the real pool offers (min / 5 % / median / 95 % / max); real offers with `D < 0` and `D = 0`; real and `rev_out` commits.
- **The P5-36b fitted-tau rule on the pool:** the P5-36b val-S thresholds (`results/fit.json` of P5-36b: built-in 0.3259, LM 0.1344) applied to the same records: real offers removed and `rev_out` offers. The LM value was fitted with the earlier LM guard (`tcfg-26ae951a20a0cddd`). Descriptive only.
- Bias check: greedy CER of the pool (the P14-33 references: val 0.2603, test 0.3051).
- Cost: two beam searches per decision against the coherence-only decision (median ratio).

## 5. Compute

CPU only (`HIP_VISIBLE_DEVICES`, `CUDA_VISIBLE_DEVICES` = -1); a GPU job (P15-43) runs at the same time and the GPU is not touched. `python -m fidetype.utils.isolation run --class background --threads 1`, detached by `launch.py`, keep-awake; working-set limit 2,500 MB (smoke peak 393 MB). Log, `DONE` / `FAILED` / `STOP` and per-item JSONL (restart skips finished items) in `C:\Users\zhang\bci-data\derived\p5-37\`. Order: pass 1 = real and `rev_out` of all 781 sentences (the primary rules); pass 2 = the nulls. Estimate from the smoke test: pass 1 about 1-1.5 h, pass 2 about 3-4 h (near-uniform frames are slow for the built-in guard). **Cap: 8 h.** If pass 2 is not done at the cap, the run stops and the finished null sets are reported; the primary verdict needs pass 1 only. No input set is reduced after the start.

Outputs in git: `results/results.json` (counts, thresholds, summary values only) and `results/run.log`. No log-probs, text or per-item records in git.

## 6. Not in this plan

Shipping the gate (gap 190); any refit of `tau`; other beam settings or LMs; a held-out retrain (option B).
