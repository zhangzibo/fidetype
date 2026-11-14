---
title: "M2-18: empty commits on no-signal input - mechanism, Paper 1 impact, opt-in commit gate"
type: experiment
task: M2-18
updated: 2026-11-13
---

# M2-18: empty commits on no-signal input

**Trigger.** In the M3-28 validation dry run on T12 decoder-validation blocks, the frozen Paper 1 v4 recipe (tag `paper1-v4-frozen-config`) chose `commit_max_risk` 1.0. It then committed 335 of 400 uniform (no-signal) control streams, and 320 of those were empty texts ([M3-28 results](../2026-11-13-confirmatory-t12-v2/results.md)). The M3-28 pre-registration guessed "an empty candidate gets guard risk 0". That guess was not tested. This task finds the real mechanism, checks Paper 1, and adds an opt-in fix.

## 1. Mechanism

**The guess was wrong. The guard gives an empty candidate risk 1.0, not 0.** In `HallucinationGuard.score`, an empty top-1 text sets the low-evidence term to 1.0 (`guard.py`, "An empty output has no evidence for any text"). With `combine="max"` the risk is then 1.0, the highest value.

The failure is in the policy rule, not in the guard:

1. COMMIT needs `p_top1 >= commit_p` **and** `guard_risk <= commit_max_risk` (`policy.py`, rule 2).
2. The default grid has `commit_max_risk` in (0.1, 0.2, 0.3, 0.5, **1.0**). The guard risk is clipped to [0, 1]. So at 1.0 the guard test is always true: **the value 1.0 turns the guard limit off.**
3. `abstain_risk` 1.01 (also chosen) never abstains.
4. On a near-uniform stream the T12 word decoder returns the empty text as top-1 (320 of 400 streams). In 242 of these the n-best list has only one candidate, so the calibrated `p_top1` is 1.0 (median 1.0, minimum 0.39). The commit threshold was 0.3.
5. So the empty text passes every test and is committed.

Trace of the 335 uniform commits in the dry run (refit in memory, same config id `tcfg-845934f0792ad9fc` as M3-28; [`results/t12-dryrun.json`](results/t12-dryrun.json)):

| item | value |
|---|---|
| uniform streams with an empty top-1 | 320 / 400 |
| guard risk of every empty top-1 | 1.0 (320 / 320) |
| uniform commits / of which empty / one-word | 335 / 320 / 12 |
| guard risk of the 15 non-empty uniform commits | 1.0 (all) |
| commits kept if `commit_max_risk` were 0.99, 0.5, 0.3, 0.2 or 0.1 | 0 |
| commits abstained if `abstain_risk` were 0.8 or 0.6 | 335 |

**Why the trust-pool run did not commit them.** We rebuilt the trust-pool uniform controls with the same draw as M3-28 and ran them through the frozen trust-pool configuration (`tcfg-9fb4c81c5931e00c`; diagnosis only, the confirmatory result does not change; [`results/t12-pool-uniform.json`](results/t12-pool-uniform.json)). The decoder behaved the same: 304 of 400 empty top-1 texts, all with guard risk 1.0 and median `p_top1` 1.0. The only difference was the fitted grid value `commit_max_risk` 0.1: risk 1.0 > 0.1, so the guard test failed and the policy fell through to OFFER (301 "conformal set of 1", 99 "final attempt: offer top-k"). **No other rule blocked them.** With the same inputs and `commit_max_risk` set to 1.0, the trust-pool configuration commits 321 of 400 uniform streams (304 empty).

**Minimal reproducer (synthetic data only).** [`repro.py`](repro.py) uses a toy word decoder (CTC greedy, then drop words that are not in the lexicon). On uniform streams it returns one empty candidate. Output ([`results/repro.txt`](results/repro.txt)): with `commit_max_risk` 1.0 the v4-style policy commits 60 of 60 uniform streams, 55 of them empty; with 0.5 or 0.1, or with `abstain_risk` 0.8, it commits none. Tests: `tests/test_trust_commit_gate.py::test_empty_top1_gets_guard_risk_one_not_zero`, `::test_v4_grid_value_commits_empty_text`, `::test_reproducer_uniform_streams_commit_empty_text`.

## 2. Paper 1 (T15) impact: **no Paper 1 number changes**

We re-ran the frozen v4 configuration on Brain-to-Text '25 (T15), both fixed splits of Tab. 1 and both decoders, plus the full-fit plug-in rows, with the same code path as `clean-drift/run.py` and `v4-derived/guard_controls.py` ([`t15_eval.py`](t15_eval.py), [`results/t15.md`](results/t15.md), [`results/t15.json`](results/t15.json)). The refits reproduce Paper 1 exactly.

| fit | fitted `commit_max_risk` | test wrong-commit (Paper 1) | test commits | empty | one word | <= 3 chars | uniform / frame-shuffled / other-trial commits |
|---|---|---|---|---|---|---|---|
| ours, split A | 0.1 | 0.0245 (0.0245) | 82 | 0 | 0 | 0 | 0 / 0 / 29 |
| ours, split B | 0.3 | 0.0515 (0.0515) | 157 | 0 | 0 | 0 | 0 / 0 / 58 |
| published, split A | 0.5 | 0.0294 (0.0294) | 329 | 0 | 0 | 0 | 0 / 0 / 0 |
| published, split B | 0.5 | 0.0306 (0.0306) | 339 | 0 | 0 | 0 | 0 / 0 / 0 |
| ours, full fit | 0.5 | 0.0588 (0.059) | 189 | 0 | 0 | 0 | 0 / 0 / 65 |
| published, full fit | 0.5 | 0.0441 (0.044) | 386 | 0 | 0 | 0 | 0 / 0 / 0 |

- Every fixed-split and full-fit Paper 1 fit chose `commit_max_risk` <= 0.5. So an empty text (risk 1.0) could never be committed there.
- **Repeated splits (Tab. 2).** The fitted grid value was 1.0 in 53 of 200 splits on our decoder and 65 of 200 on the published gate (split tables in the Paper 1 cache). In those splits the guard limit was off. But no real T15 trial has an empty top-1: we scanned all 22 per-temperature decode caches of the Paper 1 analyses (35,816 n-best lists, every temperature that a split used): **0 empty top-1 texts**, 44 one-word top-1 texts ([`scan_caches.py`](scan_caches.py), [`results/cache-scan.json`](results/cache-scan.json)). So no repeated-split number on real trials contains an empty commit. sEMG decode caches: 0 empty top-1 in 53,808 lists (sEMG fits also chose 1.0 often: 49/50 calib, 33/50 cross-session).
- The control-stream claims of Paper 1 (0/300 uniform and frame-shuffled, Sec. 7.6 and Tab. S-controls) come from fits with `commit_max_risk` 0.1 and 0.5. They stay true as reported.

**Erratum candidate (wording only, no number).** Paper 1 says "The guard stopped this" and "our guard is one such check" (Discussion; Results Sec. 7.6). These statements hold for the reported fits. They do not hold for every fit of the frozen recipe: when the grid fit picks `commit_max_risk` 1.0 (one of five grid values; 53/200 and 65/200 T15 re-splits; the T12 dry run), the guard limit is off, and the frozen v4 configuration can commit empty or full-risk texts on no-signal input. Suggested sentence: "The guard limit is part of the fitted policy; when the fit selects `commit_max_risk = 1.0`, the guard does not block any commit. A deployed configuration should forbid empty commits and commits at guard risk 1.0 (repository task M2-18)." We did not edit the paper.

## 3. Fix: opt-in commit gate

New module `src/fidetype/trust/content.py`:

- `CommitGate(min_chars=1, min_words=0, max_guard_risk=None)`: a COMMIT needs at least `min_chars` non-white-space characters, at least `min_words` words and, if `max_guard_risk` is set, `guard_risk < max_guard_risk` (strict).
- `gate_decision(...)`: a COMMIT that fails the gate becomes the decision of the same policy with `commit_p = +inf` (OFFER / OFFER_WORDS / ASK / ABSTAIN by the normal rules). Reason prefix `"commit gate: "`.
- `GatedPolicy`: a `DecisionPolicy` subclass that applies the gate.
- `FrozenTrustConfig.commit_gate` (new field, dict; **empty = off**). An empty field is left out of the JSON file and of `config_id`, so every existing configuration keeps its bytes, its id and its decisions (test: the M3-28 configs keep `tcfg-9fb4c81c5931e00c` and `tcfg-845934f0792ad9fc`). `with_commit_gate(min_chars, min_words, max_guard_risk)` returns a copy with a new id; `build()` returns a `GatedPolicy`; `from_pipeline` records the gate of a gated pipeline.
- `StreamingTrustLayer` applies the gate of its configuration last, on every decision path (plain, online controller, session-risk).
- **The risk bound stays valid.** The gate only removes commits, and for each item the fallback loss is at most the commit loss. So a CRC / LTT bound for the ungated policy also holds for the gated one, without a new calibration (test `test_gate_never_increases_the_item_loss`).
- Known limit: on the online path the controller's ticket still counts a gated COMMIT as a commit (its loss is then over-counted, which is conservative).

Paper 1 code and the frozen configuration are unchanged: `policy.py`, `guard.py`, `risk_control.py`, `harness.py` are byte-identical to the tag; `PAPER1_V4_RECIPE` is unchanged.

**Spec.** FEP-0001 section 3 gets rule 9: a trust layer SHOULD NOT emit a final `COMMIT` with an empty committed text; it uses `ABSTAIN` to show no text; a bridge SHOULD NOT forward an empty committed text. It is a SHOULD, not a MUST, because v4 configurations can still emit one. Open question 6 asks whether it becomes a MUST with a reject vector when a v5 reference configuration has the gate on by default. The conformance profile is unchanged.

Tests: `tests/test_trust_commit_gate.py` (12).

## 4. Before / after

Three gate variants: **A** = no empty text (`CommitGate()`); **B** = A + guard risk < 1 (`CommitGate(1, 0, 1.0)`, recommended); **C** = at least 2 words.

**T12 v2 validation dry run** (commits / wrong commits; n = 400 per set):

| set | v4 | gate A | gate B | gate C |
|---|---|---|---|---|
| "test" (decoder-validation test sessions) | 22 / 11 (0.0275) | 22 / 11 | 22 / 11 | 22 / 11 |
| uniform control | **335 / 335** (320 empty) | 15 / 15 | **0 / 0** | 3 / 3 |
| frame-shuffled control | 6 / 6 (1 empty) | 5 / 5 | 3 / 3 | 5 / 5 |
| intent mismatch | 22 / 22 | 22 / 22 | 22 / 22 | 22 / 22 |
| calibration half (LTT input) | 11 / 7 | 11 / 7 | 11 / 7 | 11 / 7 |

- Gate A alone removes the 320 empty commits but leaves 15 uniform commits (3.75 %, above the 1 % C3 limit). These are one- or two-word texts with guard risk 1.0.
- Gate B removes all uniform commits and 3 of 6 frame-shuffled commits (3/400 = 0.75 %, below 1 %). With gate B the dry run would pass C3. The test rows, eWPM (7.09) and the calibration half do not change.
- Gated config id of the dry-run config with gate B: `tcfg-b13fe05849072188`.

**T15 (Paper 1 fits):** all six fits, all sets, all three gates: **identical** to v4 (commits, wrong commits, eWPM; 0 differences). Gate B can change T15 numbers only in fits that choose `commit_max_risk` 1.0 (Tab. 2 re-splits); we did not run those, because the gate is not part of Paper 1.

## 5. Stability finding and a v5 suggestion (not applied)

One discrete grid value decides the behaviour on no-signal input. On 240-trial T12 fit sets the recipe chose `commit_max_risk` 1.0 on the validation blocks ("commits on no-signal input": 335/400 uniform) and 0.1 on the trust pool ("commits almost nothing": 1/400 test, 0/400 controls). On T15 re-splits, 1.0 was chosen in 27 % (ours) and 33 % (published) of splits. The grid fit maximises eWPM under a plug-in wrong-commit limit on real trials only, so it cannot see the no-signal case.

Suggested v5 recipe changes (for a future configuration; **not applied**):
1. Commit gate B on by default (`min_chars` 1, `max_guard_risk` 1.0). Equivalent for the guard part: replace 1.0 in the `commit_max_risk` grid by a value below 1 (for example 0.8).
2. A control-aware grid fit: build uniform and frame-shuffled versions of the fit-A streams, and make a grid point feasible only if it commits at most 1 % of them. This needs no labels.
3. Report the selection stability: refit on bootstrap resamples of fit-A and report how often each grid value wins. Prefer the more conservative value when eWPM differs by less than a small margin.
4. Keep `PAPER1_V4_RECIPE` and the tag unchanged; v5 is a new recipe record with a new name.

## Files and reruns

- [`repro.py`](repro.py): synthetic reproducer (seconds).
- [`t12_dryrun.py`](t12_dryrun.py) `--stage dryrun` (about 3 min) and `--stage pool` (about 1 min): reads the M3-28 derived files outside the repo (`C:\Users\zhang\bci-data\derived\2026-11-13-confirmatory-t12-v2\`). Writes `results/t12-dryrun.json`, `results/t12-pool-uniform.json`, `results/t12.log` (the log has two dry-run passes: first with gate variants A and C only, then with A, B, C).
- [`t15_eval.py`](t15_eval.py) (about 5 min with warm caches): reads the Paper 1 decode caches; new decodes go to `C:\Users\zhang\bci-data\cache\m2-18\`. Writes `results/t15.json`, `results/t15.md`, `results/t15.log`.
- [`scan_caches.py`](scan_caches.py): counts empty / short top-1 texts in the Paper 1 per-temperature caches.
- All result files hold counts and settings only: no text, no signals.

Run each from the repo root with `.venv\Scripts\python.exe -I <script>`.
