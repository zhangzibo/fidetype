---
title: M4-06 real-data frozen trust config through the streaming layer (B2T '25)
type: experiment
updated: 2026-11-12
---

# M4-06: a frozen trust configuration fitted on real data, replayed through the streaming layer

Task M4-06 (follow-up of M4-03). CPU only. Data: Brain-to-Text '25 copy task (T15, CC0). Code: [run.py](run.py). Settings: [config.json](config.json). Tables: [results/tables.md](results/tables.md). Numbers: `results/*.json`. Log: `results/run.log`.

Run (repo root): `.venv\Scripts\python.exe -I experiments/2026-11-13-m4-06-real-replay/run.py` (stages `fit streams replay uncached rounded controls memory tables`; about 12 min, most of it the fresh-decode stages).

## What we did
1. Fit the Paper 1 frozen recipe (git tag `paper1-v4-frozen-config`, `paper1_v4_harness_config`: guard on, policy grid on fit-A, LTT α = 0.05, δ = 0.1, combine max) on fixed split A: fit-A = alternate fit-half trials per day (411), clean calibration = the other fit-half trials (401). The grid step runs with `pipe.fit(fitA, fitA)`, then `pipe.calibrate_commit(clean_cal)`. This is the procedure of the paper.
2. Froze each pipeline with `FrozenTrustConfig.from_pipeline` and saved it. The two files hold numbers and settings only:
   - [configs/trust-config-b2t25-ours-splitA.json](configs/trust-config-b2t25-ours-splitA.json), `tcfg-f5ca0020b3b8fce2`
   - [configs/trust-config-b2t25-published-splitA.json](configs/trust-config-b2t25-published-splitA.json), `tcfg-ea22af7ec91eea3f`
3. Wrote the 816 test trials as NTS JSON Lines at full precision (float32 values as the shortest float repr, so JSON → float64 → float32 is exact), plus hypothesis streams (the decoder n-best after the frozen frame temperature, with `char_confidences`, FEP-0001). Files are in `C:\Users\zhang\bci-data\derived\m4-06-real-replay\streams` (not in the repo).
4. Replayed them through `StreamingTrustLayer` (one session per day, a new header per trial, `max_attempts = 1` as in the harness, a hash-mode provenance ledger). Routes: frames (with the matching decode_fn: `words_fn` or `published_plus_fn`) and hypothesis.

## Results

### Frozen configs
| decoder | config_id | frame T | grid commit_p | LTT λ̂ (n 401) | final commit_p | paper λ |
|---|---|---|---|---|---|---|
| ours | `tcfg-f5ca0020b3b8fce2` | 3.8151 | 0.3 | 0.00 | **0.3** | 0.3 |
| published gate | `tcfg-ea22af7ec91eea3f` | 3.8151 | 0.7 | 0.76 | **0.76** | 0.76 |

### 1. Equivalence with the batch harness
Fields compared with `==`: action, shown texts, p_top1, guard risk, prediction set.

| input | ours frames | ours hypothesis | published frames | published hypothesis |
|---|---|---|---|---|
| full-precision NTS, cached decode | 816/816 | 816/816 | 816/816 | 816/816 |
| full-precision NTS, fresh decode (ours) | 816/816 | | | |
| benchmark v0.1 NTS files (log-probs rounded to 6 decimals) | 1/816 | | 5/816 | |

**No mismatch on full-precision streams.** The hypothesis n-best survived the JSON round trip exactly (816/816 per decoder).

**Rounded files (cause of the mismatches):** the benchmark files round each log-prob to 6 decimals. Then p_top1 moves by at most 2.0e-8 (ours) / 3.4e-8 (published), and the guard risk by at most 1.9e-9. No action, no shown text and no top text changed (0 of 816), and the test metrics are the same. So the differences are float noise from the input rounding, not a layer error. Exact equality needs the same bytes in.

### 2. Test metrics (816 trials) vs Paper 1 Tab. 3, guaranteed rule, split A
| decoder / route | wrong-commit (n) | commit rate (n) | eWPM | paper |
|---|---|---|---|---|
| ours, frames and hypothesis | 0.0245 (20) | 0.100 (82) | 11.48 | 0.0245 (20) / 0.100 (82) / 11.48 |
| published gate, frames and hypothesis | 0.0294 (24) | 0.403 (329) | 18.65 | 0.0294 (24) / 0.403 (329) / 18.65 |

Paper values: `experiments/2026-11-12-paper1-r4-analyses/v4-derived/results/guard_controls.json` (Tab. 3 prints 0.025 / 0.10 / 11.48 and 0.029 / 0.40 / 18.65). eWPM comes from the harness user simulation driven by the streaming decisions.

### 3. Latency and memory (one CPU process)
| path | p50 | p95 | max |
|---|---|---|---|
| `push(frame)` | 0.014 ms | 0.017 ms | |
| hypothesis route: final hypothesis → decision (trust core + ledger entry) | 0.44 ms | 0.63 ms | 1.0 ms |
| frames route, cached decode (stream build + frame T + cache lookup + trust core + ledger) | 0.70–0.97 ms | 1.07–1.64 ms | 3.0 ms |
| frames route, **fresh decode** (ours: phoneme beam 64 → CMUdict → word LM) | **173 ms** | **992 ms** | 3,229 ms |

- On the frames route the decoder is the latency (p95 about 1 s for our lexicon decoder). The layer itself adds under 1 ms.
- Memory: at most 180 KiB of buffered frames per session (562 frames × 41 × float64). tracemalloc peak over 100 trials: about 1.06 MB (frames route), 37–66 KiB (hypothesis route). Retained after 100 trials: 5–42 KiB. No growth across trials.

### 4. Provenance
For each of the 4 replays: 816/816 decisions carry the frozen `config_id`; 816/816 carry the input hash (frames: `stream_sha256` = `stream_fingerprint` of the trial stream; hypothesis: SHA-256 of the hypothesis event); 816/816 have a ledger decision id. Each ledger (genesis 1, context 1, decision 816) verifies (`verify(...).ok`). The context entry cites the config id. Ledgers are hash-mode (no raw text) and stay in `bci-data\derived`.

### 5. Controls (300-trial draw of the R4 run, streaming path)
| decoder | real | other trial | frame-shuffled | uniform |
|---|---|---|---|---|
| ours: paper / frames / hypothesis | 29 / 29 / 29 | 29 / 29 / 29 | **0 / 0 / 0** | **0 / 0 / 0** |
| published: paper / frames / hypothesis | 115 / 115 / 115 | 0 / 0 / 0 | **0 / 0 / 0** | **0 / 0 / 0** |

Commits out of 300; 0/300 gives a one-sided 95 % upper bound of 0.0099. Every control decision equals the batch decision (300/300 per cell).

## Notes and limits
- **A frozen config is valid only with its decode_fn.** The published-gate config needs `published_plus_fn` (our 10-best plus the published sentence, looked up by `meta.fidetype.trial_index`). On the hypothesis route the producer must apply the frozen frame temperature before it decodes; the layer cannot check this.
- The cached replays use the same decodes as the paper (disk cache copied from `bci-data/cache/paper1-r4`). The fresh-decode run shows that the cache does not hide a difference: 816/816 equal.
- One participant, one split. This is an equivalence and engineering check, not a new safety result.
