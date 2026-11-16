---
title: P15-05 (F2 / E3) LLM rescoring and rewrite with a grounding check - plan
type: experiment
task: P15-05
updated: 2026-11-15
---

# P15-05: faithful LLM decoding with a run-time grounding check (plan)

Written before the runs. Pillar F2, experiment E3 ([north star](../../wiki/questions/north-star.md#f2-faithful-language-model-decoding-e3), [roadmap P15-05](../../wiki/questions/roadmap-standard.md#p15-05-e3-llm-rescoring-with-a-grounding-check)). Before this plan, the code ran only on smoke subsets of 80 `val_select` trials (code check and timing; no held-out trial; outputs not used). The smoke test found one design issue, fixed before the runs: the guard passes tempered frames to `decode_fn` (see Rescoring below).

## Question
Can a local LLM improve the decoded text, while a run-time check blocks text that the neural evidence does not support, and the trust layer still keeps its bound and its null controls?

## Setup
| item | value |
|---|---|
| data | T15 (Brain-to-Text '25, CC0), M4-12 `m4-12-fixed0` recorded phoneme log-probs `(T, 41)`, read only. Fit: `val_select` (722 even-index `val` trials). Held out: `val_eval` (701 odd-index trials). Same files and split as [P14-03](../2026-11-16-p14-03-replay-validation/plan.md). T12 v2 (CC0, by session, 480 -> 400) only if time allows, same code |
| current decoder (base) | the P14-03 word route: CTC phoneme beam -> CMUdict lexicon -> char 6-gram LM (tuned B2T '25 config), 10-best word list |
| LLM | Qwen2.5-1.5B-Instruct, GGUF Q4_K_M, official Qwen build. Licence Apache-2.0. Source: `https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF` (revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, file `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes). SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` (checked after download and at each run start). Local path: `C:\Users\zhang\bci-data\models\qwen2.5-1.5b-instruct-gguf\` (not in the repo) |
| runtime | `llama-cpp-python` 0.3.36, CPU wheel (AVX2), in the repo venv as the new optional extra `fidetype[llm]`. CPU only, 4 threads, under `fidetype.utils.isolation run --class background --threads 4`. No GPU |
| trust layer | public `fidetype.trust.calibrate(...)` with the arm's pipeline as `decode_fn`, alpha 0.05, delta 0.1, seed 0, `stream_texts` = phoneme strings (as P14-03); built-in null controls (uniform 300, shuffled 300, max commits = alpha * 300) |

Smoke timing: about 0.09 s per LLM sentence score, about 0.7 s per rewrite. All 701 + 722 trials fit in the CPU budget, so **no subset** is used.

## Arms (8)
| arm | base n-best | LLM rescoring | LLM rewrite | grounding check |
|---|---|---|---|---|
| A0 | yes | - | - | - |
| A1 | yes | - | - | yes |
| B0 | yes | yes | - | - |
| B1 | yes | yes | - | yes |
| C0 | yes | yes | limited to the n-best lattice | - |
| C1 | yes | yes | limited to the n-best lattice | yes |
| D0 | yes | yes | free (reference hazard arm) | - |
| D1 | yes | yes | free (reference hazard arm) | yes |

- **Rescoring:** `score += lambda * log p_LLM(text)`; `log p_LLM` = log-probability of the text plus end-of-text after a fixed short chat prefix. `lambda` from the grid {0.1, 0.25, 0.5, 1.0, 2.0}: lowest `val_select` top-1 WER (ties: the smaller value). `tau` and `lambda` are fitted on the `val_select` inputs as the guard gives them to `decode_fn`: `log_softmax(x / T_frame)`, with `T_frame` from the A0 calibration (the smoke test showed that a calibrated guard tempers the frames before `decode_fn`). A0 therefore runs first.
- **Rewrite:** greedy LLM answer (temperature 0) to a fixed prompt with the top-5 candidates (after rescoring). The rewrite goes on top of the list (best score + 2.0); its character confidences are copied from the decoder candidates that have the same word (at the same position first), else 0.
  - C ("lattice"): the prompt says "use only words in the guesses", and a rewrite with any word outside the word bag of the base 10-best is discarded (counted).
  - D ("free"): the prompt says "correct any wrong words"; no lattice limit. D is not a candidate method. It is the hazard reference that shows what the grounding check does with text from the LLM prior.
- **Grounding check** (new reusable code `fidetype.trust.grounding`): `deficit(c) = (log p_ctc(anchor | x) - log p_ctc(c | x)) / T`, with `log p_ctc` the CTC forward score of the CMUdict phoneme sequence of the text (words joined by the SIL label; the best of up to 16 pronunciation variants), `anchor` = base top-1 for the same input, `T` = frames. A text with a word not in CMUdict has deficit infinity. `tau` = split-conformal 95 % quantile of the deficits of the **true** `val_select` texts (rank `ceil((n + 1) 0.95)`). A failing candidate stays in the list (so the n-best still shows the doubt) but drops below the best passing candidate (score = best passing - 1.0 x rank). If no candidate passes, the list is empty and the trust layer withholds.

## Controls
- **Uniform** and **time-shuffled** inputs: (a) the built-in controls of `calibrate` (from `val_select`; a refused config is a finding, not weakened); (b) our own 300 + 300 seeded draws from `val_eval` per arm, through the calibrated guard.
- **Swapped signal** (mismatched evidence), 701 trials per arm: for held-out trial `j`, the language side (base n-best, LLM rescoring and rewrite) is computed from trial `i = perm(j)` (seeded derangement, different text), while the input that the guard and the grounding check see is trial `j`. This is the case "the LLM writes text from its context or prior, not from the current signal". A commit whose text is not the truth of trial `j` is unsupported by the signal. We also count commits equal to the truth of trial `i` (leak). Expected: arms without grounding commit at about their normal rate (the trust gate sees only the n-best); arms with grounding should not.
- Why not the "standard" swap (feed trial `j` and score against the truth of `i`): our pipeline has no context of trial `i`, so it would pass trivially and test nothing.

## Metrics (held-out `val_eval`, per arm)
- WER and sentence accuracy of the pipeline top-1 (all 701 trials; empty output = all words deleted).
- Commits, wrong commits, wrong-commit rate over all trials with a Clopper-Pearson 95 % interval; offers, withholds.
- **Hallucination rate** = unsupported words / shown words, over committed texts and first offered choices. An **unsupported word** is a shown word that the word alignment does not match to the truth **and** that is in no candidate of the base 10-best of the same input (it does not come from the neural decode). By construction this is 0 for A and B (they only reorder base candidates); it measures what a rewrite adds.
- **Fluent-wrong commits:** wrong commits with LLM log-prob per word at or above the median of the true `val_select` texts.
- Null and swapped commits as above; WER difference to A0 with a paired bootstrap (2000 resamples, seed 0, 95 % percentile interval).

## Pre-registered success criteria
Primary arm: **B1** (LLM rescoring + grounding). Comparison: A0 (current).
1. **S1 accuracy:** WER(B1) < WER(A0), and the paired-bootstrap 95 % interval of WER(B1) - WER(A0) is below 0.
2. **S2 bound:** `calibrate` returns a guard (built-in controls pass) and the held-out wrong-commit rate <= 0.05.
3. **S3 controls:** held-out uniform and shuffled commits <= 1 / 300 each; swapped-signal commits not equal to the truth of the signal <= 2 / 701.
4. **S4 hallucination:** hallucination rate(B1) <= hallucination rate(A0), and fluent-wrong commits(B1) <= fluent-wrong commits(A0).

**F2/E3 pass** = S1-S4 all pass for B1. Secondary (descriptive, same four checks): C1 against A0. Grounding effect (descriptive): X1 against X0 for X in A-D (swapped commits, hallucination rate, WER cost). If S1 fails but S2-S4 pass, the result is "safe but no gain" (a valid negative result).

## Honest limits (known before the run)
- One participant, one split, one LLM (1.5B, 4-bit). A larger LLM may help more.
- `tau` is a coverage statement on true texts (95 %), not a bound on hallucinated commits; that is P15-06.
- The hallucination word metric uses the base 10-best as "supported by the signal". A word can be in the 10-best and still be weakly supported.
- The LLM rewrite candidate is not rescored; its rank comes from the fixed margin.
- The B2T '25 T15 word route commits rarely (P14-03: 2 / 701), so the commit counts are small.

## Outputs
- Repo: `run.py`, `config.json`, `launch_detached.py`, `results/results-t15.json` (aggregates), `results/run.log`, `results.md`.
- Per-trial outputs, caches (base n-best, LLM scores and rewrites in sqlite), guard files: `C:\Users\zhang\bci-data\derived\f2-e3-llm-grounding\` only.
