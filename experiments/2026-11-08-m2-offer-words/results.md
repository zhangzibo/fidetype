---
title: OFFER_WORDS (per-word choices) and partial correction
type: experiment
updated: 2026-11-08
---

# OFFER_WORDS: per-word choices and partial correction in the trust layer

The beam re-tune showed that per-word alternatives reach the truth more often than whole sentences ([beam-retune](../2026-11-08-beam-retune/results.md), "Per-word alternatives"). The simulated user could not choose words, so the harness could not measure this. This experiment adds a per-word action and a word-level user model, then measures them on the simulator and on real MEG.

- Code: `src/fidetype/trust/policy.py` (action `OFFER_WORDS`, `WordSlotInfo`, `highlight_slots`, `OFFER_WORDS_GRID`, `fit_thresholds(word_grid=, max_silent_error=)`), `src/fidetype/interact/simulated_user.py` (word model, `UserConfig.aac_gaze()`), `src/fidetype/eval/harness.py` (word slots, fit), `src/fidetype/eval/ewpm.py` (new metrics). Tests: `tests/test_trust_offer_words.py` (24 tests).
- Script: `run.py` (`--part sim`, `--part real`, `--part tables`). Raw numbers: `results/sim.json`, `results/real.json`. Logs: `results/*_log.txt`. All tables: [results/tables.md](results/tables.md).

**Main finding:** On the simulator, OFFER_WORDS gives +0.4 to +1.7 eWPM over the trust policy without it at the worst preset (paired CIs exclude 0; it replaces most sentence OFFERs), and no change at the median preset. On real MEG, the policy fit never selects it (0 of 209 trials): the decoder gets 10 % of the words right, and the true word is among the 3 alternatives of a wrong slot only 7 % of the time. Forcing OFFER_WORDS on every trial is slower than the trust policy (2.86 vs 2.96 eWPM). **All BCI policies on real MEG are below typing with the gaze keyboard alone (3.14 eWPM).**

## What changed

| Part | Change | Default |
|---|---|---|
| Policy | New action `OFFER_WORDS`: show the top-1 sentence; highlight each slot with confidence < `word_conf_threshold`; show its `offer_words_k` best alternatives. Rule 4, after OFFER and before ASK / final fallback. Gate: mean slot confidence ≥ `offer_words_min_conf`, optional `offer_words_max_slots`. | `offer_words=False`: the policy never reads the slots. |
| Slot confidence | Mass of the top-1 word in its own slot of `word_alternatives` (calibrated sentence posteriors). | — |
| Fit | `fit_thresholds(..., word_grid=OFFER_WORDS_GRID)` adds `word_conf_threshold` × `offer_words_min_conf` (7 × 5); optional `max_silent_error` limit. | Both `None`: same search as before. |
| User | Word model (`partial_correction=True`): fix wrong words one by one with a fallback method; select from alternatives; miss unhighlighted wrong words with `p_miss_unflagged`; retype the sentence if that is cheaper; type an abstained sentence (`fallback_after_abstain`). | `UserConfig()` is unchanged (sentence model). |
| Metrics | `system_word_accuracy`, `keystrokes_saved` (KSR), `share_words_system/selected/typed`, `rate_offer_words`. | Added keys only. |

**Backward compatibility (checked).** A harness snapshot (trust fit + always-commit, worst preset, 30/30/30 items) before and after the change has identical records and metrics; only the new keys are added. The 178 old tests pass unchanged. The reference rows below reproduce the beam-retune trust table exactly.

### OFFER_WORDS and wrong commits
The system asserts the words it does not highlight. So an OFFER_WORDS sentence counts as a **wrong commit** if an unhighlighted word is wrong, and as a **silent error** if the user misses that word. This keeps the 0.05 wrong-commit limit meaningful for the new action.

## User model (word model, `UserConfig.aac_gaze()`)

| Parameter | Value | Source |
|---|---|---|
| Fallback typing | 20 chars/min | Cai et al. 2024 (SpeakFaster): gaze user LP1, Tobii keyboard baseline, 4.05 / 4.37 WPM (× 5 chars). Field user FP1: 8.1 WPM (sensitivity row "40 cpm"). |
| Scan + select one word slot, k = 3 | 1.0 + 1.0 · log2(4) + 1.5 = 4.5 s | Cai et al. 2024: 4.7 s (unscripted) and 7.0 s (scripted) to select a FillMask single-word option. Only the sum is matched; the split is an assumption. |
| One gaze selection (`word_select_s`) | 1.5 s | Assumption. |
| Navigate to an unhighlighted word | 3.0 s, 2 keystrokes | Assumption, after the FillMask flow (click the phrase, then the word chip). Editing keystrokes are class F in Soukoreff & MacKenzie 2003. |
| Miss a wrong unhighlighted word | 0.05 per word | Assumption. A missed error is a "not corrected error" (Soukoreff & MacKenzie 2003). No measured AAC value. |
| Retype overhead | 1.5 s, 1 keystroke | Assumption. |
| Sentence-OFFER read + select | unchanged (0.5 s + 0.3 s/word per candidate; 1.0 + 0.5 · log2(k+1)) | Check: 5 options of 7 words ≈ 15 s; Cai et al. 2024 measured 12.7 s / 21.2 s for 5 phrase options. |
| Neural input | 152 chars/min | Unchanged (Brain2Qwerty v1). |

KSR = 1 − fallback keystrokes / characters of the target (Cai et al. 2024 use the same ratio). The neural input is not a keystroke.

## (a) Simulator

Set-up as the beam-retune trust part: template sentences, RETUNED beam (n_best 10) + 6-gram LM, frame calibration, 120 / 120 / 120, M2 seeds, one repeat. Policy fit: max eWPM with wrong-commit ≤ 0.05 on val, base grid of 224 configs (× 35 with OFFER_WORDS). Test, eWPM [item-bootstrap 95 % CI]:

| condition | always commit | trust | trust + OFFER_WORDS | OW − trust (paired CI) | OW rate | gaze only |
|---|---|---|---|---|---|---|
| median/T=0.5 | 24.55 (wc 0.100) | 24.45 (wc 0.067) | 24.41 (wc 0.067) | [−0.16, 0.05] | 0.10 | 4.10 |
| median/T=1.0 | 24.44 (wc 0.100) | 24.48 (wc 0.033) | 24.84 (wc 0.042) | [−0.07, 0.85] | 0.14 | 4.10 |
| worst/T=0.5 | 21.04 (wc 0.250) | 19.49 (wc 0.050) | **20.45** (wc 0.058) | **[0.36, 1.57]** | 0.63 | 4.10 |
| worst/T=1.0 | 19.95 (wc 0.333) | 19.40 (wc 0.025) | **20.46** (wc 0.042) | **[0.40, 1.74]** | 0.73 | 4.10 |

wc = wrong-commit rate. Silent-error rates are 0.000–0.008 for both trust policies and 0.000–0.025 for always commit.

- At the worst preset, OFFER_WORDS replaces most sentence OFFERs (OFFER rate 0.49–0.60 → 0.00–0.03). It closes the gap to always commit (OW − commit CIs include 0) at 6–8× fewer wrong commits.
- At the median preset, 86–90 % of sentences are committed, so OFFER_WORDS has little to replace.
- Highlighting is precise enough: 1.0–1.3 slots per OFFER_WORDS sentence; 26–42 % of highlighted slots are wrong, and the truth is among the 3 alternatives in 76–100 % of the wrong highlighted slots.
- **OFFER_WORDS for every sentence with all slots highlighted halves eWPM** (12.2–12.7). Scanning every word costs more than it saves. The highlight threshold is necessary.
- The word-model user makes always commit much faster than before at T = 0.5 (24.55 vs 17.17 with the old user): the word model corrects a wrong commit word by word, and the old model charged a full edit. So the eWPM cost of the trust policy against always commit depends on the correction model.
- The silent-error-limited fit (diagnostic rows in tables.md) gives the same picture.

## (b) Real MEG

Set-up as M2-10 ([m2-real-keystroke](../2026-11-08-m2-real-keystroke/results.md)): synchronous keystroke decoder with oracle key timing, overt typing, RETUNED beam with lm_weight 0.5, Spanish 6-gram LM, fit on val (114 trials, 11 sentences), test 209 trials, 17 sentences. User `aac_gaze()`.

| policy | eWPM [trial CI] {sentence CI} | wrong-commit | silent error | KSR | COMMIT / OFFER / OFFER_WORDS |
|---|---|---|---|---|---|
| always commit LM top-1 | 2.31 [2.12, 2.49] {2.12, 2.51} | 1.000 | 0.254 | 0.02 | 1.00 / 0 / 0 |
| trust, no OFFER_WORDS | 2.96 [2.90, 3.02] {2.81, 3.12} | 0.000 | 0.000 | −0.04 | 0 / 1.00 / 0 |
| trust + OFFER_WORDS | 2.96 (identical) | 0.000 | 0.000 | −0.04 | 0 / 1.00 / 0 |
| diag: OFFER_WORDS always, all slots | 2.86 [2.81, 2.91] {2.73, 3.00} | 0.000 | 0.000 | 0.09 | 0 / 0 / 1.00 |
| gaze typing only (no BCI) | 3.14 | 0 | 0 | 0.00 | — |

- System word accuracy is 0.10. A sentence has 6.5 wrong slots on average. For the forced OFFER_WORDS row, 80 % of highlighted slots are wrong, but the truth is among the 3 alternatives in only 7 % of them. The alternatives are wrong words too (as M2-10 found: top-3 per slot 0.291 vs top-1 0.264).
- The fit picks a gate (`offer_words_min_conf` 0.9) that never opens. It falls back to the old trust policy: OFFER the top-1, and the user retypes or fixes it. This is the right choice for this decoder.
- Trust − commit: +0.65 eWPM, sentence CI [0.51, 0.79]; silent error −0.25 [−0.31, −0.20]. With word-level correction, always commit lets 25 % of sentences through with a missed wrong word.
- **No policy beats gaze typing alone** (3.14 eWPM). The users would be faster without the BCI. KSR is near 0: the users type about as many fallback characters as the sentence has.

### User-model sensitivity (real; every policy refitted)

| variant | commit | trust | trust + OW | OW rate | gaze only |
|---|---|---|---|---|---|
| fallback 40 cpm (FP1) | 4.16 | 4.91 | 4.91 | 0 | 6.29 |
| p_miss_unflagged 0 | 3.00 | 2.96 | 2.96 | 0 | 3.14 |
| p_miss_unflagged 0.2 | 0.96 (silent 0.73) | 2.96 | 2.96 | 0 | 3.14 |
| slow selection (× 2) | 2.43 | 2.78 | 2.78 | 0 | 3.14 |
| no full retype | 2.28 | 2.93 | 2.93 | 0 | 3.14 |
| no typing after ABSTAIN | 2.31 | 2.96 | 2.96 | 0 | 3.14 |

- OFFER_WORDS is never selected in any variant. Gaze-only stays the fastest in every variant.
- The trust advantage over always commit comes from silent errors. If the user never misses a wrong word (p_miss 0), always commit is level with trust (3.00 vs 2.96). If the user misses 1 in 5, always commit loses 3× speed and 73 % of sentences carry an error.

> **Our take:** OFFER_WORDS is a useful action when the decoder is close: most words right, a few uncertain words, and the right word among the alternatives. The simulator worst preset (system word accuracy 0.96–0.97) is that regime; real MEG (0.10) is not. The action does not rescue a weak decoder, and the fit correctly refuses it. The more important real-data result is the comparison with gaze typing: at key accuracy 0.39, the BCI costs the user time. For Paper 1, report eWPM against a no-BCI fallback baseline, not only against other BCI policies.

## Limits

- The word-model time values are partly assumptions. Only the per-slot sum (4.5 s) and the fallback rate (20 chars/min) are matched to Cai et al. 2024; LP1 and FP1 are two ALS gaze users with an LLM UI, not BCI users.
- The neural input rate (152 chars/min, overt typing) and the gaze fallback rate come from different user groups.
- `p_miss_unflagged` has no measurement. The real-MEG ranking of commit vs trust depends on it (sensitivity table).
- Real MEG: 17 test and 11 val sentences, oracle key timing, overt typing, calibration and policy fitted on the same val trials (as in M2-10).
- Simulator: one seed per condition, 120 test sentences; the M2 template LM is in-domain.
- The user model is rational: it retypes when that is cheaper, and it knows the cost after reading.
- The base grid is smaller than `DEFAULT_GRID` (224 vs 3960 configs) to keep the OFFER_WORDS product fast. The reference rows with the full grid and the old user reproduce the beam-retune values exactly.

## Reproduce

```bash
export PATH="$HOME/.local/bin:$PATH"
uv run python experiments/2026-11-08-m2-offer-words/run.py --part real   # about 6 min
uv run python experiments/2026-11-08-m2-offer-words/run.py --part sim    # about 15 min
uv run python experiments/2026-11-08-m2-offer-words/run.py --part tables
```

The real part reads the M2-10 streams in `C:\Users\zhang\bci-data\streams\keystroke-sync-2026-11-08` and the Spanish LM in `C:\Users\zhang\bci-data\lm`.
