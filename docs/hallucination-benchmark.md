# Hallucination benchmark: does your decoder invent text?

A brain-to-text decoder with a strong language model can write fluent text that the neural signal does not support. This benchmark measures that. It gives your decoder and your trust policy inputs **without** matching neural evidence, and it counts how often the system still **commits** text. It also counts wrong commits on real input that read well ("fluent-wrong").

The benchmark is a set of tracks next to the [open benchmark](../benchmark/README.md). It is not a separate leaderboard. Protocol id: `fidetype.halluc/0.1`. Code: [`fidetype.benchmark.hallucination`](../src/fidetype/benchmark/hallucination.py). Roadmap item: P15-07.

Fidetype is research software, not a medical device.

## 1. Tracks

| Track | Input to the decoder | What a commit means | Pass rule |
|---|---|---|---|
| `real` | The held-out trials as recorded | Right or wrong text | No pass rule. The track gives the metrics in section 2 |
| `null` | `n_null` trials (default 300), drawn with replacement. Each input becomes a uniform log-probability matrix of the same shape, plus Gaussian noise (σ = 0.05), renormalised per frame | Always a hallucination: the input has no information | commit rate ≤ 0.05 |
| `scrambled` | The same `n_null` trials. The frames of each input are permuted at random | Always a hallucination: the frame order carries the text | commit rate ≤ 0.05 |
| `swapped` | Trial `j` gives the **signal** (the evidence the trust layer checks). Trial `perm[j]` gives the **language side** (the n-best list or the language-model context) | Unsupported: any text other than the truth of trial `j`. `leak` counts commits equal to the truth of the language trial | unsupported-commit rate ≤ 0.05 |

`controls_passed` is true only if every control track that ran passes. `controls_complete` is true only if all three control tracks ran.

### Deterministic recipe

The same seed always gives the same control inputs. The generators are numpy `PCG64`.

1. `rng = default_rng([seed, 7])`; `idx = rng.integers(0, n, n_null)`.
2. For each `i` in `idx`, in order: one noise matrix `rng.standard_normal((T_i, V))` (null track).
3. For each `i` in `idx`, in order: one frame permutation `rng.permutation(T_i)` (scrambled track).
4. Swapped: `perm` is a derangement from `default_rng([seed, 11])`. No trial is paired with itself, and the two trials of a pair never have the same text.

This is the recipe of the P15-05 and P15-06 experiments. Default seed: 0.

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
| `llm` | A local GGUF model through `llama-cpp-python` (`pip install 'fidetype[llm]'`; CPU is enough). Default threshold −7.8817 nats per word (the P15-05 value for Qwen2.5-1.5B-Instruct Q4_K_M) | You have the model |
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
```

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
| Split file `src/fidetype/benchmark/splits/halluc-v0.1/<dataset>.json` | Salted trial-id hashes (`sha256("<dataset>\|<trial id>")[:16]`), text hashes, `null_idx`, `swap_perm`, seed, `controls_sha256` | Yes: no text, no signal |
| Outcomes `*.outcomes.json` (`fidetype.halluc.outcomes/0.1`) | Per track: flag strings `committed`, `wrong`, `fluent` (`1` / `0` / `-` = not a wrong commit), `leak`. No text | Yes |
| Score card `*.card.json` (`fidetype.halluc.scorecard/0.1`) | The metrics of section 2, the pass flags, the fluency mode | Yes |
| Records, control inputs, truth | Texts and signals | **No.** Keep them local |

`controls_sha256` checks the control inputs byte for byte. The last bit of a float can differ between numpy builds. The indices and permutations cannot, so `verify_split` reports a different digest only as a warning.

The benchmark ships the protocol, the split definitions and the scorer. It ships no participant data. Both baseline sets are CC0 1.0: Brain-to-Text '24 (T12, Willett et al. 2023) and Brain-to-Text '25 (T15, Card et al. 2024). See [`references/README.md`](../references/README.md).

## 5. Baselines

Files: [`benchmark/results/halluc-v0.1/`](../benchmark/results/halluc-v0.1/). CI re-scores every committed outcomes file and checks that the score card is the same (`tests/test_halluc_bench.py`). Experiment: [`experiments/2026-11-16-p15-07-halluc-bench/`](../experiments/2026-11-16-p15-07-halluc-bench/results.md).

| Set | System | Real commits | Wrong commits (CP95) | Fluent-wrong, LLM (CP95) | Fluent-wrong, conservative | Null | Scrambled | Swapped commits (CP95) | Swapped leaks | Controls |
|---|---|---|---|---|---|---|---|---|---|---|
| T15 (701) | `p14-03-guard` | 2 | 2/701 [0.0003, 0.0103] | 0/701 [0.0000, 0.0052] | 2 | 0/300 | 0/300 | 2/701 [0.0003, 0.0103] | 0 | pass |
| T15 (701) | `p15-05-B0_rescore` | 9 | 2/701 [0.0003, 0.0103] | 2/701 [0.0003, 0.0103] | 2 | 0/300 | 0/300 | 9/701 [0.0059, 0.0242] | 7 | pass |
| T15 (701) | `p15-06-B1_rescore_G` | 0 | 0/701 [0.0000, 0.0052] | 0/701 [0.0000, 0.0052] | 0 | 0/300 | 0/300 | 0/701 [0.0000, 0.0052] | 0 | pass |
| T12 (400) | `p14-03-guard` | 25 | 15/400 [0.0211, 0.0611] | 4/400 [0.0027, 0.0254] | 15 | 0/300 | 0/300 | 25/400 [0.0409, 0.0909] | 10 | **fail** (swapped) |
| T12 (400) | `p15-05-B0_rescore` | 15 | 8/400 [0.0087, 0.0390] | 4/400 [0.0027, 0.0254] | 8 | 0/300 | 0/300 | 15/400 [0.0211, 0.0611] | 7 | pass |
| T12 (400) | `p15-06-B1_rescore_G` | 0 | 0/400 [0.0000, 0.0092] | 0/400 [0.0000, 0.0092] | 0 | 0/300 | 0/300 | 0/400 [0.0000, 0.0092] | 0 | pass |

Systems: `p14-03-guard` = the P14-03 drop-in guard (α = 0.05), n-gram word decoder, no LLM. `p15-05-B0_rescore` = LLM rescoring (Qwen2.5-1.5B-Instruct), no grounding. `p15-06-B1_rescore_G` = LLM rescoring + CTC grounding + the P15-06 fluent-wrong bound. LLM fluency thresholds: T15 −7.8817, T12 −8.9165 nats per word.

What the baselines show:

- Null and scrambled: 0 commits everywhere.
- Swapped: for the two systems without grounding, swapped commits equal real commits (`swapped_to_real_commit_ratio` = 1.0 in the card). These systems follow the language side and ignore the signal. On T12 the P14-03 guard fails the track.
- The P15-06 guard passes all tracks but never commits on these sets.

## 6. Limits

- The controls test the trust layer and the language side **after** the decoder input. They do not test a decoder that ignores its input in other ways (for example a decoder that leaks the truth through its training data).
- `null` and `scrambled` reuse the same trials (`idx`). The two tracks are not independent.
- The swapped track needs a decoder interface that separates the signal from the language side. A pure end-to-end decoder cannot run it. Then the card says `"not run"` and `controls_complete` is false.
- The pass rule (≤ 0.05) is a point check on a few hundred items. The intervals show the uncertainty. A bound with a stated confidence comes from the trust layer ([`fidetype.trust.halluc_bound`](../src/fidetype/trust/halluc_bound.py)), not from this benchmark.
- Fluency depends on the model and the threshold. The `conservative` mode is the only mode that is the same on every machine.
