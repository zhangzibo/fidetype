# P14-04 / P4-02: one-command live decode — results

Date: 2026-11-16/17. Machine: the project PC (Windows 11, CPU only; other agents' CPU jobs ran at the same time, so the latency numbers are under load). Code: `src/fidetype/live/`. Guide: [docs/live-decode.md](../../docs/live-decode.md). Local outputs (not committed): `C:/Users/zhang/bci-data/derived/p14-04-live/`.

## What was run

| # | Command (shortened) | Source | Model / guard | Result |
|---|---|---|---|---|
| 1 | `fidetype live --source synthetic` | synthetic typist, 16 ch, 250 Hz, real time | `builtin:synthetic-keys` | 10 decisions: 8 commit, 2 offer; NTS trust-ready + provenance PASS |
| 2 | same, 20 seeds x 10 utterances, `--speed 0` (held-out check) | synthetic | builtin | 200 utterances: 126 commits, **6 wrong** (wrong-commit rate 0.030 ≤ α 0.05), 73 offers, 1 withhold |
| 3 | `fidetype live --source synthetic --null --utterances 50` | synthetic, no key bursts | builtin | **0 commits** (6 offer, 44 withhold) |
| 4 | `fidetype live --source brainflow --board-id -1 --duration 20` | BrainFlow 5.24 Synthetic board (16 ch EEG, 250 Hz), fixed timing, 2 s segments | builtin | 10 decisions: **0 commit**, 1 offer, 9 withhold; NTS PASS |
| 5 | `fidetype live replay-synthetic` + `fidetype live --source lsl --stream-name fidetype.replay.synthetic` | real pylsl 1.18 loopback | builtin | 10 decisions: 8 commit, 2 offer (same as #1); NTS PASS |
| 6 | `fidetype live train-kt` | KT-sEMG (CC BY 4.0) | `kt-semg-lda` (local) | model: 12 train runs, 37,703 keys; guard: 173 segments of 4 train + 2 cal runs; null controls PASS (uniform 0/300, shuffled 0/173) |
| 7 | `fidetype live replay-kt --run run28 --speed 3` + `fidetype live --source lsl ...kt-semg-lda...` | KT-sEMG test run run28 over LSL, 32 ch, 2000 Hz, 640.6 s at 3x | `kt-semg-lda` | 22 segments, 786 key windows, 22 decisions: 0 commit, 22 offer (0 offer hits); NTS PASS |

## KT-sEMG demo decoder (honest numbers)

- Offline key accuracy with the live pipeline (causal z-score, oracle onsets): run28 **0.248** (799 keys; majority class 0.138); run26 0.087 (104 keys; majority 0.106). Cross-session transfer is weak.
- Calibration: top-1 exact on 0 of 173 segments (segments have 5 to 100+ keys). The guard calibrates `commit_p` (λ̂ 0.13, policy grid 0.30) but has 0 in-sample commits, so on this decoder it **never commits**. That is the correct behaviour for a decoder this weak. Live run #7: 22 offers, 0 commits (wrong-commit 0/22, CP95 upper 0.154).
- The live path works on a public recording end to end; decoding quality needs a better EMG decoder (P11-01) and live onset detection (gap P4-10).

## Latency (added by Fidetype)

`compute` = CPU time of the step. `added` = wall time from the end of the poll that delivered the last needed sample to the written output (module doc of `fidetype.live.runner`).

| Run | Window compute p50 / p95 (ms) | Window added p50 / p95 (ms) | Decision compute p50 / p95 (ms) | Decision added p50 / p95 (ms) |
|---|---|---|---|---|
| #1 synthetic, real time | 0.218 / 0.312 | 0.243 / 0.347 | 1.53 / 11.52 | 1.59 / 11.60 |
| #4 BrainFlow Synthetic board | 0.199 / 0.290 | 0.333 / 0.474 | 1.23 / 3.03 | 1.36 / 3.20 |
| #5 LSL loopback (synthetic) | 0.199 / 0.276 | 0.220 / 0.312 | 1.32 / 5.15 | 1.36 / 5.20 |
| #7 LSL KT-sEMG, 32 ch at 2000 Hz | 0.213 / 0.300 | 0.653 / 0.863 | 1.96 / 12.03 | 2.46 / 12.78 |

Per window, Fidetype adds well under 1 ms. Per decision (key beam search + trust guard), a few ms; the p95 grows with segment length (KT segments up to 113 keys). The window itself (0.2 s, of which 0.05 s after the onset) and the source delay come on top.

## Quickstart timing (docs followed by this agent)

Sections 2-4 of [docs/live-decode.md](../../docs/live-decode.md), commands as written: section 2 (synthetic, real time) 42.7 s; section 3 (BrainFlow Synthetic board, `--duration 20`) 20.9 s; section 4 (LSL loopback) 43.6 s; plus `fidetype validate` — **107.5 s** in all. Install (section 1) was not re-run: the venv already had `pylsl` and `brainflow`, and `uv sync` with other extras would have changed the shared environment of concurrent agents. Section 5 (KT-sEMG) needs the dataset: training about 13 min CPU, replay of run28 at 3x 3.6 min.

## Tests

`tests/test_live.py`: 17 tests. 15 need no optional package (synthetic end to end with NTS conformance, null input never commits, pacing, collect mode = live, mismatch refusals, fixed timing, BrainFlow path with `FakeBoard` and a fake clock, CLI). 2 use the real BrainFlow Synthetic board and a real pylsl loopback; they skip when the packages are missing. CI: the main job runs the 15; the new job `live` installs `[lsl,brainflow]` and runs all 17. Full suite: 1209 passed, 11 skipped.

## Gaps registered

P4-10 live key-onset detector; P4-11 reconnect in `fidetype live --source lsl`; P14-11 CI LSL replay of a public recording ([open gaps](../../wiki/questions/open-gaps.md)).
