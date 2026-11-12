# G1: trust evaluation on the async M1-09 MEG streams (Paper 1)

Date: 2026-11-11. Tracker: M3-10 (Paper 1 gap G1, also part of G3). CPU only, no GPU job.

**Question.** All MEG trust numbers so far came from the synchronous M1-15 full-r1 decoder (oracle key times). The Paper 1 MEG decoder is the async M1-09 `r4b-full-medium` model (test greedy CER 0.506, beam + LM 0.475; [M1-09 result](../../wiki/questions/m1-09-async-full-result.md)). Do the trust results hold on the async streams? And what are the CIs over sentences and participants?

## Answer
1. **Same picture as sync.** Trust removes all wrong commits (always commit 0.997 → trust 0). Trust is faster than always commit by +0.62 eWPM (CI over sentences [+0.49, +0.75]).
2. **Parity with gaze typing, not a gain.** Trust 3.20 vs gaze only 3.155 eWPM. Paired trust − gaze: +0.05, CI over sentences [−0.04, +0.15], over participants [−0.07, +0.22]. Sync full-r1: trust 3.23, trust − gaze CI over sentences [−0.02, +0.18].
3. **Null audit: trust commits nothing.** On real, shuffled-MEG, zeros-MEG, other-sentence, frame-shuffled and uniform input, trust and trust + OFFER_WORDS commit 0 % (637 trials each). Always commit commits 100 %, and 85–100 % of these commits are fluent Spanish.
4. **CRC / LTT spend the risk budget on useless commits.** The top-1 sentence is right for 2 of 637 test trials. CRC (n_cal 408, 200 splits) gives mean wrong-commit 0.0193, LTT 0.0214, the old gate 0. eWPM 3.199–3.204. The same pattern as sync (M2-13: 0 / 0.0186 / 0.0207).
5. **Online re-calibration:** `aci` 0.0188, `aci_window` 0.0078 wrong-commit, eWPM 3.200–3.201 (offline CRC 0.0204). Bounded, but no gain: every commit is wrong.

> **Our take:** G1 does not change the Paper 1 MEG claim. It makes it cleaner: the async decoder gives the same safety result and the same parity with gaze typing as the sync decoder. On MEG the trust layer shows safety, not speed. The cause is the LM step: the true sentence is in the 10-best for only 1.6 % of trials (sync 0.6 %).

## Setting
| item | value |
|---|---|
| Streams | `C:\Users\zhang\bci-data\streams\m1-09-r4b-full-medium\` (val 437 instances / 11 sentences; test 637 instances / 17 sentences / 19 participants). Not in git |
| Decoding | M2-14 / M1-15 full-r1 settings, unchanged: `RETUNED` prefix beam, `n_best` 10, `lm_weight` 0.5, Spanish Tatoeba 6-gram char LM, frame confidence. Frame temperature fitted on val: 3.30 |
| Fit | All parts on val (frame T, sentence T, conformal, policy grid `BASE_GRID`, max wrong-commit 0.05), report on test. User `UserConfig.aac_gaze()` |
| Policies | always commit LM top-1; trust; trust + OFFER_WORDS; two silent-error-limited variants; OFFER_WORDS always; gaze typing only |
| Null inputs | shuffled MEG and zeros MEG = the M1-09 `infer --control` outputs (`m1-09-r4b-full-medium_beam-controls/logprobs_test.npz`); other sentence = the real stream of another test instance of the same participant with another target; frame-shuffled; near-uniform (jitter 0.05) |
| CRC / LTT | M2-13 protocol: α 0.05, δ 0.1, 200 random cal / test splits, n_cal 100 and 408. New: grouped splits (cal = 11 of 17 sentences, or 12 of 19 participants). One-shot row: calibrate on val, test on all test |
| Online | M2-16 drift protocol: warm start on val, test in file order (participant by participant), feedback delay 0 and 10 |
| Sync row | The same script on the M1-15 full-r1 streams (harness only). It reproduces the old numbers exactly (commit 2.714, trust 3.229) |
| Run time | async 23 min (harness + 6 sensitivity variants 17 min, null audit 6 min, CRC + online < 5 s); sync 5 min |

### CI method (for Paper 1, gap G3)
- Percentile bootstrap, 95 %, B = 2000 (sensitivity runs: B = 300).
- Four resampling units: **trials** (637 instances); **unique sentences** (cluster bootstrap over the 17 test sentences: draw 17 sentences with replacement, keep all their instances); **participants** (cluster bootstrap over the 19 participants); **two-way** (draw sentences and participants independently; instance weight = sentence count × participant count). The two-way CI is the most conservative. It covers both sources of variance.
- eWPM is a ratio (60 × correct words / time), so each bootstrap sample recomputes the ratio from the weighted sums. Paired differences use the same weights for both policies. The gaze-only row uses the same per-instance arrays (time = characters / fallback rate), so "trust − gaze" is paired.
- The gaze-only CI over participants is narrow ([3.15, 3.16]) because all participants type the same 17 sentences. Its CI over sentences ([3.02, 3.29]) shows the sentence-length effect.

## Main result: eWPM harness (test, async vs sync)
eWPM point [95 % CI: trials / sentences / participants / two-way].

| decoder | policy | eWPM | CI trials | CI sentences | CI participants | CI two-way | wrong-commit | silent error | KSR |
|---|---|---|---|---|---|---|---|---|---|
| **async M1-09** | always commit LM top-1 | **2.580** | [2.47, 2.69] | [2.41, 2.76] | [2.41, 2.79] | [2.32, 2.88] | 0.997 | 0.235 | 0.113 |
| | trust | **3.203** | [3.15, 3.26] | [3.07, 3.36] | [3.08, 3.37] | [3.02, 3.43] | **0** | 0 | 0.047 |
| | trust + OFFER_WORDS | 3.202 | [3.15, 3.26] | [3.07, 3.36] | [3.08, 3.37] | [3.02, 3.43] | 0 | 0 | 0.049 |
| | OFFER_WORDS always | 3.097 | [3.05, 3.15] | [2.97, 3.24] | [2.98, 3.26] | [2.92, 3.32] | 0 | 0 | 0.178 |
| sync M1-15 full-r1 | always commit LM top-1 | 2.714 | [2.61, 2.83] | [2.54, 2.90] | [2.54, 2.90] | [2.45, 2.99] | 1.000 | 0.199 | 0.123 |
| | trust | 3.229 | [3.18, 3.28] | [3.08, 3.40] | [3.12, 3.37] | [3.04, 3.46] | 0 | 0 | 0.058 |
| | trust + OFFER_WORDS | 3.229 | [3.18, 3.28] | [3.08, 3.40] | [3.12, 3.37] | [3.04, 3.46] | 0.002 | 0 | 0.058 |
| both | gaze typing only (no BCI) | 3.155 | [3.13, 3.18] | [3.02, 3.29] | [3.15, 3.16] | [3.03, 3.29] | 0 | 0 | 0 |

The two silent-error-limited trust variants equal trust (async 3.203 / 3.202). Action rates (async): always commit COMMIT 1.00; trust OFFER 1.00 (it offers the top-1 on every trial); trust + OFFER_WORDS OFFER 0.99, OFFER_WORDS 0.01.

### Paired eWPM differences
| difference | decoder | trials | sentences | participants | two-way |
|---|---|---|---|---|---|
| trust − commit | async | [+0.53, +0.72] | [+0.49, +0.75] | [+0.52, +0.74] | [+0.45, +0.82] |
| | sync | [+0.42, +0.60] | [+0.39, +0.63] | [+0.41, +0.63] | [+0.35, +0.72] |
| trust − gaze only | async | [−0.00, +0.10] | [−0.04, +0.15] | [−0.07, +0.22] | [−0.11, +0.26] |
| | sync | [+0.03, +0.12] | [−0.02, +0.18] | [−0.04, +0.22] | [−0.07, +0.26] |
| commit − gaze only | async | [−0.68, −0.46] | [−0.76, −0.37] | [−0.75, −0.36] | [−0.85, −0.26] |
| trust + OW − trust | async | [−0.00, +0.00] | [−0.00, +0.00] | [−0.00, +0.00] | [−0.00, +0.00] |

- Point differences: async trust − gaze +0.048; sync +0.074.
- Over trials, sync trust − gaze excludes 0. Over sentences, participants or both, it does not. **Trial-level CIs make sync look like a gain. The sentence-level CIs do not support that.**
- True sentence at rank 1: async 0.31 % (2 / 637), sync 0 %. In the 10-best: async 1.57 %, sync 0.63 %.
- Commit-policy top-1 CER in the harness: async 0.522, sync 0.451. The harness beam (frame T 3.30, `lm_weight` 0.5) is not the M1-09 val-tuned beam (0.475). Async has 5× more frames per sentence (one per 40 ms, not one per key), so the same LM weight acts differently.
- Words (trust, async): 29 % selected from offers, 71 % typed (sync 31 % / 69 %).

### Per participant (async, test eWPM)
Trust is above gaze only for 10 of 19 participants (P06, P07, P08, P09, P15, P16, P19, P22, P24, P25). Best: P15 4.32 vs 3.15, P16 4.13. Worst: P12 2.82, P20 2.84. Sync: 11 of 19. Full table: [tables.md](results/tables.md).

### User-model sensitivity (async, refit per variant)
| variant | commit | trust | trust + OW | gaze only | trust − gaze [CI sentences] | [CI participants] |
|---|---|---|---|---|---|---|
| main (aac_gaze) | 2.58 | 3.20 | 3.20 | 3.15 | [−0.04, +0.15] | [−0.07, +0.22] |
| fallback 40 cpm (FP1, 8.1 WPM) | 4.31 | 5.15 | 5.15 | 6.31 | [−1.29, −1.01] | [−1.31, −0.95] |
| p_miss_unflagged 0 | 3.24 | 3.20 | 3.20 | 3.15 | [−0.04, +0.15] | [−0.08, +0.22] |
| p_miss_unflagged 0.2 | 1.24 | 3.20 | 3.20 | 3.15 | [−0.04, +0.15] | [−0.08, +0.22] |
| slow selection (scan, select, nav × 2) | 2.54 | 3.00 | 2.99 | 3.15 | [−0.23, −0.08] | [−0.26, −0.02] |
| no full retype | 2.54 | 3.18 | 3.18 | 3.15 | [−0.06, +0.13] | [−0.10, +0.21] |
| no typing after ABSTAIN | 2.58 | 3.20 | 3.20 | 3.15 | [−0.04, +0.15] | [−0.08, +0.22] |

- Gaze only is clearly faster with a fast fallback (40 cpm) and with slow selection. Sync showed the same (6.31 vs 5.15; 3.15 vs 2.99).
- Always commit depends strongly on how often the user misses an unflagged error (1.24 to 3.24). Trust does not (3.20 in all three).

## Null-input audit (async, 637 test trials per input)
| input | fluent top-1 | always commit: COMMIT / fluent and committed | trust: COMMIT | trust + OW: COMMIT / OFFER_WORDS | guard-risk AUROC null vs real |
|---|---|---|---|---|---|
| real MEG | 0.848 | 1.000 / 0.848 (wrong 0.997) | 0 | 0 / 0.014 | — |
| shuffled MEG | 0.918 | 1.000 / 0.918 | 0 | 0 / 0.050 | 0.916 |
| zeros MEG | 1.000 | 1.000 / 1.000 | 0 | 0 / 0.496 | 1.000 |
| other sentence (same participant) | 0.854 | 1.000 / 0.854 | 0 | 0 / 0.003 | 0.494 |
| frame-shuffled | 0.892 | 1.000 / 0.892 | 0 | 0 / 0.025 | 0.472 |
| uniform (jitter 0.05) | 1.000 | 1.000 / 1.000 | 0 | 0 / 0.223 | 1.000 |

- "Fluent" = at least 2 words and at least 80 % of the words in the Tatoeba Spanish lexicon (as in M2-10 / M6-06).
- Trust commits nothing on any input, because it commits nothing on real input either. So this audit shows the gate is closed, not that it detects null input.
- The guard risk separates shuffled MEG, zeros and uniform from real input (AUROC 0.92–1.00). It does not separate the real stream of another sentence (0.49) or frame-shuffled frames (0.47). As on B2T and EMG: no stream-only signal can detect a real stream of a different intended sentence.
- Old R7 (M2-10 sync keystroke decoder): fluent commits 83 % / 84 % / 86 % / 100 % (real / shuffled / frame-shuffled / uniform), trust 0 %. Async: 85 % / 92 % / 89 % / 100 %, trust 0 %.
- Trust + OFFER_WORDS shows word choices on 50 % of zeros and 22 % of uniform trials (it never commits them). The user still has to select each word.

## CRC / LTT (M2-13 protocol, async)
Test 637; old gate `commit_p` 0.5; eligible for COMMIT (other rules allow it) 2.4 %; top-1 right 0.31 %.

| protocol | old gate | plug-in | CRC | CRC + tune | LTT | eWPM range |
|---|---|---|---|---|---|---|
| random, n_cal 100 | 0 | 0.0100 | 0.0129 | 0.0099 | 0.0085 | 3.200–3.204 |
| **random, n_cal 408** | **0** | 0.0066 | **0.0193** (p95 0.0306) | 0.0066 | **0.0214** (p95 0.0349) | 3.199–3.204 |
| grouped by sentence (cal 11 of 17) | 0 | 0.0046 | 0.0194 (p95 0.0377) | 0.0046 | 0.0218 (p95 0.0382) | 3.199–3.204 |
| grouped by participant (cal 12 of 19) | 0 | 0.0051 | 0.0201 (p95 0.0390) | 0.0051 | 0.0232 (p95 0.0467) | 3.211–3.216 |
| one shot: cal = val, test = all | 0 | 0 | 0.0204 | 0 | 0.0220 | 3.198–3.203 |
| sync M1-15 full-r1, n_cal 408 (M2-13) | 0 | — | 0.0186 | — | 0.0207 | 3.22–3.23 |

Mean test wrong-commit over 200 splits; ± se ≤ 0.001. Full table with p95, P(> α), commit rate and the never-commit share: [tables.md](results/tables.md).

- All methods stay below α = 0.05 on average. LTT exceeds α in 4 % of participant-grouped splits; CRC in 1 %.
- CRC and LTT commit about 2 % of trials. Almost all these commits are wrong. They cost about 0.005 eWPM. The old gate (fit on val with max wrong-commit 0.05) commits nothing.
- Grouped splits (new calibration sentences or new participants) give the same means as random splits, with wider p95.

## Online re-calibration (M2-16 drift protocol, async)
| method | wrong-commit (delay 0) | delay 10 | max rolling-50 (d0) | commit rate | eWPM | certificate |
|---|---|---|---|---|---|---|
| offline old gate | 0 | — | 0 | 0 | 3.203 | — |
| offline CRC | 0.0204 | — | 0.120 | 0.022 | 3.198 | — |
| offline LTT | 0.0220 | — | 0.140 | 0.024 | 3.198 | — |
| window (200) | 0.0078 | 0.0063 | 0.040 | 0.009 | 3.201 | — |
| decay (0.99) | 0.0204 | 0.0204 | 0.120 | 0.022 | 3.198 | — |
| aci (η 0.05) | 0.0188 | 0.0173 | 0.100 | 0.019 | 3.200 | 0.0468 |
| aci_window | 0.0078 | 0.0063 | 0.040 | 0.009 | 3.201 | 0.0343 |

- All online methods keep the long-run rate below α. The sync M1-15 row in M2-16 (delay 0): offline CRC 0.0220, window 0.0141, decay 0.0188, `aci` 0.0173, `aci_window` 0.0141.
- As in M2-16: MEG is the degenerate case. Every commit is wrong, so the online methods spend part of the budget and gain nothing.

## Limits
- **One decoder seed.** The CIs cover the test sentences and participants, not training variance (gap G2).
- **17 unique test sentences, 11 val sentences.** The sentence-cluster CIs are wide and rest on few clusters. The two-way CI is the honest one for "trust vs gaze".
- **Beam settings not re-tuned for async.** We kept the M2-14 / M1-15 settings for a like-for-like comparison. The harness top-1 CER (0.522) is higher than the M1-09 val-tuned beam (0.475). A better LM step could change eWPM. It would not change the safety result.
- **The null audit is uninformative for trust**: the gate is closed on real input too. The guard AUROC column is the informative part.
- **Simulated user.** eWPM comes from the user model; no live users (gap G14).
- The shuffled / zeros controls are CPU re-runs of the model (in the 10 instances we checked, `real_cpu` differs from the GPU stream by at most 0.12–0.19 in log-probability per frame). The real-input row uses the GPU streams, as all other runs.

## Files
| file | content |
|---|---|
| `run.py`, `config.json` | the script (stages harness, null, items, splits, online; `--streams sync`) and its fixed settings |
| `tables.py` | writes `results/tables.md` from the JSON files |
| `results/harness-async.json`, `results/harness-sync.json` | policies, four bootstraps, paired differences, n-best hit rates, per participant, examples; async also the sensitivity runs |
| `results/null-audit-async.json` | null-input audit |
| `results/items-meg-async.json` | M2-13 per-trial item table (score, both outcomes; derived numbers and texts, no signals) |
| `results/crc-splits-async.json` | CRC / LTT splits |
| `results/online-async.json` | M2-16 drift protocol |
| `results/run-async.log`, `results/run-sync.log` | logs |

## Reproduce
```
.venv\Scripts\python.exe -I experiments/2026-11-11-g1-async-meg-trust/run.py
.venv\Scripts\python.exe -I experiments/2026-11-11-g1-async-meg-trust/run.py --streams sync --stages harness --no-sensitivity
.venv\Scripts\python.exe -X utf8 experiments/2026-11-11-g1-async-meg-trust/tables.py
```
