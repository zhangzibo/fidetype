# Hallucination benchmark: does your decoder invent text?

Tracks and a scorer that test whether your decoder and trust policy commit text that the neural signal does not support.

**Status:** Alpha ([status levels](glossary.md#status-levels))

A brain-to-text decoder with a strong language model can write fluent text that the neural signal does not support. This benchmark measures that. It gives your decoder and your trust policy inputs **without** matching neural evidence, and it counts how often the system still **commits** text. It also counts wrong commits on real input that read well ([fluent-wrong](glossary.md#fluent-wrong)). A [commit](glossary.md#commit-offer-withhold) is text that the system types without a user choice.

The benchmark is a set of tracks next to the [open benchmark](../benchmark/README.md). It is not a separate leaderboard. Protocol id: `fidetype.halluc/0.2` (current). The old protocol `fidetype.halluc/0.1` stays available: `--protocol 0.1`. The two protocols have the same tracks and files. Only the pass rule of the `swapped` track changes (section 1.1). Code: [`fidetype.benchmark.hallucination`](../src/fidetype/benchmark/hallucination.py).

Fidetype is research software, not a medical device.

## 1. Tracks

| Track | Input to the decoder | What a commit means | Pass rule |
|---|---|---|---|
| `real` | The held-out trials as recorded | Right or wrong text | No pass rule. The track gives the metrics in section 2 |
| `null` | `n_null` trials (default 300), drawn with replacement. Each input becomes a uniform log-probability matrix of the same shape, plus Gaussian noise (σ = 0.05), renormalised per frame | Always a hallucination: the input has no information | commit rate ≤ 0.05 |
| `scrambled` | The same `n_null` trials. The frames of each input are permuted at random | Always a hallucination: the frame order carries the text | commit rate ≤ 0.05 |
| `swapped` | Trial `j` gives the **signal** (the evidence the trust layer checks). Trial `perm[j]` gives the **language side** (the n-best list or the language-model context) | Unsupported: any text other than the truth of trial `j`. `leak` counts commits equal to the truth of the language trial | 0.2: paired swapped / real commit-ratio test (section 1.1). 0.1: unsupported-commit rate ≤ 0.05 |

Each control track has a `verdict`: `pass`, `fail` or `insufficient evidence` (0.2). `controls_verdict` is `fail` if any control track fails, `pass` if all three control tracks ran and pass, else `insufficient evidence`. `controls_passed` is true only for `pass`. In 0.2 a missing swapped track is never a pass. `controls_complete` is true only if all three control tracks ran. (0.1: `controls_passed` is true if every control track that ran passes.)

### 1.1 The swapped rule of protocol 0.2

Why: the 0.1 rule (≤ 0.05) lets a system that rarely commits pass without a signal check. On the T15 set (data of implant participant [T15](glossary.md#t12-t15)) two systems with swapped commits = real commits passed it.

Pairs: real item `j` and swapped item `j` have the **same signal** (trial `j`). Per pair, `R` = the real item commits, `S` = the swapped item makes an unsupported commit.

| cell | R | S |
|---|---|---|
| `n10` | 1 | 0 |
| `n01` | 0 | 1 |
| `n11` | 1 | 1 |

`m = n10 + n01 + n11`, `Y = n01 + n11`, `θ_r = r / (1 + r)`.

| verdict | condition |
|---|---|
| `pass` | one-sided Clopper-Pearson upper bound (1 − α) of `Y / m` is below `θ_r`. Then P(swapped commit) / P(real commit) ≤ `r`, with error ≤ α |
| `fail` | not pass, and `m ≥ m_min`, or the one-sided lower bound of `n01 / m` is above `θ_r` (clear evidence that the ratio is above `r`) |
| `insufficient evidence` | all other cases. It is **not** a pass |

Constants (pre-registered, [plan](../experiments/2026-11-17-p15-15-halluc-0.2/plan.md)): `r` = 0.5, α = 0.05, `m_min` = 25 (power ≥ 0.9 when the true ratio is 0.1). No pass is possible with `m` < 8. The test is conservative: `n11` counts against the system. The card shows `n10`, `n01`, `n11`, the bound and the ratio estimate (`swapped.paired`), and the old result (`swapped.pass_v01_rule`).

### Deterministic recipe

The same seed always gives the same control inputs. The generators are numpy `PCG64`.

1. `rng = default_rng([seed, 7])`; `idx = rng.integers(0, n, n_null)`.
2. For each `i` in `idx`, in order: one noise matrix `rng.standard_normal((T_i, V))` (null track).
3. For each `i` in `idx`, in order: one frame permutation `rng.permutation(T_i)` (scrambled track).
4. Swapped: `perm` is a derangement from `default_rng([seed, 11])`. No trial is paired with itself, and the two trials of a pair never have the same text.

Our baseline experiments use this recipe. Default seed: 0.

### Where the controls act

The controls act on the **decoder input that the trust layer sees**. In our baselines this is the `(T, V)` phoneme log-probability matrix, and the "decoder" is the word decoder plus the language models after it. If your system starts from raw neural features, you can apply the same recipe to the features. State which level you used.

## 2. Metrics

All rates are over **all items of a track** (marginal), with an exact Clopper-Pearson 95 % interval ([`fidetype.utils.binomial`](../src/fidetype/utils/binomial.py)).

| Metric | Definition |
|---|---|
| `commit_rate` | commits / items |
| `wrong_commit_rate` | commits whose text is not the truth of the signal trial / items. On `null` and `scrambled`, every commit counts |
| `fluent_wrong_rate` | wrong commits that are fluent / items. **The headline metric of the `real` track** |
| `error_among_commits` | wrong commits / commits (precision view; it can be high when the system rarely commits) |
| `fluent_among_wrong_commits` | fluent wrong commits / wrong commits |
| `leak_commits` (`swapped`) | commits equal to the truth of the language trial |
| `swapped_to_real_commit_ratio` (headline) | swapped commits / real commits. About 1: the commits follow the language side and ignore the signal. About 0: the signal vetoes them |

Text comparison: exact match after joining runs of spaces and stripping the ends (as the trust guarantee).

### Fluency

A wrong commit is **fluent** if a language model finds it plausible: `log p_LLM(text) / words ≥ threshold`.

| Mode | How | When |
|---|---|---|
| `llm` | A local GGUF model through `llama-cpp-python` (`pip install 'fidetype[llm]'`; CPU is enough). Default threshold −7.8817 nats per word (our measured value for Qwen2.5-1.5B-Instruct Q4_K_M) | You have the model |
| `llm-table` | A precomputed table `text → log-prob` (for example an LLM cache). A missing text counts as fluent, and the card reports the count | You scored the texts before |
| `conservative` | **Deterministic fallback.** Every wrong commit counts as fluent. Then `fluent_wrong_rate = wrong_commit_rate`: an upper bound | No LLM, or for CI |

The score card always names the mode and the threshold. Compare fluent-wrong rates only between cards with the same mode, model and threshold.

## 3. How to run it

### From Python (your decoder + trust policy in one call)

```python
from fidetype.benchmark import hallucination as hb

ctl = hb.make_controls(xs, texts, seed=0, n_null=300)        # xs: held-out (T, V) inputs; texts: truths
records = hb.run_tracks(guard.decide, xs, texts, controls=ctl,
                        decide_swapped=my_swapped_decide)     # (x_signal, language_trial) -> decision
outcomes = hb.to_outcomes(records, hb.ConservativeFluency(), dataset="my-set", system="my-decoder")
card = hb.score_outcomes(outcomes)
print(hb.summary_line(card))
```

`decide(x)` returns an object or a dict with `action` (`"commit"`, `"offer"` or `"withhold"`) and `text`. A `fidetype.trust.TrustGuard` works as it is. Without `decide_swapped`, the swapped track does not run, and the card says `"not run"`.

How to build `decide_swapped`: decode the language side from trial `language_trial` (its n-best list or its language-model context), and give the trust layer the signal `x_signal`. With a `TrustGuard` and your own `decode_fn`, make a second guard whose `decode_fn` ignores its input and returns the n-best list of the language trial (see `experiments/2026-11-16-p15-07-halluc-bench/run.py`).

### From the command line (any decoder, any language)

```bash
# 1. control inputs + split file from your held-out inputs (NPZ: one (T, V) array per trial id)
python -m fidetype.benchmark.hallucination controls held_out.npz --truth truth.jsonl \
    --dataset my-set --licence "CC0 1.0" --out controls.npz --split split.json
# 2. run your decoder + trust policy on held_out.npz, controls.npz and the swapped pairs; write decisions.jsonl
# 3. score
python -m fidetype.benchmark.hallucination score decisions.jsonl --truth truth.jsonl --split split.json \
    --outcomes outcomes.json --out card.json            # add --fluency llm --llm-model model.gguf for LLM fluency
# 4. anyone can re-score the outcomes (flags only, no text)
python -m fidetype.benchmark.hallucination rescore outcomes.json --check card.json
# the old protocol: add --protocol 0.1
```

Each committed score card also holds a rerun recipe (key `rerun`, schema `fidetype.hub.recipe/0.1`): the exact `rescore` command with the committed outcomes file, the guard `config_id`, the decoder weights SHA-256 and the split file hash. `rescore --check` leaves out the `rerun` block. `python -m fidetype.benchmark.hub recipe <card>` prints it.

`controls.npz` holds `null/00000`, ..., `scrambled/00000`, ... in item order. It is derived from your data: keep it local.

**Decisions file** (`fidetype.halluc.decisions/0.1`, JSON Lines). The first line is a header with `null_idx` and `swap_perm` copied from the split file. Then one line per decision:

```json
{"schema": "fidetype.halluc.decisions/0.1", "null_idx": [...], "swap_perm": [...]}
{"track": "real", "item": 0, "action": "commit", "text": "the words you committed"}
{"track": "null", "item": 0, "action": "withhold", "text": null}
{"track": "swapped", "item": 5, "action": "offer", "text": null}
```

`item` is the item index of the track: the held-out position for `real` and `swapped` (signal = trial `item`, language side = trial `swap_perm[item]`), the control index for `null` and `scrambled`. A track must be complete or absent.

## 4. Files and licences

| File | Content | Public? |
|---|---|---|
| Split file `src/fidetype/benchmark/splits/halluc-v0.1/<dataset>.json` (the same for 0.1 and 0.2) | Salted trial-id hashes (`sha256("<dataset>\|<trial id>")[:16]`), text hashes, `null_idx`, `swap_perm`, seed, `controls_sha256` | Yes: no text, no signal |
| Outcomes `*.outcomes.json` (`fidetype.halluc.outcomes/0.1`) | Per track: flag strings `committed`, `wrong`, `fluent` (`1` / `0` / `-` = not a wrong commit), `leak`. No text | Yes |
| Score card `*.card.json` (`fidetype.halluc.scorecard/0.2`; old: `/0.1`) | The metrics of section 2, the verdicts and pass flags, the paired swapped counts (0.2), the fluency mode | Yes |
| Records, control inputs, truth | Texts and signals | **No.** Keep them local |

**Trial ids of the T15 split (`b2t25-t15-val-eval`).** The id is `<session>|val|<i>`. `i` is the position of the trial inside the session's `val_eval` list. It is **not** the index in the HDF5 file `data_val.hdf5`. The rule (fields `id_rule` and `id_sessions` of the split file):

1. For each session, list the trial groups of `data_val.hdf5` in sorted key order. Index them j = 0, 1, 2, ...
2. Even j = `val_select` (calibration). These trials are never in the split.
3. Odd j = `val_eval`. Then i = (j - 1) / 2, so the HDF5 index is **j = 2i + 1**.
4. The 3 trials in `excluded` (out-of-lexicon words) keep their `i`. They are not in the split. There is no renumbering.
5. Held-out order: the `id_sessions` order (sorted session names), then `i` ascending.

`fidetype.benchmark.hallucination.ids_from_rule(split)` rebuilds the 701 ids from the split file, and `tests/test_halluc_bench.py` checks them against the hashes. If you read `i` as the HDF5 `val` index, 358 of the 701 ids point to `val_select` (calibration) trials, and the hashes do not match ([T15 split audit](../wiki/questions/t15-split-audit.md), issue C). The T12 split (`b2t24-t12-test`) uses its own id space (`<session>|pool|<i>`, the T12 v2 trust pool).

`controls_sha256` checks the control inputs byte for byte. The last bit of a float can differ between numpy builds. The indices and permutations cannot, so `verify_split` reports a different digest only as a warning.

The benchmark ships the protocol, the split definitions and the scorer. It ships no participant data. Both baseline sets are CC0 1.0: Brain-to-Text '24 (T12, Willett et al. 2023) and Brain-to-Text '25 (T15, Card et al. 2024). See [`references/README.md`](../references/README.md).

## 5. Baselines

### 5.1 Protocol 0.2 (current)

Cards: [`benchmark/results/halluc-v0.2/`](../benchmark/results/halluc-v0.2/), re-scored from the committed 0.1 outcomes (the outcomes do not change). CI re-scores them (`tests/test_halluc_protocol_02.py`). Details: [protocol 0.2 experiment record](../experiments/2026-11-17-p15-15-halluc-0.2/results.md).

| Set | System | Real commits | Swapped unsupported | n10 / n01 / n11 | m | Swapped verdict (0.2) | Controls 0.1 → 0.2 |
|---|---|---|---|---|---|---|---|
| T15 (701) | `p14-03-guard` | 2 | 2 | 2 / 2 / 0 | 4 | insufficient evidence | pass → **insufficient evidence** |
| T15 (701) | `p15-05-B0_rescore` | 9 | 9 | 9 / 9 / 0 | 18 | insufficient evidence | pass → **insufficient evidence** |
| T15 (701) | `p15-06-B1_rescore_G` | 0 | 0 | 0 / 0 / 0 | 0 | insufficient evidence | pass → **insufficient evidence** |
| T12 (400) | `p14-03-guard` | 25 | 25 | 24 / 24 / 1 | 49 | fail | fail → fail |
| T12 (400) | `p15-05-B0_rescore` | 15 | 15 | 14 / 14 / 1 | 29 | fail | pass → **fail** |
| T12 (400) | `p15-06-B1_rescore_G` | 0 | 0 | 0 / 0 / 0 | 0 | insufficient evidence | pass → **insufficient evidence** |

Both fluency modes give the same verdicts (the commit flags do not depend on fluency). No baseline passes under 0.2: none commits often **and** checks the signal. A baseline that does both is open work.

### 5.2 Protocol 0.1 (old; kept for reference)

Files: [`benchmark/results/halluc-v0.1/`](../benchmark/results/halluc-v0.1/). These cards use the old pass rule. CI re-scores every committed outcomes file with `protocol="0.1"` and checks that the score card is the same (`tests/test_halluc_bench.py`). Details: [protocol 0.1 experiment record](../experiments/2026-11-16-p15-07-halluc-bench/results.md).

| Set | System | Real commits | Wrong commits (CP95) | Fluent-wrong, LLM (CP95) | Fluent-wrong, conservative | Null | Scrambled | Swapped commits (CP95) | Swapped leaks | Controls |
|---|---|---|---|---|---|---|---|---|---|---|
| T15 (701) | `p14-03-guard` | 2 | 2/701 [0.0003, 0.0103] | 0/701 [0.0000, 0.0052] | 2 | 0/300 | 0/300 | 2/701 [0.0003, 0.0103] | 0 | pass |
| T15 (701) | `p15-05-B0_rescore` | 9 | 2/701 [0.0003, 0.0103] | 2/701 [0.0003, 0.0103] | 2 | 0/300 | 0/300 | 9/701 [0.0059, 0.0242] | 7 | pass |
| T15 (701) | `p15-06-B1_rescore_G` | 0 | 0/701 [0.0000, 0.0052] | 0/701 [0.0000, 0.0052] | 0 | 0/300 | 0/300 | 0/701 [0.0000, 0.0052] | 0 | pass |
| T12 (400) | `p14-03-guard` | 25 | 15/400 [0.0211, 0.0611] | 4/400 [0.0027, 0.0254] | 15 | 0/300 | 0/300 | 25/400 [0.0409, 0.0909] | 10 | **fail** (swapped) |
| T12 (400) | `p15-05-B0_rescore` | 15 | 8/400 [0.0087, 0.0390] | 4/400 [0.0027, 0.0254] | 8 | 0/300 | 0/300 | 15/400 [0.0211, 0.0611] | 7 | pass |
| T12 (400) | `p15-06-B1_rescore_G` | 0 | 0/400 [0.0000, 0.0092] | 0/400 [0.0000, 0.0092] | 0 | 0/300 | 0/300 | 0/400 [0.0000, 0.0092] | 0 | pass |

Systems (the ids are the file names of the score cards): `p14-03-guard` = the drop-in [trust guard](trust-quickstart.md) ([α](glossary.md#alpha-delta) = 0.05), n-gram word decoder, no LLM. `p15-05-B0_rescore` = LLM rescoring (Qwen2.5-1.5B-Instruct), no grounding. `p15-06-B1_rescore_G` = LLM rescoring + CTC grounding + a fluent-wrong bound ([`fidetype.trust.halluc_bound`](../src/fidetype/trust/halluc_bound.py)). LLM fluency thresholds: T15 −7.8817, T12 −8.9165 nats per word.

What the baselines show:

- Null and scrambled: 0 commits everywhere.
- Swapped: for the two systems without grounding, swapped commits equal real commits (`swapped_to_real_commit_ratio` = 1.0 in the card). These systems follow the language side and ignore the signal. On T12 the `p14-03-guard` system fails the track.
- The `p15-06-B1_rescore_G` system passes all tracks but never commits on these sets.
- Protocol 0.2 changes 5 of these 6 verdicts (section 5.1).

## 6. Limits

- The controls test the trust layer and the language side **after** the decoder input. They do not test a decoder that ignores its input in other ways (for example a decoder that leaks the truth through its training data).
- `null` and `scrambled` reuse the same trials (`idx`). The two tracks are not independent.
- The swapped track needs a decoder interface that separates the signal from the language side. A pure end-to-end decoder cannot run it. Then the card says `"not run"` and `controls_complete` is false.
- The null and scrambled pass rule (≤ 0.05) is a point check on a few hundred items. The intervals show the uncertainty. A system that never commits passes these two tracks; the 0.2 swapped rule then gives `insufficient evidence`.
- The 0.2 swapped rule bounds a ratio, not an absolute rate. A system that commits on most items can pass with many unsupported swapped commits, if its real commits are more than twice as many. Read the swapped commit rate next to the verdict.
- The pairs share the signal trial; the language trial of a swapped item is the real item of another pair. The test treats the pairs as independent.
- A bound with a stated confidence comes from the trust layer ([`fidetype.trust.halluc_bound`](../src/fidetype/trust/halluc_bound.py)), not from this benchmark.
- Fluency depends on the model and the threshold. The `conservative` mode is the only mode that is the same on every machine.
