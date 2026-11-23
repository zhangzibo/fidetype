# Trust guarantee sheet: what the drop-in guard promises

`fidetype.trust.calibrate` (see the [10-minute quickstart](trust-quickstart.md)) returns a guard and a **guarantee sheet** (`print(guard.sheet)`). This page explains each line of the sheet: what is guaranteed, under which assumptions, what is **not** guaranteed, and how to read the audit log.

Fidetype is research software, not a medical device. Nothing on this page is a medical or legal claim.

## 1. The guarantee in one sentence

> With probability at least 1 − δ over the draw of the calibration data, the **wrong-commit rate** of the guard on new utterances from the same distribution is at most α.

| Term | Meaning |
|---|---|
| Utterance | One decoder output (one `(T, V)` matrix or one n-best list) and one decision |
| Wrong commit | The guard says `commit` and the committed text is not exactly the true text (after the space normalisation below) |
| Wrong-commit rate | Wrong commits / **all** utterances (not / commits) |
| α (`alpha`) | The largest wrong-commit rate that you accept. Default 0.05 |
| δ (`delta`) | The probability that the calibration draw was unlucky and the bound does not hold. Default 0.1 |

Example: α = 0.05, δ = 0.1. Over many utterances, at most 5 % of all utterances become wrong commits. This is true for at least 90 % of the calibration sets that you could have drawn.

## 2. How the guard gets the guarantee

The wrapper adds no new statistics. It runs the existing Fidetype recipe ([learn then test](../wiki/concepts/learn-then-test.md), [trust decision](../wiki/concepts/trust-decision.md)):

| Step | Data | What it fits |
|---|---|---|
| 1. Random split (seed on the sheet) | all labelled utterances | three disjoint parts |
| 2. Fit part (25 %) | `n_fit` | frame temperature (logits only), sentence temperature, conformal threshold |
| 3. Policy part (37.5 %) | `n_policy` | the policy grid (guard limits, offer size), chosen for typing speed with a plug-in wrong-commit limit α |
| 4. LTT part (37.5 %) | `n_ltt` | the commit threshold λ̂ on `p_top1`: **Learn then Test**, exact binomial p-values, grid 1.00 → 0.00 in steps of 0.01, fixed-sequence testing at level δ |
| 5. Combine | — | final threshold = max(policy-grid threshold, λ̂). A higher threshold only removes commits, so the bound still holds |
| 6. Commit gate | — | always on: no empty commit, no commit at guard risk 1.0. A gate only removes commits, so the bound still holds |
| 7. Null controls | synthetic and your null inputs | refuse the guard if it commits on null input (section 5) |

The LTT part is used for nothing else. So its utterances are exchangeable with new utterances, if your data meet the assumptions below.

## 3. Assumptions (the guarantee holds only if all are true)

| # | Assumption | How it can break |
|---|---|---|
| A1 | **Exchangeable data.** Calibration and live utterances come from the same distribution: same user, device, electrode or sensor position, decoder, task and session type | A new day, a new user, a new sensor position, fatigue, drift, a different task (free text vs. copy typing) |
| A2 | The decoder, its weights, its vocabulary and its decode settings (`decode_fn`, `lexicon`) do not change after calibration | You retrain or update the decoder or the language model |
| A3 | The true texts are right and use the same normalisation as the decoder output. The wrapper joins runs of spaces and strips the ends; nothing else (no case folding, no punctuation removal) | Labels with typos; labels in upper case while the decoder writes lower case |
| A4 | Each utterance is decided once. The calibration utterances were not used to tune anything else (not the decoder, not the lexicon) | Repeated tries of the same utterance; a lexicon or LM built from the calibration texts |
| A5 | The labelled utterances are a random sample of the use, not a hand-picked set | Only the "good" trials kept for calibration |

If an assumption is false, the numbers on the sheet can be wrong in either direction. Re-calibrate when the use changes. For drift during a session, Fidetype has online re-calibration and a per-session monitor ([adaptive conformal inference](../wiki/concepts/adaptive-conformal-inference.md)); the drop-in wrapper does not use them yet.

## 4. What is NOT guaranteed

| Not guaranteed | Why |
|---|---|
| Any single utterance | The bound is on a rate over many utterances |
| A bound per user, per session or per sentence type | The bound is on the mix of the calibration data. One user in a mix can be worse |
| Data that differ from the calibration data | See A1 |
| The error rate among commits (precision) | The rate is wrong commits / all utterances. With few commits, many of them can be wrong (M2-19: 6 of 9 commits wrong at a rate of 0.0086). An optional bound exists: section 10 |
| A minimum number of commits or a typing speed | The guard may commit rarely or never. It trades commits for safety |
| Offered and withheld text | Only commits count. An offer can hold no right choice |
| Hallucination on inputs that the null controls do not cover | The controls test two kinds of null input (section 5), not every failure |
| A medical or legal claim | Research software |

## 5. Null controls (refusal rule)

Every calibration runs two null controls. This follows the project rule of 2026-11-15: every trust-config re-tune keeps the commit gate on and passes a uniform and a shuffled control ([streaming trust layer](../wiki/concepts/streaming-trust-layer.md)). The rule came from M2-19, where a re-tuned config committed 186 of 300 no-signal streams.

| Control | Logits input | n-best input |
|---|---|---|
| uniform | Near-uniform frames (log 1/V + 0.05·N(0, 1)) with the lengths of calibration utterances | Calibration n-best lists with equal scores and no character confidences |
| shuffled | Calibration frames in a random time order | **Your** decoder's n-best on null input (`null_inputs`), because Fidetype does not run your decoder |
| user (optional, logits) | Your decoder's output on null input (`null_inputs`) | — |

**Pass rule.** A control with n inputs passes if the guard commits on at most floor(r · n) of them. r is `null_max_commit_rate` (default α), because every commit on null input is a wrong commit. The target is 0. If any control fails, `calibrate` raises `NullControlError` (with the counts in `.report`) and returns no guard.

**Known limits of the controls.**

- A decoder with no language model and no lexicon usually fails the shuffled control: shuffled frames keep their confidence, so the decoder writes confident nonsense. Use `lexicon=` or your own `decode_fn` with a language model.
- For very short utterances (one or two letters), a shuffle can give a real word ("no" → "on"). Then a commit on the shuffled control is not always a hallucination.
- The controls are a sanity check, not a proof. They do not test drift, a new user or other failures.

### 5a. Offer null control (P5-31)

The commit controls count only COMMITs. A guard can also OFFER a list of choices. An offer list that the guard shows as often on null input as on real input does not depend on the signal. P14-41 found this case: the offer-only `willett-hw` guard offers on 77 of 80 frame-shuffled test inputs, and on 77 of 80 real test inputs.

The offer null control counts the OFFERs on the same control inputs (no extra decoding). It compares each control with the **real offer rate**: the OFFERs of the final guard on the LTT items.

**Pass rule (pre-stated).** A control with n inputs and k offers passes if both are true:

1. k / n ≤ 0.5 × (real offer rate) (`OFFER_NULL_MAX_RATIO`). This asks for a clear drop, not only a significant one.
2. k ≤ floor(r · n) (the commit allowance), **or** a one-sided Fisher exact test of "null offer rate < real offer rate" gives p ≤ 0.05 (`OFFER_NULL_P`). This asks for evidence when the null offers are more than a few.

A guard that never offers passes (0 ≤ 0). A guard that offers on null input but never on real input fails.

**Mode: a warning first (`calibrate(offer_control=...)`).**

| Mode | What happens on a failure |
|---|---|
| `"warn"` (default) | The result is in `sheet.offers`. The sheet gets a warning that starts with `offer null control (P5-31) FAILED`. The guard, its `config_id`, `feasible`, the commit threshold and the commit controls do not change |
| `"refuse"` | `calibrate` raises `NullControlError` and returns no guard |
| `"off"` | The control does not run. The sheet has the bytes of a guard before P5-31 |

Why a warning first:

- The commit guarantee (section 1) does not use the offer list. An offer failure does not make the bound false.
- Many existing guards fail this rule by design: the policy offers when it is not sure, and null input is the least sure input. For example, the n-best test guard of `tests/test_trust_offer_control.py` offers on 60 of 60 equal-score lists and on 33 of 112 real LTT items. A refusal would turn these calibrations into errors without notice.
- The rule (0.5, 0.05) is new. It is validated on few guards. A refusal rule must not change the status of packaged guards in silence.

What a failure means for you: do not show the offer list as a suggestion of the user's intent. Show it as "no reliable reading", or withhold it. Use `offer_control="refuse"` if your product shows offers as suggestions.

**Decision (user, 2026-11-22, gap 152):** the default stays `"warn"`. The `"refuse"` rule applies only to guards that ship an offer gate (section 5b): a packaged manifest whose trust block has an `offer_gate` must carry an `offer_control` block with verdict `"pass"`, or the manifest parser refuses it. Today this holds for `t15-m4-13` and both `willett-hw` guards. `kt-semg-lda` has no offer gate and keeps its failing block in `"warn"` mode (gap 155).

**Check a saved guard.** `fidetype.trust.recheck_offer_control(guard, inputs, null_inputs=...)` runs the control on a saved guard without a new calibration. Give it the calibration inputs in the same order (and the same `null_inputs`). It makes the same split and the same control inputs from `sheet.seed`, so the commit counts must equal the sheet (`commits_match_sheet: True`).

### 5b. Offer gate (P5-33)

An offer gate makes a guard WITHHOLD an offer when the input shows no evidence of signal.

```python
from fidetype.trust import OfferGate
guard.set_offer_gate(OfferGate("coherence", 0.187))   # or ft.load(path, offer_gate=...)
```

- It acts **only on OFFER decisions**. A COMMIT and a WITHHOLD never change. So the commit bound, the commit threshold, the commit null controls and `config_id` stay the same.
- It reads one feature of the decision (`fidetype.trust.offer_gate`). An example is `coherence`: the mean dot product of adjacent frame probabilities, minus the mean over all frame pairs. Its expected value is 0 when the frame order is random, and also on flat input. Per-frame statistics (`peak`, `neg_entropy`) cannot see a frame-shuffled input.
- `OfferGate.fit(feature, values, keep=0.95)` sets the threshold from the feature values of the real calibration OFFERs. Fit it on items that the offer null control does not use as real items.
- A guard file stores the gate under `offer_gate`, but only when a gate is set. Old files keep their bytes. `ft.load(path, offer_gate=False)` switches a stored gate off.
- `recheck_offer_control` sees the gate.

Packaged guards: `t15-m4-13` has the gate `coherence >= 0.187` in its manifest (`trust.offer_gate`). It is on by default, and `model.guard(offer_gate=False)` switches it off. With the gate, the guard passes the offer null control (uniform 0 / 300, frame-shuffled 0 / 300, real 212 / 271). The 54 LTT commits do not change. Results: [P5-33](../experiments/2026-11-21-p5-33-withhold/results.md).

Both `willett-hw` guards have the gate too (P14-54): `coherence >= 0.00418` in `trust.offer_gate` (built-in readout) and `coherence >= 0.00282` in `readouts.lm.trust.offer_gate` (LM readout). With the gate, both pass the offer null control (uniform, frame-shuffled and time-shuffled input 0 offers each; real 40 / 40); without it, they offered on 297 / 300 and 289 / 300 frame-shuffled inputs. The thresholds differ because the built-in guard applies its frame temperature (1.49) before the feature is computed. Results: [P14-54](../experiments/2026-11-21-p14-54-willett-order-gate/results.md).

## 6. Reading the sheet

| Line | Meaning | Look for |
|---|---|---|
| `config_id` | Content id (`tcfg-` + 16 hex) of the frozen configuration. The audit log cites it | The same id in your audit log and in your report |
| `input` | Input kind and decoder (`builtin:...`, `builtin:...+lexicon(N words)` or `custom:<function>`) | The decoder that you use live |
| `guarantee` | P(wrong-commit rate ≤ α) ≥ 1 − δ | The α and δ that you claim |
| `calibration items` | n = fit + policy grid + LTT | — |
| `LTT items needed` | Smallest LTT part (labelled utterances, not commits) that can certify any commit with 0 errors: n ≥ log δ / log(1 − α) (45 for α 0.05, δ 0.1) | `n_ltt` at or above this number |
| `lambda_hat` / `feasible` | The LTT threshold. `feasible: False` means no threshold passed: the guard never commits | `feasible: True` |
| `commit threshold` | The final `p_top1` threshold (max of grid and λ̂), or `never commits` | A number |
| `commit gate` | The gate settings | `min_chars 1`, `max_guard_risk 1.0` |
| `LTT items (in-sample)` | Commits and wrong commits of the final guard on the LTT part, the commits that the commit gate blocked (guard risk 1.00), and the median guard risk. In-sample: a sanity check, **not** a test | Wrong commits / `n_ltt` near or below α; more commits than gate blocks (else the guard will rarely commit) |
| `null controls` | Commits / n per control and the allowed number | All `PASS` (else there is no sheet) |
| `offer null control` | Offers / n on the real LTT items and on each control, with the Fisher p-value (section 5a) | All `PASS`; on `FAIL`, do not show offers as suggestions |
| `assumptions`, `not guaranteed` | Sections 3 and 4 of this page | — |
| `warnings` | For example "only 30 LTT items", "never commits", "the commit gate blocked N in-sample commits", "only N of M LTT items commit in-sample", "frame temperature not fitted" | No warnings, or warnings that you understand |

**Check it yourself.** Keep a labelled test set that the calibration never saw. Count wrong commits / all test utterances. One test set cannot prove a 1 − δ statement, but a rate far above α means that an assumption is false.

## 7. Reading the audit log

`guard.write_audit("audit.jsonl")` writes JSON Lines (UTF-8, one object per line):

1. **First line** `{"type": "audit_header", ...}`: `schema` (`fidetype.trust-audit/0.1`), `fidetype_version`, `config_id`, `input_kind` and the full `guarantee` sheet.
2. **One line per decision** `{"type": "trust_decision", ...}` (the NTS `trust_decision` event of FEP-0001, plus audit fields):

| Field | Meaning |
|---|---|
| `seq` | Decision number in this guard (0, 1, 2, ...) |
| `time_utc` | Wall-clock time of the decision (ISO 8601, UTC) |
| `utterance_id` | Your reference, if you gave one to `decide` |
| `user_action` | `commit`, `offer` or `withhold` |
| `action` | The trust-layer action: `COMMIT`, `OFFER`, `OFFER_WORDS`, `ASK` or `ABSTAIN` |
| `reason` | Why (for example `commit gate: empty text; ...`, `no candidate`) |
| `shown` | The committed text or the offered choices. Left out with `audit_text=False` |
| `p_top1` | Calibrated probability that the top text is right (`score_semantics: calibrated_prob`) |
| `guard_risk` | Hallucination-guard risk of the top text, in [0, 1] |
| `set_size` | Size of the conformal set |
| `config_id` | The configuration that made the decision; must match the header |
| `input_sha256` | SHA-256 of the NTS events of the input: proves which input gave the decision, without the input |
| `input` | Input reference; for logits also `stream_sha256` (fingerprint of the stream) and the frame range |
| `latency_s` | Decision time in seconds |

How to audit: (1) all records carry the header's `config_id`; (2) count `user_action == "commit"` and, with ground truth, the wrong ones; (3) compare that rate with α on the sheet; (4) to prove an input, recompute `input_sha256` from `guard.nts_events(x)`.

**Privacy.** With `audit_text=True` (the default), `shown` holds decoded text: personal data. Store the log like other user data, or use `audit_text=False`. The log holds no signal. `guard.save()` writes no signal and no text.

## 8. Validated on

Held-out check of the drop-in API, used as an outside user would use it (public API only, recorded decoder output, our word decoder as `decode_fn`, `stream_texts` = phoneme strings), alpha 0.05, delta 0.1, all other defaults ([experiment](../experiments/2026-11-16-p14-03-replay-validation/results.md)):

| Set (licence) | Split | Null controls | Held-out commits | Wrong-commit rate [CP95] |
|---|---|---|---|---|
| T15, Brain-to-Text '25 (CC0) | by trial: 722 calibration, 701 held out | uniform 0/300, shuffled 1/300: PASS | 2 / 701 (2 wrong) | 0.0029 [0.0003, 0.0103] |
| T12, Brain-to-Text '24 (CC0) | by session: 14 sessions (480) calibration, 10 later sessions (400) held out | uniform 0/300, shuffled 0/300: PASS | 25 / 400 (15 wrong) | 0.0375 [0.0211, 0.0611] |

Both rates are below alpha. On T12 (later sessions, so with drift) the CP95 upper bound is above alpha: one draw does not prove the bound, and most commits are wrong (the bound is not on precision, section 4). Both sets are intracortical speech with our own decoders; other modalities are not yet validated.

## 9. Optional: a bound on fluent-wrong commits (P15-06)

If a language model (LLM) helps your decoder, the guard can also bound the rate of **fluent-wrong** commits: committed text that is wrong but reads well. It is off by default; without these arguments nothing changes.

```python
from fidetype.trust.halluc_bound import CommitGrounding
from fidetype.trust.grounding import lexicon_label_fn

grounding = CommitGrounding(lexicon_label_fn(prons, symbol_ids), word_sep_id=symbol_ids[" "])
guard = ft.calibrate(cal_logits, cal_texts, vocab=VOCAB, decode_fn=my_decoder,
                     grounding=grounding, llm=my_llm_scorer, halluc_alpha=0.01)
```

| Item | Meaning |
|---|---|
| Fluent-wrong commit | A commit whose text is not the true text **and** whose LLM log-probability per word is at or above `fluent_threshold` (default: the median of the true texts of the fit part). Without `llm=`, every wrong commit counts |
| Guarantee | With probability at least 1 − `halluc_delta` (default δ): fluent-wrong rate ≤ `halluc_alpha` **and** wrong-commit rate ≤ α (rates over all utterances) |
| Grounding gate | A commit passes only if its text is supported by the frames: sentence deficit ≤ `tau_commit` (CTC score against `anchor_fn`, or the best path) and largest word deficit ≤ `tau_word` (forced alignment). A blocked commit becomes an offer or a withhold. Offers do not change |
| How | Learn then Test over the joint grid (`commit_p`, `tau_commit`, `tau_word`): test order from the policy part, fixed-sequence test on the LTT part, p-value = max of the two exact binomial p-values. The chosen `commit_p` is never below the plain one, so section 1 and the null controls still hold |
| Sheet | A "hallucination bound" block: α_h, δ_h, the loss, the selected point, how many grid points were tested and certified |
| Cost | The bound can remove most commits. To certify α_h = 0.01 with zero errors, the LTT part needs about 230 utterances or more (the guard otherwise never commits) |

Not guaranteed: wrong commits that the LLM finds non-fluent (they count only in section 1); that each committed word was said. `ft.load` needs the same `grounding=` again. Validated on T15 (one set): the bound held in all arms, but with the strict selection rule the LLM-rescoring guard did not commit at all ([experiment](../experiments/2026-11-16-p15-06-halluc-bound/results.md)).

## 10. Optional: a bound on the error rate among commits (P5-02)

Section 1 bounds wrong commits / **all** utterances. A guard that commits rarely meets it even if most of its commits are wrong (P14-03: T15 2 of 2 commits wrong, T12 15 of 25). The precision bound answers the user's question: "when it types, is it right?". It is off by default; without these arguments nothing changes.

```python
guard = ft.calibrate(cal_logits, cal_texts, vocab=VOCAB, decode_fn=my_decoder,
                     target_precision=0.95)          # precision_delta defaults to delta
print(guard.sheet)                                   # adds a "precision bound" block
```

| Item | Meaning |
|---|---|
| Error rate among commits | Wrong COMMITs / all COMMITs. Precision = 1 − this rate |
| Guarantee | With probability at least 1 − `precision_delta` (default δ), the error rate among commits on new utterances is at most 1 − `target_precision` |
| Together with section 1 | Both statements hold together with probability at least 1 − δ − `precision_delta` (union bound) |
| Together with section 9 | Allowed since the P5-02 completion. With `grounding=` / `llm=` **and** `target_precision=`, the precision risk is a **third risk of the same joint test** (no second test on the same LTT part): p-value = max(p_wc, p_h, p_precision) for each grid point (`commit_p`, `tau_commit`, `tau_word`), test order from the policy part, fixed-sequence test on the LTT part at level δ_j = min(`halluc_delta`, `precision_delta`). Then wrong-commit ≤ α, fluent-wrong ≤ α_h and error among commits ≤ 1 − `target_precision` hold **together** with probability at least 1 − δ_j. The sheet shows both blocks; the precision block has `joint_with: halluc` |
| How | For each threshold `commit_p` (grid 1.00 → 0.00, step 0.01, or `precision_grid`): exact binomial p-value P(Bin(commits, β) ≤ wrong) on the commits of the LTT part, β = 1 − `target_precision`. Given the number of commits, the commits are an exchangeable sample, so the p-value is valid. p ≤ δ is the same test as "one-sided Clopper-Pearson upper bound ≤ β". The error rate is not monotone in `commit_p`, so the test order comes from the policy part (smallest p-value first), and a fixed-sequence test on the LTT part certifies the thresholds ([learn then test](../wiki/concepts/learn-then-test.md)) |
| Selection | The certified threshold with the most commits, but never below the plain `commit_p`. A higher threshold only removes commits, so section 1 and the null controls still hold |
| No certified threshold | The guard never commits (sheet warning). It still offers and withholds |
| Cost | To certify a threshold, the LTT part needs at least log δ / log(`target_precision`) right commits: 22 for 0.9, 45 for 0.95, 230 for 0.99 (δ 0.1). A decoder that is rarely right cannot get a useful precision guarantee |
| Sheet | A "precision bound" block: target, δ_p, the selected threshold, the P14-03 threshold, how many thresholds were tested and certified, the test commits and a one-sided CP lower bound on precision |

Not guaranteed: precision for one session or one user; any single commit; data that differ from the calibration data (section 3). The joint test with section 9 needs more data: each certified grid point must pass all three tests on the same LTT part. `ft.load` needs nothing extra (with section 9: the same `grounding=`). Code: [`src/fidetype/trust/precision_bound.py`](../src/fidetype/trust/precision_bound.py). Validated on synthetic exchangeable data (the test suite: violation rate at most δ over 200 draws). On the P14-03 replay sets (T15, T12; targets 0.5 to 0.95) no threshold was certified: the decoders are right on only about 8 % of sentences, so the guard never commits (P14-03 guard: 2 of 2 and 15 of 25 commits wrong). Safe, but not yet useful on these decoders ([experiment](../experiments/2026-11-16-p5-02-precision/results.md)).

## 10a. Optional: a learned commit score (P5-23)

By default the guard commits when `p_top1` (the calibrated probability of the top-1 text) is at or above the certified threshold. `p_top1` uses only the n-best scores. Other outputs of the decoder also show whether the top-1 text is right. With `confidence="learned"`, a small model combines them into one commit score. The guarantee of section 1 does not change. Off by default: without the argument nothing changes.

```python
guard = ft.calibrate(cal_logits, cal_texts, vocab=VOCAB, decode_fn=my_decoder,
                     confidence="learned")           # confidence_l2=1.0 (L2 weight)
print(guard.sheet)                                   # "commit threshold  learned commit score >= ..."
```

| Item | Meaning |
|---|---|
| Features (13, fixed) | `p_top1`, logit of `p_top1`, margin to the second candidate, n-best entropy, n-best word agreement (posterior-weighted, per word position), mean and smallest character confidence, guard risk, number of words, acoustic log-probability per character, LM log-probability per word, acoustic gap (best acoustic score in the n-best minus the top-1 one, per character), input frames per character. A missing value (for example no LM score) counts as the fit mean |
| Model | Logistic regression on standardised features, L2 weight `confidence_l2` (default 1.0), Newton steps (deterministic, numpy only). Each feature is clipped to the range of the fit items, so the score does not extrapolate (for example on null input). Each weight has a fixed allowed sign (more evidence never lowers the score); a weight with the wrong sign removes its feature (backward elimination, listed as `dropped`) |
| Three-way split | Fit part + policy-grid part of the usual split: fit the score (the temperatures and the conformal threshold are fitted first, on the fit part, as before). LTT part: certify the threshold of the score, LTT with exact binomial p-values, fixed-sequence grid 1.00 → 0.00 step 0.01. The LTT items were not used to fit the score, so the LTT bound holds as in section 2 |
| Commit rule | COMMIT the top-1 text iff the score ≥ the certified threshold **and** the commit gate passes (non-empty text, guard risk below 1.0). The threshold of the policy grid is not used (no `max` with it) |
| Null controls | Section 5, on the final guard with the learned score. A failed control refuses the calibration |
| Files | The score (weights, means, scales, ranges, threshold, the LTT record) is in the frozen configuration (`recipe.commit_score`), so `config_id` covers it. `guard.save` / `ft.load` round-trip it. The configuration has `commit_p = inf`: a trust layer that reads it without the drop-in guard never commits |
| Sheet | The `commit threshold` line names the learned score. A `commit score` block gives the model, the features used, the fit items and the certify items. The `offline_ltt` policy sheet (section 12) has `status.commit_score = "learned"` and the model |
| Results | `TrustResult.commit_score` and the audit record key `commit_score`. `p_top1` is still reported |
| Not combined (this version) | `grounding=`, `llm=`, `target_precision=` (a `ValueError`); `guard.online(...)` (a `ValueError`: the online methods move a threshold on `p_top1`) |

Not guaranteed: anything beyond section 1. A learned score can commit more often than `p_top1` (more right words), but it can also commit less. It needs enough items: it is fitted on about 62 % of the calibration items, and the LTT part is the same size as before. Code: [`src/fidetype/trust/commit_score.py`](../src/fidetype/trust/commit_score.py). Validated (pre-registered, [P5-23 results](../experiments/2026-11-18-p5-23-learned-confidence/results.md)): T15 M4-13 `val_eval` (701): safe WPM 2.64 vs 2.23 with `p_top1` (paired difference +0.42 [0.07, 0.78]), 113 commits and 10 wrong (0.0143) vs 104 and 17; T12 (400): 1.87 vs 1.27, difference not clear (interval includes 0), 15 wrong in both. Null controls 0 / 300 everywhere. One participant per set.

## 10b. Optional: certified word-prefix commits (P5-24)

`calibrate(..., confidence="learned", commit_unit="prefix")` lets the guard commit the first words of the top-1 text when the whole text is not safe to commit. The default stays `commit_unit="sentence"`.

| Step | What happens |
|---|---|
| Score | A learned prefix score (module `fidetype.trust.commit_score`, same model type as 10a) scores every word prefix k of the top-1 text: prefix posterior mass, smallest and mean n-best word agreement over the prefix, prefix character confidences, k, k / m, "complete" (k = m), and the sentence features. The score of prefix k is the smallest raw score of prefixes 1..k, so it never rises with k. |
| Fit | One row per prefix of the fit + policy-grid items. Label: the prefix is right. |
| Loss | The committed prefix is wrong: its words are not the first words of the true text. A commit of all m top-1 words (complete) is wrong unless it equals the true text. |
| Certify | LTT on the LTT items only (disjoint from the fit items): fixed sequence 1.00 -> 0.00 step 0.01, exact binomial p-values, loss as above. The loss is monotone in the threshold: a lower threshold gives a longer prefix, and a wrong prefix stays wrong when it grows. |
| Guarantee | P( wrong-prefix-commit rate <= alpha ) >= 1 - delta; rate = wrong commits (prefix or complete) / all utterances. |
| Decide | Commit the longest prefix with score >= the threshold; the commit gate (non-empty text, guard risk < 1.0 of the top-1 text) still applies. |
| Output | `TrustResult.text` is the committed prefix; `n_words_committed`, `complete`, `commit_unit`; the decision event has `commit_unit`, `n_words_committed`, `n_words_top1`, `complete`. `guard.is_right(result, truth)` applies the loss. |
| Controls | The uniform and shuffled null controls run on the final prefix guard; every prefix commit counts. |

Not in this version: `online()`, `target_precision=`, `grounding=`, `llm=`. A plain n-best prefix posterior is not offered: when all candidates share a prefix its mass is 1.0, also when the truth is not in the list, so LTT finds no feasible threshold (P14-23). Score a prefix guard with [safe WPM v0.2 (proposed)](safe-wpm-v0.2-proposal.md); v0.1 gives a right prefix 0 words.

### 10b.1 A frozen external prefix score (P5-35)

`calibrate(..., commit_unit="prefix", prefix_score=score)` certifies a prefix score that you fitted elsewhere (for example from a second decoder, a language model or a wide competitor set). `score` is a `fidetype.trust.FrozenPrefixScore(fn, name=, version=, spec=)`.

| Step | What happens |
|---|---|
| Your function | `fn(ctx)` gets a `PrefixContext`: `words` (the guard's top-1 words), `texts` and `posteriors` (the calibrated n-best), `candidates`, `log_probs` (logits input: the frame-calibrated `(T, V)` log-probabilities that the decoder saw; `None` for n-best), `p_top1`, `guard_risk`, `n_frames`, `builtin_rows` (the 10b prefix features). It returns `len(words)` scores (higher = surer, normally in [0, 1]) or `None` (no commit for this item). A wrong length or NaN raises `ValueError`. |
| Fit | None. Calibrate fits no score. |
| Certify, loss, guarantee, decide, controls | As in 10b: the library makes the scores monotone (running minimum), applies the commit gate, certifies the threshold by LTT on the LTT items only, and runs the null controls on the final guard. |
| Identity | `spec` is a JSON object that describes the score completely (weights, features, decoder identity). The digest of `name`, `version` and `spec` (`pfx-...`) is in the frozen configuration (`recipe.commit_score`, schema `fidetype.external-prefix-score/0.1`), so `config_id` changes when the score changes. A spec that is not JSON (NaN, infinity, arrays, objects) raises `TypeError`. A bare function raises `TypeError`: it has no stable identity. |
| Guard file | Keeps `name`, `version`, `spec` and the digest, not the function. `ft.load(path, prefix_score=score)` needs the same score again: no score or another digest raises `ValueError`. Files of other guards do not change (no new keys). |
| Sheet | `commit threshold  external prefix score >= ...`; a `commit score  external, frozen` block with the name, version and digest; one more assumption: the score was frozen before calibration and was not fitted, tuned or selected on the LTT items. The `offline_ltt` policy sheet has `status.commit_score = "external"`. |

The LTT guarantee needs a score that did not see the LTT items. The library cannot check this. Fit the score on other data, or on the fit + policy-grid items of the same `seed` split (P11-16 did this). Not combined with `target_precision=`, `grounding=`, `llm=`, `online()`, or the hybrid guard (P5-26).

Validated (P5-35, [results](../experiments/2026-11-21-p5-35-external-prefix-score/results.md)): the P11-16 LX-FL prefix guard (EMG, research only) reproduced through `prefix_score=`: same threshold 0.86, same null-control counts (uniform 0, shuffled 5, user 0 of 300) and the same decisions on 3 x 1,221 test prompts (real: 671 commits, 592 prefix, 46 wrong; time-shuffled and zero EMG: 0 commits), now with a guard file and `config_id`.

## 10c. Optional: streaming word-by-word prefix commits (P5-27)

`fidetype.trust.stream_commit.calibrate_streaming(base, inputs, texts, step_frames=...)` builds a guard that decides at checkpoints while an utterance goes on, not only at its end. `base` is a calibrated prefix guard (10b) with logits input from a **causal** decoder: the first n frames of a stored output must be what the decoder emits live.

| Step | What happens |
|---|---|
| Checkpoints | Every `step_frames` decoder frames and at the end of the utterance. At each one the base pipeline decodes the frames so far. |
| Score | One score per word prefix and checkpoint: the 10b prefix features + `stable_log` (how many earlier checkpoints had the same first k words), `at_end`, `open_last_word`. Same model type as 10a; monotone in k. |
| Commit | Append-only. With K words committed: if the top-1 text does not start with them, no commit (a conflict). Else commit up to the longest prefix with score >= the threshold. Committed words are never retracted. Only the end checkpoint can make a complete commit. |
| Loss | An utterance is wrong if any of its commits is wrong (`wrong-stream-commit`). For append-only commits this equals "the final committed text is wrong". |
| Certify | LTT (fixed sequence 1.00 -> 0.00 step 0.01, exact binomial p-values) on the LTT part of the `calibrate` split; the fit + policy-grid parts fit the score. Fixed-sequence LTT does not need a monotone loss. |
| Guarantee | P( rate of utterances with a wrong commit <= alpha ) >= 1 - delta over the calibration draw, for exchangeable utterances. |
| Events | One event per commit (`fidetype.stream-commit-event/0.1`) with the words added, the words committed so far, the checkpoint time and a hash chain (`prev_id` -> `id`); `StreamingPrefixGuard.check_chain(events)` verifies it. |
| Controls | Uniform and shuffled null inputs are streamed through the final guard; an input with one or more commits counts; more than floor(alpha * n) refuses the guard. |

T15 result (P5-27, pre-registered, [results](../experiments/2026-11-18-p5-27-streaming-prefix/results.md)): step 6 frames (0.48 s), LTT threshold 0.99, controls 0 / 300 and 0 / 300, 5 / 701 wrong trials (0.0071). Under the proposed v0.2 + reading cost it gives 2.34 [2.11, 2.57] against 4.67 for the one-commit prefix guard (10b): the one-commit guard wins. The streaming guard commits words about 10 s earlier, but its single threshold over about 39 checkpoints per trial is strict, and it never extends a commit at the end. Use 10b for words; use 10c only where early commits matter more than the number of words.

Score it with `safe_wpm(..., metric_version="0.2", n_commits=...)`, the proposed "several commits per trial" extension (section 7 of the [v0.2 proposal](safe-wpm-v0.2-proposal.md)). The default behaviour of `calibrate` does not change.

## 11. Online use: adaptive risk control for drift (P5-02, P15-04)

The guard above is calibrated once. Its bound needs exchangeable data (section 3). Live data drift: within a session, between days, after a decoder update. Adaptive conformal methods move the COMMIT threshold from the user's feedback. Their bound holds for **any** sequence of utterances. But it is a **long-run average**, not a 1 − δ statement.

### 11.1 On the drop-in guard: `guard.online(...)`

```python
og = guard.online("aci")                 # or "aci_window", "window", "bandit"
r, tk = og.decide(x)                     # a TrustResult, as from guard.decide(x)
og.feedback(tk, final_text)              # the user's final text, or None if unknown
og.report()["certificate"]               # mean wrong-commit loss <= this number (any sequence)
for s in og.policy_sheets(): print(s)    # offline sheet(s) + the online sheet (section 12)
```

| `method` | Guarantee | Feedback it needs | Controller |
|---|---|---|---|
| `"aci"` (default) | mean wrong-commit loss ≤ α + (λ_end − λ_1)/(η T), any sequence (Gibbs & Candès 2021) | the loss of each decision (labels of commits) | `OnlineCommitRiskControl(method="aci")` |
| `"aci_window"` | mean loss ≤ α + (α_1 − α_end)/(γ T), any sequence; window CRC at an adaptive level | full feedback (truth of non-commits) for the window | `OnlineCommitRiskControl(method="aci_window")` |
| `"window"` | approximate only (weighted CRC; exact only under exchangeability) | full feedback | `OnlineCommitRiskControl(method="window")` |
| `"bandit"` | (G1) marginal or (G2) precision ACI, any sequence; with `explore` > 0 also the (G3) audit | labels of shown items only (section 11.2) | `BanditCommitRiskControl` |

| Item | Meaning |
|---|---|
| Commit score | The guard runs once at `commit_p = 0` (all other rules, the commit gate and the grounding gate unchanged). If it would commit, the score is `p_top1`; else −∞ |
| Floor (`floor=True`, default) | The online threshold never goes below the offline `commit_p`. So the online guard commits a subset of the offline commits: the offline sheet still holds (under section 3), and the online bound holds for any sequence on top. If the offline guard never commits, the online guard never commits either. `floor=False`: only the online bound holds |
| Audit log | Each decision goes into the audit log of the wrapped guard, with an `online` record (method, threshold, ticket, score) |
| The wrapped guard | It does not change. `guard.decide` gives the same results as before |

Tested in `tests/test_trust_p5_02_sheets_online.py`: a synthetic stream drifts after calibration (30 % of the utterances are confidently wrong). The offline guard's wrong-commit rate rises above 2α. The `aci` online guard keeps the realised rate below its certificate and near α.

Not covered: silent errors (a wrong commit that the user does not correct looks right); one short session (slack O(1/(η T))); any single utterance.

### 11.2 Feedback only on what was shown (P15-04)

For online re-calibration during use, the user's feedback exists only for text that was SHOWN (a commit that the user may correct, or an offer that the user picks from or retypes). Withheld items get no label. `BanditCommitRiskControl` works with exactly this feedback. On the drop-in guard, use `guard.online("bandit", explore=0.05)`. On a `DecisionPolicy`:

```python
from fidetype.trust import BanditCommitRiskControl, BanditTrustPolicy
bp = BanditTrustPolicy(policy, BanditCommitRiskControl(alpha=0.05, explore=0.05))
decision, tk = bp.decide(x)          # COMMIT, OFFER (also exploration) or the policy's other action
bp.feedback(tk, final_text)          # the user's final text if shown, else None
bp.controller.report()               # realised rate, certificate, audit per threshold
```

| Statement | Holds for | Needs |
|---|---|---|
| Long-run wrong-commit rate per item ≤ α + (λ_end − λ_start)/(η T) (`target="marginal"`, default) | any sequence (drift, decoder updates) | the labels of commits only |
| Long-run error rate among commits ≤ α + (λ_end − λ_start)/(η N_commits) (`target="precision"`) | any sequence | the labels of commits only; set `lam_init` (at "never commit" it never moves) |
| Audit: upper bound on the wrong commits that any grid threshold would have made on the items decided so far | probability ≥ 1 − δ over the exploration coins | `explore` > 0: withheld items are shown as an OFFER at this rate (never committed); coins unpredictable to whatever produces the data (default `seed=None`, OS entropy; a fixed seed only for replays and tests); every decided item enters the audit at decision time (automatic since the G3 review fix: a shown item counts as wrong until its label arrives, so late or lost labels only widen the bound) |

Audit details. Items that the policy forbids to commit (score −inf) are never explored: they add nothing to the audit. With the floor on (`floor=True`), audit rows for grid thresholds below the floor are marked `floored` in `report()["audit"]` and their numbers are None: scores below the floor never reach the controller, so these rows are not bounds for those thresholds. Review: [G3 audit review](../wiki/questions/g3-audit-review.md).

Not covered: silent errors (wrong commits that the user does not correct), one short session, future items for the audit bound. Full scope: [F1 guarantee scope](../wiki/questions/f1-guarantee-scope.md). Code: [`src/fidetype/trust/bandit_risk.py`](../src/fidetype/trust/bandit_risk.py), [`src/fidetype/trust/online_guard.py`](../src/fidetype/trust/online_guard.py). Replay: [P15-04](../experiments/2026-11-16-p15-04-bandit/results.md).

## 12. One guarantee sheet per policy (P5-02)

Each way to choose the COMMIT threshold gives a different kind of statement. `PolicySheet` states each one in **one format**: machine-readable JSON (schema `fidetype.guarantee-sheet/1.0`) and printable text.

```python
sheets = guard.policy_sheets()           # or og.policy_sheets(), ft.policy_sheets(controller)
print(sheets[0])                         # printable text
ft.save_sheets(sheets, "sheets.json")    # JSON; ft.load_sheets("sheets.json") gives the same sheets back
```

Command line (no decoder needed): `python -m fidetype.trust.guarantee_sheet guard.json` (add `--json` for JSON). It reads a saved guard or a sheet file.

| `policy_type` | Made from | Statement | `validity` |
|---|---|---|---|
| `offline_crc` | `CommitRiskControl(method="crc")` | E[wrong-commit loss] ≤ α | `finite_sample_expectation` |
| `offline_ltt` | every `calibrate` guard; `CommitRiskControl(method="ltt")` | P(wrong-commit rate ≤ α) ≥ 1 − δ | `finite_sample_probability` |
| `precision_ltt` | `calibrate(target_precision=)` | P(error among commits ≤ 1 − target) ≥ 1 − δ_p | `finite_sample_probability` |
| `joint_fluent_wrong` | `calibrate(grounding= / llm=)`, optionally with `target_precision=` | P(wrong-commit ≤ α and fluent-wrong ≤ α_h [and precision]) ≥ 1 − δ_h (one joint test) | `finite_sample_probability` |
| `online_aci` | `guard.online("aci")`; `OnlineCommitRiskControl(method="aci")` | mean loss ≤ certificate, any sequence | `deterministic_long_run` |
| `online_aci_window` | `guard.online("aci_window")` | mean loss ≤ certificate, any sequence | `deterministic_long_run` |
| `online_window` | `guard.online("window")` | approximate | `approximate` |
| `bandit` | `guard.online("bandit")`; `BanditCommitRiskControl` | (G1) / (G2) any sequence; (G3) audit with `explore` > 0 | `deterministic_long_run` (`+anytime_audit`) |

| Field | Meaning |
|---|---|
| `schema` | `fidetype.guarantee-sheet/1.0`. A reader accepts every 1.x sheet. It keeps unknown keys in `extra` and writes them back |
| `policy_type`, `validity` | The table above |
| `statement` | The guarantee in one sentence |
| `method` | How the threshold is chosen, with its parameters |
| `risk` | The controlled risk (name and definition); a list for a joint test |
| `levels` | `alpha` and `delta` always (`delta: null` = deterministic, no failure probability); also `alpha_h`, `target_precision`, `eta`, `explore`, ... |
| `calibration` | Size and scope: `n_items`, the split, ordering and test items, the data scope, the feedback kind (online) |
| `assumptions`, `not_guaranteed` | What must be true; what the sheet does **not** promise. Every sheet lists both |
| `controls` | Null-control results. Empty for an online controller: its controls are those of the wrapped guard |
| `status` | The current state: `feasible`, the threshold; online also `n_observed`, `realised`, `certificate` |
| `warnings`, `config_id`, `references`, `created_utc` | — |

The files write `inf` as the string `"inf"` and nan as `null`, so they are strict JSON. The old `GuaranteeSheet` (`guard.sheet`, section 6) does not change. The policy sheets are made from it.

## 13. Related

- [10-minute quickstart](trust-quickstart.md)
- [Concepts: the trust layer](concepts.md)
- Wiki: [learn then test](../wiki/concepts/learn-then-test.md), [conformal risk control](../wiki/concepts/conformal-risk-control.md), [trust decision](../wiki/concepts/trust-decision.md), [streaming trust layer](../wiki/concepts/streaming-trust-layer.md)
- Source: [`src/fidetype/trust/dropin.py`](../src/fidetype/trust/dropin.py)
