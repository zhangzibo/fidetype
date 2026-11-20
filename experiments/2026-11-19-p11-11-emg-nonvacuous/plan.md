---
title: P11-11 non-vacuous certified safe WPM for the P11-01 emg2qwerty EMG decoder - pre-registration
type: experiment
task: P11-11
updated: 2026-11-19
---

# P11-11: a non-vacuous certified EMG safe WPM (pre-registration)

Written and committed **before** any decision on an evaluation prompt was computed or read. Gap 102 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-11](../../wiki/questions/roadmap-standard.md#p11-11-non-vacuous-emg-safe-wpm-commit-unit-or-lm). Follow-up of [P11-09](../2026-11-19-p11-09-emg-trust/results.md).

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates only: no per-user value, no user pseudonym, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-11\`. The P11-09 files in `derived\p11-09\` are read only.

CPU only (isolation runner, class `background`, 4 threads). **No GPU.** RAM target under 4 GB.

## Why P11-09 was vacuous, and the levers we pick
P11-09: the certified guard made 0 commits on 1,221 test prompts. A COMMIT had to equal the **whole raw key sequence** of the prompt, with the user's own typing errors and Backspace keys. Top-1 was exactly right on 2 / 1,221.

| Lever | Choice | Reason |
|---|---|---|
| L1 target = **intended text** | yes (primary) | The text that a user wants is the text on the screen at the end of the prompt: the key sequence with each Backspace applied. The roadmap names this target. Decoder errors on keys that the user deleted then do not count. |
| L2 **character LM + word lexicon** (n-best rescoring) | yes (primary) | emg2qwerty prompts are short word lists and phrases (mean 4.1 words). A licence-clean character LM and a word list remove most single-key errors inside words. |
| L3 **word-prefix commits** (proposed v0.2) | yes (secondary arm) | A commit of the first k right words earns k words. This uses the existing `commit_unit="prefix"` (P5-24). |
| L4 incremental beam / latency | no | The latency failure is gap 37 (P3-06). This item has no collector replay. |

### What was done before this plan (disclosure)
A planning probe on **calibration (track-val) prompts only** (all 1,224 of them; no track-test decoder output was read). It used the cached P11-09 decoder outputs.
- Built-in key CTC beam (beam 64, 64-best), then Backspace resolution and a merge of equal texts: top-1 intended text exactly right on 7.4 % of the prompts; raw key sequence exactly right on 0.4 %.
- The same n-best rescored with the Tatoeba 6-gram character LM (weight 0.5 or 1.0): 21.1 % / 21.2 % exactly right; the right text is somewhere in the n-best list on 26.1 %; first word right on 60 %.
- A lexicon penalty (words typed at least twice in the track-train sessions) adds up to 1 point (22.1 %).
- Per user, the exact rate varies a lot (0 to 34 of 153 prompts with no LM).
- The lexicon covers 95.4 % of the calibration truth words.
- Leakage probe (truth texts only, no decoder output): of the 2,399 distinct intended texts of the 16 sessions, 1 is a Tatoeba training sentence, and 67 phrases of 15 or more characters occur inside Tatoeba training sentences. So we rebuild the LM without them (below).
These numbers chose the levers. Because the probe touched all calibration prompts, the run tunes the decoder again by a fixed rule on the **non-certify** part only (below).

## Question
With the intended text as the target and an LM / lexicon n-best rescoring, does a drop-in trust guard on the P11-01 personalised EMG decoder give a **certified, non-vacuous safe WPM v0.1** on the held-out emg2qwerty prompts? Is it above the no-BCI reference?

## Data and splits (as P11-09, unchanged)
- Users: the 8 P11-01 test users. Per user, the first test session is the emg2qwerty track **val** session (**calibration**) and the second is the track **test** session (**evaluation**). The code checks this (`check_track_splits`).
- Prompts: the P11-09 prompt list `derived\p11-09\prompts.json` (track rule: at least 3 in-vocabulary keys; 1,224 calibration, 1,221 evaluation; test prompts equal the track truth rows). Decision window: prompt frames + 20 frames (0.20 s), as P11-09.
- Decoder outputs: the P11-09 CPU log-probs `derived\p11-09\lp\` (real, time-shuffled, zero EMG), merged to the 33-column key CTC form (`merge_to_key_ctc`). Nothing is refitted.
- The run logs a 16-hex digest of each unit list. They must equal the P11-09 digests.

## Targets
- **Intended text** `resolve(keys)`: walk the key sequence; a letter, `.`, `,` or `'` appends its character; `Space` appends a space; `Backspace` removes the last character (if any); `Enter` is ignored. Then join runs of spaces and strip the ends. Truth = `resolve(track truth keys)`. Words = the space-separated words of this text.
- **Track keys** (arm K only): the raw key text as in P11-09 (`codes_to_key_text`).

## Decoder side (fixed here)
1. **Beam:** `IncrementalPrefixBeam(key_ctc_vocab(), blank 0, lm=None, beam=64, n_best=64, prune_topk=None, align=False, search="vector")` on the window (log-probs as given by the guard).
2. **Resolve and merge:** each hypothesis -> its intended text; equal texts are merged (log-sum-exp of the acoustic log-probs).
3. **Rescore:** `score(t) = acoustic(t) + w * LM(t) - c * n_oov(t)`. `LM` = the natural-log probability of the normalised text with the end marker (`CharNgramLM.score_sentence`). `n_oov` = number of words of t not in the lexicon.
4. **Output:** the 20 best texts with their scores (an n-best list for the guard, `decode_fn`).
5. **Arm K:** the same beam; the n-best items are the raw key texts, each scored with `acoustic + w * LM(resolve) - c * n_oov(resolve)`, the 20 best.

**LM (rebuilt, leak-free):** the `build_lms.py` English recipe (Tatoeba export of 2026-11-08, seed 20261108, 5,000 held out, first 600,000 training sentences, order 6, modified KN), with a larger blocklist: the 2,000 `corpus.py` sentences as before, plus every normalised intended text of the 16 sessions (calibration and evaluation), removed by exact match, and every corpus sentence that contains such a text of 15 or more characters, or is contained in one. File `derived\p11-11\eng_tatoeba_6gram_mkn_noE2Q.npz` (outside the repo). Licence of the text: CC BY 2.0 FR (Tatoeba).

**Lexicon:** the words of the intended texts of all prompts of the **track-train** sessions (927 sessions; the 16 val / test sessions of our users and all other val / test sessions excluded), kept if typed at least twice. Built from the P11-01 key labels (`derived\p11-01-emg-decoder\sessions\*.lab.npz`). Research only (derived from CC BY-NC-SA data); it stays local.

**Tuning rule (fixed here):** `calibrate` orders the 1,224 calibration prompts by `numpy.random.default_rng(0).permutation(1224)`; the first 306 are its fit part, the next 459 its policy grid, the last 459 its LTT (certify) part. We choose `(w, c)` on the **first 765** (fit + policy grid) only: grid w in {0.25, 0.5, 0.75, 1.0, 1.5}, c in {0, 1, 2, 4, 8}; criterion = share of prompts whose top-1 intended text is exactly right; ties -> smaller w, then smaller c. The LTT part is never used to choose anything. Arm K uses the same `(w, c)`.

## Guards (per arm)
`fidetype.trust.calibrate` on the 1,224 calibration prompts, input kind `logits` (key CTC log-probs) with `decode_fn` = the decoder above, vocabulary `key_ctc_vocab()`, alpha **0.05**, delta **0.1**, method LTT, seed 0, `null_trials` 300, default commit gate. Controls: the automatic uniform and frame-shuffled controls (300 each), plus `null_inputs` = 300 input-level **time-shuffled** calibration windows (the P11-09 draw: `default_rng(0).choice(1224, 300, replace=False)`). A control passes iff commits <= floor(0.05 n) = 15. A refused arm (`NullControlError`) has no guard and no result.

| Arm | Target | Commit unit | `confidence` | Role |
|---|---|---|---|---|
| **S** | intended text | sentence | `p_top1` (default) | **primary** |
| SL | intended text | sentence | `learned` (P5-23) | secondary |
| X | intended text | word prefix (`commit_unit="prefix"`) | `learned` | secondary (proposed v0.2) |
| K | track keys | sentence | `p_top1` | secondary: track-conformant; card only if certified and non-vacuous |

The guarantee (each arm): with probability >= 0.9 over the calibration draw, wrong COMMITs / all prompts <= 0.05 (marginal, pooled over the 8 users; exchangeable val / test sessions). For X a wrong commit is a wrong prefix or a wrong complete commit (P5-24 risk).

## Outcomes

### Primary: safe WPM v0.1 of arm S
`safe_wpm(...)` (ADOPTED v0.1 rules, unchanged) on the 1,221 evaluation prompts. A commit is right iff its text equals the intended truth exactly (after joining spaces). `n_words`, `n_chars` = the intended truth. Timing: the track's measured per-prompt time (first to last key-down; the truth `neural_s`). Correction: the default rule (2 s + 0.79 s per character). CI: percentile cluster bootstrap over users (B 2000, seed 0, 8 clusters). Guarantee and calibrate controls from the guard sheet.

### No-BCI reference
`no_bci_wpm` of the same call: gaze typing of every **intended** text at 20 characters per minute (the reference on the same target and trials). We also give the P11-09 reference on the raw key texts (2.93); the intended texts are shorter, so their reference is higher (stricter).

### Verdicts (arm S unless named)
| Id | Verdict | Rule |
|---|---|---|
| **V1 guard** | certified / refused | `calibrate` returns a guard (all controls pass) with `feasible` true |
| **V2 safety** | holds / fails / clear violation | wrong commits / evaluation prompts <= 0.05 -> holds; CP95 lower bound > 0.05 -> clear violation |
| **V3 value** | non-vacuous / vacuous | status `certified` with at least one commit and value > 0 |
| **V4 vs no-BCI** | above / below / clearly above | value > no-BCI of the same trials (intended text) -> above; CI lower end > it -> clearly above. Also reported against 2.93 |
| **V6 controls** | pass / fail | the calibrate controls pass, and on the evaluation prompts the input-level time-shuffled and zero-EMG inputs give commit rates <= 0.05 each |
| V2/V3-SL, -X, -K | as V2 / V3 | arms SL, X (v0.2 status), K (track keys) |

### Hypotheses
- **H1** (main): V1 certified, V2 holds, V3 non-vacuous for arm S.
- **H2**: arm S is above the no-BCI reference of its target (uncertain; no prediction of the level).
- **H3**: arm X has a larger proposed-v0.2 value than arm S's v0.1 value.
- **H4**: arm K (raw keys) stays vacuous or nearly so (at most 1 % of prompts committed).

### Secondary (reported, not decided)
1. Proposed `safe-wpm/0.2` (not adopted) of arms S, SL, X: (a) plain, (b) with the P14-28 `aac-gaze-v1` reading cost 0.5 s per commit + 0.3 s per committed word. For X: v0.2 with `committed_words`, `complete` and `penalty_chars` from `prefix_outcome`; also v0.1 "complete-only" (prefix commits become no commit), as P5-24.
2. Per arm: commits, wrong commits with CP95, error among commits, commit rate, top-1 exact rate (intended text and raw keys), LTT threshold, chosen `(w, c)` and its tuning-part exact rate, decision time per prompt (offline), the always-commit reference (no bound).
3. LM rebuild: sentences removed, held-out perplexity. Lexicon: size, coverage of the evaluation truth words (reported, never used to choose).

## Score card
The track target is the raw key sequence. Arms S, SL and X change the target, so they are **not** track entries and get no card. Arm K is track-conformant: if K is certified and non-vacuous, we add a declared-subset card `emg2qwerty__p11-11-crt-lm-subset8__guard` with a rerun recipe (P11-09 convention), then `python -m fidetype.benchmark.leaderboard` and `--check`. If K is vacuous, the P11-09 cards already state the vacuous track result and we add none.

## Gap rule
Gap 102 closes iff arm S gives a certified, non-vacuous v0.1 value (V1 + V3), with V6 pass, or (fallback path the roadmap allows) arm X gives a certified, non-vacuous proposed-v0.2 value. Results state which path. If neither, the result states with numbers why it stays vacuous, and gap 102 stays open with the reason. Every new limit becomes a new roadmap item and open-gap entry.

## Order, limits, outputs
1. Commit this plan before any decision on evaluation prompts. Then the code ([run.py](run.py), tests) with a pytest.
2. Stages (detached through the isolation runner, resumable; each finished stage is a file in `derived\p11-11\`; a `DONE` file marks the end): `lm` (rebuild), `lexicon`, `nbest` (beam n-best of all windows, cached by window), `tune`, `guards`, `decide` (real, shuffled, zeros), `score`.
3. No change of split, window, decoder, grid, rule, metric or controls after this commit. Any variant is a new item.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including a failure.
