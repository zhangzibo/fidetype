---
title: P11-07 character LM inside the CTC beam for the emg2qwerty EMG decoder - pre-registration
type: experiment
task: P11-07
updated: 2026-11-19
---

# P11-07: a character LM inside the CTC beam for the P11-01 EMG decoder (pre-registration)

Written and committed **before** any track-test decision with the new decoder was computed or read. Gap 87 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-07](../../wiki/questions/roadmap-standard.md#p11-07-ctc-beam-search-with-a-character-lm-for-the-emg-decoder). It also feeds gap 37 ([P3-06](../../wiki/questions/roadmap-standard.md#p3-06-logits-guard-inside-the-latency-budget-incremental-decoding), latency). Follow-up of [P11-01](../2026-11-16-p11-01-emg-decoder/results.md), [P11-11](../2026-11-19-p11-11-emg-nonvacuous/results.md) and [P11-12](../2026-11-20-p11-12-emg-nosignal-gate/results.md).

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled and over-user aggregates only: no per-user value, no user pseudonym, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-prompt and per-session files stay in `C:\Users\zhang\bci-data\derived\p11-07\`. The P11-01, P11-09, P11-11 and P11-12 files are read only.

## Problem
- P11-01 decodes greedily with no LM: personalised test CER **15.09 %** (mean over 8 users; pooled 15.15 %). Published (Sivakumar et al. 2024, Table 3, fine-tuned): no LM 11.28 %, 6-gram character LM with beam **6.95 %**.
- P11-11 / P11-12 used the LM only **after** the beam: a no-LM key beam (64, 64-best), then n-best rescoring with the Tatoeba 6-gram and a lexicon. That gave no CER, and the offline decision time grew to p95 402 ms (P11-11; budget 50 ms, gap 37).

## Question
Does a character LM **inside** a causal CTC prefix beam (shallow fusion) lower the test CER of the P11-01 personalised decoders, raw keys and intended text? Can a bounded beam with the LM meet the 50 ms decision budget on CPU? Does the new decoder change the certified P11-12 safe WPM (arm S)?

## What was done before this plan (disclosure)
- Reading of the P11-01, P11-09, P11-11, P11-12 and P11-13 code and results (all numbers above come from their committed pages).
- Decoder code [lmbeam.py](lmbeam.py) written. Two checks on **40 track-val (calibration) prompt windows** of the P11-09 log-probs, no track-test window: (1) with no LM, its top-1 equals the top-1 of `fidetype.lm.beam.IncrementalPrefixBeam` (vector search, beam 32, no top-k cut, prune -8) on 20 / 20 windows; (2) speed: whole-window decode with the LM (w 0.5, bonus 1, prune -8) p50 19-37 ms, p95 28-54 ms for beam 8-64, about 30-60 µs per frame. One top-1 text was printed (a speed check, not a tuning step). No CER was computed.

## Data and splits (as P11-09 / P11-11 / P11-12)
- 8 P11-01 test users. Per user: track-val session (our j = 0) and track-test session (j = 1). `check_track_splits` checks it.
- Log-probs: P11-09 `derived\p11-09\lp\` (CPU forward of the P11-01 personal models, checked against the P11-01 GPU streams; real 98-token sessions, input-level time-shuffled sessions in the 33-class key form, zero-EMG rows). No new forward pass is needed for the CER and safe-WPM parts.
- Labels: P11-01 `derived\p11-01-emg-decoder\sessions\*.lab.npz` (key tokens, key frames, prompt frame spans).
- Prompts: P11-09 `prompts.json` (1,224 calibration prompts in the track-val sessions, 1,221 evaluation prompts = the track-test truth rows). Window = prompt frames + 0.20 s.
- LM: P11-11 `eng_tatoeba_6gram_mkn_noE2Q.npz` (Tatoeba English 6-gram, modified Kneser-Ney, CC BY 2.0 FR; rebuilt **without** the intended texts of all 16 sessions; held-out perplexity 3.158). Licence-clean text, no emg2qwerty prompt of the test sessions.
- Lexicon (optional term only): P11-11 `lexicon.json` (16,875 words typed at least twice in the 927 track-train sessions; CC BY-NC-SA, research only). For the in-beam term, each word is normalised as the LM text (lower case, non-letters to space) and split.

## Decoder (fixed here; [lmbeam.py](lmbeam.py))
CTC prefix beam search over the key vocabulary, causal, streaming (`push` per chunk). The LM scores the **intended text** of a key prefix:
- a letter key (either case) appends its lower-case letter; Space and every other printable non-letter key append a space, and runs of spaces join (the `normalize_text` rule that built the LM);
- Backspace removes the last intended character, and the LM score returns to the value before that character (the deleted key costs only its acoustic score);
- Enter resets the LM context to `<s>` (a new sentence).

Rank score: `logp_acoustic + w * (logp_LM(intended) - lam * n_closed_OOV_words) + beta * n_keys`. At the end: `</s>` term and the open word's lexicon term. Pruning: tokens with `log p >= -8` extend a prefix (fixed); the `B` best prefixes stay.

| Decoder | w | beta | lam | Role |
|---|---|---|---|---|
| G | - | - | - | greedy CTC (P11-01; reproduction check) |
| B0 | 0 | 0 | 0 | beam, no LM |
| **F** | tuned | tuned | 0 | **primary**: LM only (licence-clean text) |
| FL | tuned | tuned | tuned (> 0) | secondary: LM + lexicon term (research-only lexicon) |

## Tuning (track-val only; fixed here)
- **Tuning set T** = the calibration prompts at the first 765 positions of calibrate's order (`default_rng(0).permutation(1224)`, digest `96f175801d6ff225`): the P11-11 tuning part and the P11-12 gate-fit part. The 459 LTT (certify) positions and the evaluation sessions are never used to tune. So the safe-WPM re-run keeps its calibration protocol clean.
- Input: 98-token windows (P11-01 vocabulary). Reference: the P11-01 key tokens with key frame in the prompt span `[lo, hi)`.
- Criterion: pooled raw-key CER over T (total edits / total reference keys). Ties: smaller w, then beta, then lam.
- Grid at B = 32: w in {0.25, 0.5, 0.75, 1.0, 1.5}, beta in {0, 0.5, 1, 2, 3}, lam in {0, 1, 2, 4, 8} (125 configs). **F** = best with lam = 0; **FL** = best with lam > 0.
- **Beam width:** with F's (w, beta), B in {4, 8, 16, 32, 64} on T; the chosen B is the smallest B whose T-CER is at most CER(B = 64) + 0.002. FL and B0 use the same B.

## Test (track-test sessions, run once after tuning)
### Primary: session CER, raw keys (the P11-01 / paper form)
Each of the 8 track-test sessions is streamed whole through each decoder (98 tokens, one hypothesis at the end). CER = Levenshtein(reference key tokens, decoded tokens) / reference length, per session; **mean over the 8 users** (paper form), SD (n - 1), pooled. Decoders: G, B0, F, FL at the chosen B; and F at every B in {4, 8, 16, 32, 64} (frontier, secondary).

### Intended-text CER (`registry.keycodes_to_intended_text`)
- **Per prompt from the session decode:** for each of the 1,221 evaluation prompts, the decoded tokens with emission frame in the window `[lo, end)` -> key codes (`token_key_code`) -> intended text; reference = intended text of the track truth codes. Character Levenshtein / reference length; pooled and mean over users. Also the raw key-code CER of the same prompt pieces.
- **Per prompt window (the guard's view):** each evaluation window decoded alone (33-class key form, as the guard sees it); top-1 intended text vs truth, pooled character CER; also raw key-text CER. Decoders B0, F, FL; reference values: P11-12 post-hoc pooled top-1 intended CER 0.263 (no gate; P11-11 rescoring decoder).

### Controls
- **C0 (reproduction):** decoder G on the P11-09 CPU log-probs gives the P11-01 test CER within 0.1 points (mean over users 15.09 %).
- **C1 (time-shuffled):** decoder F (33-class key form, same weights) on the time-shuffled test sessions; pooled key CER >= 0.90 (P11-01 rule).

### Latency (CPU and GPU)
Measured on the 1,221 evaluation windows (33-class key form, the guard path), one process, 1 thread, isolation class `timing`:
- **offline:** whole-window decode (push all frames, n-best, intended merge), p50 / p95 (compare: P11-11 p95 402 ms with LM rescoring);
- **streaming:** the window arrives in chunks of 4 frames (40 ms). Per-chunk `push` time (p50 / p95 / max; real time needs < 40 ms). **Added decision latency** at the window end = the last chunk's `push` + n-best + intended merge + OOV gate + no-signal gate + `guard.decide` on the ready n-best (arm S guard). p50 / p95, for F and FL at every B in {4, 8, 16, 32, 64}.
- **acoustic model per chunk:** the P11-01 personal model (user index 0 weights), forward of one 4-frame chunk with its receptive-field left context, CPU (4 threads) and GPU (ROCm, RX 7800 XT): p50 / p95 over 500 chunks after warm-up. This is the only GPU step.
- **Gap-37 verdict:** the bounded in-beam LM "meets the 50 ms decision budget on CPU" at a beam B iff p95(added decision latency) + p95(CPU model chunk) <= 50 ms. Reported for every B; the answer for gap 37 uses the chosen B. This is an offline component measurement, not a collector replay.

### Secondary: P11-12 arm S safe WPM with the new decoder
Exactly the P11-12 protocol, with the decoder changed: `decode_fn` = P11-12 no-signal gate (`derived\p11-12\gate.json`, unchanged: k_min 15, r_min 1.842, r_max 17.276) -> decoder **FL** on the 33-class window at the chosen B -> intended texts merged (log-sum-exp of scores), top 20, empty texts dropped -> P11-11 OOV gate (0.5, P11-11 lexicon). `fidetype.trust.calibrate` as P11-12 (alpha 0.05, delta 0.1, LTT, seed 0, `null_trials` 300, the same 300 input-level time-shuffled calibration windows, automatic controls). Decisions on the evaluation prompts: real, time-shuffled, zero EMG. Scoring and verdicts V1-V6: the P11-11 functions (`score_arm`, `verdicts`). Arm **S** (sentence, `p_top1`) is the pre-registered secondary; arm SL (`learned`) is reported too, as in P11-12. Compare with P11-12: S 4.10 [1.99, 6.60], SL 5.08 [2.67, 7.96].

## Hypotheses and verdicts
| Id | Statement | Pass rule |
|---|---|---|
| **H1 (primary)** | The in-beam LM lowers the session raw-key CER | F mean-over-users CER < G, and F < G for at least 7 of 8 users |
| H2 | F reaches the published fine-tuned no-LM level | F mean CER <= 11.28 % (reported against the LM column 6.95 % too) |
| H3 | The lexicon term helps | FL mean CER < F |
| H4 | Intended text improves too | F per-prompt intended CER (session decode) < G |
| **H5 (gap 37)** | A bounded in-beam LM meets 50 ms on CPU | the gap-37 rule above at the chosen B |
| H6 | Arm S stays certified with the new decoder | V1 certified, V2 holds, V3 non-vacuous (v0.1), V6 pass; value reported vs 4.10 (no level predicted) |
| C0, C1 | controls | as above |

## Gap rule
- **Gap 87 closes** when the test CER (mean over 8 users) of F is reported against the Table 3 LM column, with C0 and C1, under this plan (the roadmap done-when). It closes whether or not H1 holds; a null result is stated with numbers.
- Gap 37 gets the H5 numbers (it stays open: no collector replay here).
- New limits become roadmap items and open-gap rows.

## Score cards
Only if arm S or SL is certified, non-vacuous, passes V6, **and** its safe WPM v0.1 is above the current best `intended_text` leaderboard entry (5.08, P11-12 SL): new declared-subset cards by the P11-13 convention, then `python -m fidetype.benchmark.leaderboard --check`. Otherwise no card.

## Order, limits, outputs
1. Commit this plan and [lmbeam.py](lmbeam.py) before any test decode. Then the code (run.py, tests, launch.py).
2. Stages (detached, keep-awake, log `results/run.log`, per-unit files in `derived\p11-07\` so a stop loses minutes only, `DONE` at the end): `tune` -> `beam` -> `test` -> `guards` -> `decide` -> `latency` (CPU, timing class) -> `modellat` (ROCm venv, GPU) -> `score`.
3. No change of split, window, LM, grid, criterion, metric or controls after this commit. Any variant is a new item.

## Amendment 1 (2026-11-19 21:50, before any test decode and before any latency result)
The first `modellat` run did not finish: the ROCm torch build (2.9.1+rocm7.2.1) runs CPU matrix products without a fast BLAS (profile: `aten::mm` 78 ms per call for a 125 x 512 x 1024 product; about 0.7 s per 4-frame chunk forward). That is a property of this torch build, not of the model. Change: the **CPU** model-chunk number of the gap-37 rule now comes from the committed NumPy CRT (`fidetype.pretrained._crt`, the same maths as the P11-01 torch model) in the main venv, isolation class `timing`, 4 threads, 500 chunks; its output on one chunk is checked against the torch output (max probability difference and argmax agreement reported). The ROCm stage keeps the GPU timing (500 chunks) and a 30-chunk torch-CPU reference, which is reported as is. No other change.

Write-up: `results.md` in this folder with the verdicts and numbers as computed, including failures.
