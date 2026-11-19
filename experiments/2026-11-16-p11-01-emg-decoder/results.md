---
title: P11-01 continuous EMG-to-text decoder on emg2qwerty - results
type: experiment
task: P11-01
updated: 2026-11-19
---

# P11-01: our own causal CTC decoder on emg2qwerty (results)

Pre-registration: [plan.md](plan.md) (written 2026-11-15, before training). Aggregates: [results/results.json](results/results.json). Raw outputs (weights, per-user values, logs, 2,445 NTS streams) stay local in `C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train\`. They are not committed (see [Licence](#licence)).

Run: 2026-11-17 17:33 to 2026-11-19 00:22, on one RX 7800 XT (ROCm). It was detached and hidden. The trust-reruns queue released the GPU first.

| Stage | Time | Result |
|---|---|---|
| GPU pilot (budget rule) | 17:35-17:38 | `torch` conv 0.364 s/step, `shift` 0.435 s/step -> `torch`. 26 h / 0.364 s > 150,000, so generic steps = **150,000** (the cap) |
| Generic | 2026-11-17 17:38 to 2026-11-18 21:46 (15.6 h of training; paused 12.5 h) | best val CER 0.5457 at step **30,000** of 150,000 |
| Personal (8 users x 3,000 steps) | 21:46-00:14 (about 18 min per user) | best step 2,100-3,000 |
| Eval (test, once) | 00:14-00:19 | see below |
| NTS export | 00:19-00:22 | 2,445 streams, 2,445 pass `trust-ready` |

## Pause and resume check
The orchestrator paused the job with the `pause` file. The log shows a clean resume:

| Check | Log evidence | OK |
|---|---|---|
| Save at pause | `20:20:56 pause/stop file: saved latest.pt at step 26010, exit` | yes |
| Resume point | `2026-11-18 08:53:40 resume at step 26010 (best cer 0.5519 at 20000)` | yes: same step, same best |
| LR schedule | 9.37e-04 at step 26,000 -> 9.36e-04 at step 26,100 | yes: continuous |
| Loss | 1.2988 at step 26,000 -> 1.2939 at step 26,100 | yes: continuous |
| Skipped steps | `skipped 0` on every log line; generic `DONE.json`: `skipped 0` | yes |
| Budget | `budget.json` written once (17:37:58) and read on resume | yes |

The first step time after the resume is 0.449 s (warm-up), then 0.37 s. The unit test `test_resume_is_exact` shows that a resumed run gives the same weights as a run without a stop.

## Verdict (pre-registered criteria)

| Id | Criterion | Pass if | Result | Verdict |
|---|---|---|---|---|
| **S1 (primary)** | Personalised test CER, mean over 8 users, no LM | <= 20.0 % | **15.09 %** (SD 6.54 over users; pooled 15.15 %) | **pass** |
| S1+ (stretch) | same | <= 11.28 % | 15.09 % | **fail** (3.81 points above) |
| S2 | Generic test CER, mean over 8 users, no LM | <= 60.0 % | **53.52 %** (SD 15.31; pooled 53.75 %) | **pass** |
| S3 | Personalised < generic test CER | >= 7 of 8 users | **8 of 8** | **pass** |
| C1 | Time-shuffle control, pooled CER | >= 0.90 | **0.986** | **pass** |
| N1 | Personalised test prompt streams at `trust-ready` | 100 % | **2,445 / 2,445** | **pass** |
| L1 | Real-time form | no lookahead (unit test); median delay reported | no lookahead (`test_model_is_causal_and_chunking_exact`); emission delay median **70 ms**, p90 **110 ms** (n = 64,116 keys) | **pass** |

**Summary:** the primary criterion passes. All other criteria pass, except the stretch target S1+. We did not reach the published fine-tuned no-LM number (11.28 %).

## All numbers (test sessions, greedy CTC, no LM)

| Measure | Generic | Personalised |
|---|---|---|
| CER, pooled over 16 test sessions | 0.5375 | 0.1515 |
| CER, mean over 8 users (paper form) | 0.5352 | 0.1509 |
| SD over 8 users (n - 1) | 0.1531 | 0.0654 |
| Prompt-level CER, pooled | 0.5832 | 0.2148 |
| Reference keys | 71,476 | 71,476 |
| Val CER, pooled (selection set) | 0.5457 | - |
| Time-shuffled control, pooled | - | 0.9863 |

Prompt-level CER is higher than session CER. Each prompt is decoded from its own frames only, so its first keys have less left context. The plan's split table counts 71,769 test key presses. The evaluation counts 71,476 vocabulary keys: modifiers, arrows and non-ASCII keys are dropped (plan, Targets).

Emission delay: from key-down to the first frame whose argmax is the same token, window -0.5 s to +1 s. 64,116 of 71,476 keys (89.7 %) have such a frame. The delay includes the 64-sample window (32 ms) that ends at the frame time.

## Comparison with the published baselines

Published: Sivakumar et al. 2024 (arXiv 2410.20081), **Table 3**, CER in %, mean ± SD over their 8 test users. We checked the numbers against the paper on 2026-11-19. They equal the numbers in [plan.md](plan.md#published-baseline-what-we-compare-against) and on the [emg2qwerty entity page](../../wiki/entities/emg2qwerty.md#continuous-decoder-p11-01-done-2026-11-19). The wiki has no source page for this paper yet (new gap 90).

| Model | Ours, no LM, test | Published, no LM, test | Published, 6-gram char LM, test |
|---|---|---|---|
| Generic (no personalisation) | **53.52 ± 15.31** | 55.38 ± 4.10 | 51.78 ± 4.61 |
| Personalised (random init) | not run | 15.38 ± 5.88 | 9.55 ± 5.16 |
| Personalised (fine-tuned from generic) | **15.09 ± 6.54** | 11.28 ± 4.45 | 6.95 ± 3.61 |

Published val CER (no LM): generic 55.57 ± 4.40, random init 15.65 ± 5.95, fine-tuned 11.39 ± 4.28. With LM: 52.10 ± 5.54, 11.03 ± 4.45, 8.31 ± 3.19. Our generic val CER (pooled) is 54.57.

**The conditions differ. The comparison is indicative, not a replication.**

| Condition | Ours | Published |
|---|---|---|
| Decoding | greedy CTC, **no LM**, no beam search | no LM column = greedy; LM column = 6-gram character LM with beam search |
| Test users and splits | our own rule: 8 users by salted SHA-256, last 2 sessions = test, 2 before = val | the paper's 8 test users and split lists (from their code config, which we did not read) |
| Features | 12 log bands, 100 frames/s (29 % of the bytes) | 33 bins, 125 frames/s |
| Model | own causal ring-TCN, 8.75 M parameters, **no lookahead** | TDS conv, 900 ms past + **100 ms future** |
| Normalisation | fixed global mean / SD | batch norm |
| Compute | 1 GPU, 150,000 steps x batch 64 (best at 30,000) | 8 A10 GPUs, 150 epochs |
| CER unit | keystroke sequence (Backspace kept), as the paper | keystroke sequence |
| SD | sample SD over 8 per-user CERs | SD over 8 users (ddof not stated) |

Points to note:
- Our generic SD (15.31) is much larger than the published SD (4.10). Our test users differ from theirs, so the means are not directly comparable.
- Our personalised CER (15.09 %) is 3.81 points above the published fine-tuned value and close to their random-init value (15.38 %). It has no lookahead, so it is usable for live typing as is.
- The published LM column is 4.33 points (fine-tuned) better than its no-LM column. We have no LM yet (new gap 87).

## Observations (not pre-registered)
- **The generic model overfits early.** Val CER is best at step 30,000 (0.5457). From step 35,000 to 150,000 it stays between 0.5476 and 0.5711, and the training loss keeps going down. So the plan's first fix "a longer generic run" would not help. The schedule, regularisation or features are better levers (new gap 88).
- Personal fine-tuning lowers the mean CER over users by 38.4 points (53.52 % -> 15.09 %), in 3,000 steps (about 18 min per user). It helps every one of the 8 users (S3).
- The time-shuffle control is near 1 (0.986). The decoder uses the time structure of the EMG, not a key-frequency prior.

> **Our take:** a causal EMG decoder with no lookahead and no LM types with about 15 % key errors after 18 minutes of per-user fine-tuning. This is good enough to test the trust layer on a second modality with a useful decoder. A trust config for these streams is the next step (new gap 89). The weights are research only (NC data). A product needs a licence-clean decoder (new gap 86).

## Benchmark entry (emg2qwerty track v0.2)
**No entry added.** The scorer path for this decoder does not exist yet:
1. The track test split is the last session of 104 users. Our generic model trained on all sessions of 100 users, so it saw 96 of the 104 track test sessions. Only a declared-subset entry on our 8 test users is clean.
2. The track scores `KeyboardEvent.code` classes per prompt (`keycodes` normaliser). Our decoder emits 98 ASCII-key tokens. No mapping and no `units.jsonl` writer exist for CTC key streams.
3. A guard for safe WPM needs a trust config fitted on held-out streams of the same users (plan step 3, a follow-up).

This stays in [P14-13](../../wiki/questions/roadmap-standard.md#p14-13-conformant-emg-baselines-without-oracle-key-timing-kt-semg-emg2qwerty) (gap 27, track entry without oracle key times) and [P14-10](../../wiki/questions/roadmap-standard.md#p14-10-safe-wpm-on-the-remaining-tracks-b2t24-t12-willett-hw-kt-semg-emg2qwerty-p11-01) (gap 8, safe WPM). The trust config is new gap 89.

## New gaps
| Gap | Item | What |
|---|---|---|
| 86 | P11-06 | Licence-clean causal ConvCTC on KT-sEMG + Toronto (the other half of P11-01's title) |
| 87 | P11-07 | CTC beam search with a licence-clean character LM for the EMG decoder; compare with Table 3 LM column |
| 88 | P11-08 | Close the gap to the published fine-tuned no-LM CER (11.28 %): generic overfitting, 33 bins at 125 Hz, bounded 100 ms lookahead |
| 89 | P11-09 | Trust config for the P11-01 EMG streams (LTT on personal val streams, commit gate, null controls) and a real-time streaming replay through the collector |
| 90 | P11-10 | Ingest the emg2qwerty paper as a wiki source page |

## Licence
- Data: CC BY-NC-SA 4.0 (stricter of README / LICENSE; [entity page](../../wiki/entities/emg2qwerty.md)). Research use only.
- The plan (Licence and rules) fixes that weights and per-user results stay local. Share-alike makes any shared derived data carry the same licence. So this commit holds **pooled and over-user aggregates only**: no per-user CER, no user pseudonyms, no signals, no weights, no NTS streams. Aggregate scores of a model are facts about our experiment. The [benchmark tracks](../../docs/benchmark-tracks.md) publish emg2qwerty aggregates on the same basis.
- Code: our own, Apache-2.0. We did not read or copy the emg2qwerty code.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q experiments/2026-11-16-p11-01-emg-decoder/test_p11_01.py` |
| Full run | `.venv\Scripts\python.exe experiments\2026-11-16-p11-01-emg-decoder\launch_train.py` (needs the 95.7 GB cache of `launch_prep.py`) |
| Eval / NTS only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments/2026-11-16-p11-01-emg-decoder/train.py eval` (then `nts`); about 8 min on the GPU |
