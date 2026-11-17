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
| How | For each threshold `commit_p` (grid 1.00 → 0.00, step 0.01, or `precision_grid`): exact binomial p-value P(Bin(commits, β) ≤ wrong) on the commits of the LTT part, β = 1 − `target_precision`. Given the number of commits, the commits are an exchangeable sample, so the p-value is valid. p ≤ δ is the same test as "one-sided Clopper-Pearson upper bound ≤ β". The error rate is not monotone in `commit_p`, so the test order comes from the policy part (smallest p-value first), and a fixed-sequence test on the LTT part certifies the thresholds ([learn then test](../wiki/concepts/learn-then-test.md)) |
| Selection | The certified threshold with the most commits, but never below the plain `commit_p`. A higher threshold only removes commits, so section 1 and the null controls still hold |
| No certified threshold | The guard never commits (sheet warning). It still offers and withholds |
| Cost | To certify a threshold, the LTT part needs at least log δ / log(`target_precision`) right commits: 22 for 0.9, 45 for 0.95, 230 for 0.99 (δ 0.1). A decoder that is rarely right cannot get a useful precision guarantee |
| Sheet | A "precision bound" block: target, δ_p, the selected threshold, the P14-03 threshold, how many thresholds were tested and certified, the test commits and a one-sided CP lower bound on precision |

Not guaranteed: precision for one session or one user; any single commit; data that differ from the calibration data (section 3). The precision bound cannot be combined with the hallucination bound (section 9) yet. `ft.load` needs nothing extra. Code: [`src/fidetype/trust/precision_bound.py`](../src/fidetype/trust/precision_bound.py). Validated on synthetic exchangeable data (the test suite: violation rate at most δ over 200 draws). On the P14-03 replay sets (T15, T12; targets 0.5 to 0.95) no threshold was certified: the decoders are right on only about 8 % of sentences, so the guard never commits (P14-03 guard: 2 of 2 and 15 of 25 commits wrong). Safe, but not yet useful on these decoders ([experiment](../experiments/2026-11-16-p5-02-precision/results.md)).

## 11. Related

- [10-minute quickstart](trust-quickstart.md)
- [Concepts: the trust layer](concepts.md)
- Wiki: [learn then test](../wiki/concepts/learn-then-test.md), [conformal risk control](../wiki/concepts/conformal-risk-control.md), [trust decision](../wiki/concepts/trust-decision.md), [streaming trust layer](../wiki/concepts/streaming-trust-layer.md)
- Source: [`src/fidetype/trust/dropin.py`](../src/fidetype/trust/dropin.py)
