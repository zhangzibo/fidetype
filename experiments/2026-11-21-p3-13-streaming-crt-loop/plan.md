---
title: P3-13 streaming CRT model in the decision loop - pre-registration
type: experiment
task: P3-13
updated: 2026-11-21
---

# P3-13: streaming CRT model in the decision loop (pre-registration)

Written and committed **before** the counted run. Gap 142 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P3-13](../../wiki/questions/roadmap-standard.md#p3-13-streaming-crt-model-in-the-decision-loop). Follow-up of [P3-12](../2026-11-20-p3-12-emg-latency-budget/results.md).

**RESEARCH ONLY** (emg2qwerty data, CC BY-NC-SA 4.0). The repo gets aggregates only: no per-user value, no text, no id. Per-window files and the exported weights stay in `C:\Users\zhang\bci-data\derived\p3-13\`. The P11-01, P11-07, P11-09, P11-11, P11-12 and P3-12 files are read only. CPU only (the GPU is not used).

## Roadmap text (done when)
"the streaming model output with the per-user weights feeds the guard session and the beam on the 1,221 evaluation windows, and the decisions match those from the batch log-probs, or the differences are counted and the safe WPM v0.1 stays within the P3-12 tolerance (>= 3.32, certified, controls 0)."

## What P3-12 left open
P3-12 decided on the P11-09 batch log-probs (torch CPU, whole-session causal pass, per-user weights). The streaming CRT (`fidetype.pretrained._crt.CRTStream`) ran only as a cost stand-in (u0 weights on every window). Its float32 output differed from the NumPy batch model by up to 3.1e-5 in probability (float64: 3e-15).

## What was done before this plan (disclosure)
1. **Weights export** (`export_params.py`, torch venv, CPU, `map_location="cpu"`; no model run): the 8 P11-01 `personal-u{i}/best.pt` state dicts -> `derived\p3-13\params-u{i}.npz` (78 arrays each) and `params.json` (sha256 of each file).
2. **Probe** (8 evaluation windows, one per 150th, not counted): streaming CRT from `lo - 120` vs the P11-09 log-probs `[lo, end)`: max abs probability diff (98 tokens) 1.8e-6 to 3.7e-5; NumPy batch `_forward` vs P11-09: 1.8e-6 to 3.1e-5; streaming vs NumPy batch: 1.4e-6 to 5.9e-6; argmax agreement 1.0. About 1.1 ms per frame (background class).
3. **Smoke runs** of `run.py` into `derived\p3-13\smoke\` (not counted): `check --smoke 8`: same decisions 24 / 24 (real, shuffled, zeros), max |p_top1 diff| 3.6e-7, max prob diff of the guard rows 2.1e-5; `latency --smoke 8` (background class, 2 threads, not pinned): decision p95 8.7 ms, chunk p95 7.9 ms; `check --smoke 3` after one counter was added (n-best texts): 9 / 9.

## Design (fixed here)
- **Windows:** the same 1,221 evaluation windows as P3-12 (P11-09 prompts, the 8 track-test sessions of the 8 P11-01 test users, one session per user; window `[lo, end)` = prompt frames + 20 tail frames). Input kinds: real, time-shuffled, zero EMG (the P11-09 controls): 3,663 window decisions.
- **Model input per window and kind (path S):** a fresh `CRTStream` with the window's user weights. It first gets the warm-up frames `[max(0, lo - 120), lo)` in 4-frame chunks (outputs dropped; 120 = receptive field 121 - 1, so the outputs from `lo` on have the same maths as the whole-session causal pass). Real: the session's P11-01 feature frames. Shuffled: the same frame indices of the P11-09 time-shuffled session (the P11-09 seed rule: sha256 of `fidetype-p11-09-2026-11-19|shuffle|<session>`). Zeros: the constant zero-EMG feature `log(log_eps)` (P11-09 used the steady-state output row of this input, tiled).
- **Decision loop (path S):** for each 4-frame chunk of `[lo, end)` (the last chunk 1-4 frames, as P3-12): `CRTStream.push` -> `merge_to_key_ctc` (98 tokens -> 33 key-CTC columns) -> `GuardSession.push` -> FL@B8 beam push on the rows that `push` returns; then n-best -> intended merge (20-best) -> P11-12 no-signal gate -> P11-11 OOV gate (`GuardDecoder.post`) -> `session.end()`. Guard: P11-07 arm S (`guard-S.json`, threshold 0.70).
- **Reference (path B):** the same P3-12 pipeline, in the same process, on the batch log-probs (`Windows.get`, P11-09). Path B is also compared with the stored P3-12 decisions (`decisions-stream-S.json`; expected 3,663 / 3,663).

## Rules (fixed here)
| Id | Statement |
|---|---|
| **M1 (decisions match)** | For each of the 3,663 window decisions: path S has the same `action`, `text` and `choices` (top 3) as path B, and `abs(p_top1_S - p_top1_B) <= 1e-3`. M1 holds if 3,663 / 3,663. The tolerance on `p_top1` is there because path S and path B differ in float32 rounding (torch vs NumPy, batch vs stream); exact `p_top1` equality is counted and reported, not required. |
| **M2 (fallback, counted differences)** | If M1 fails: every differing window is counted per kind and per action change; safe WPM v0.1 of path S (P11-11 scorer, arm S sheet, as P3-12) must be **>= 3.32, certified, time-shuffled commits 0, zero-EMG commits 0**. |
| **V1 (primary, gap 142)** | M1 holds, or M2 holds. Gap 142 closes if V1 passes. |
| C2 (secondary) | Max abs probability difference of the 33-column guard rows, path S vs path B, <= 1e-3 per kind (the P11-09 amendment 2 bound for torch CPU vs GPU); log-prob diff and argmax agreement reported. Not a gate for V1. |
| L1 (secondary) | Decision latency D of path S on the real windows (FL@B8): p95 <= 50 ms and per-chunk p95 <= 40 ms. |

Also reported (always): n-best equality (exact scores; texts only), gate agreement, commits per kind, safe WPM v0.1 of both paths, window top-1 intended CER (FL@B8, pooled, no gate) of path S.

## Latency measure (L1, fixed here)
- Isolation runner, class timing, 1 BLAS thread (`python -m fidetype.utils.isolation run --class timing --threads 1 --env-json derived/p3-13/iso-latency.json`), the measurement record saved. 20 warm-up windows first (not counted), then the 1,221 real windows.
- Per chunk: features of 4 new frames (`frames_from_block` on a fixed seeded 124-sample block, as P3-12; the cost does not depend on the values) + the streaming model on the window's own feature frames with its user weights + `merge_to_key_ctc` + `session.push` + beam push.
- **D (per window)** = one `perf_counter` span: the last chunk (features + model + merge + `session.push` + beam push), then n-best + intended merge + gates + `session.end()`. The model warm-up before `lo` is not in any time (a live stream has this state already).
- The driver waits up to 2 h for a quiet machine (no other registered CPU job, load < 25 %). If the record is not clean (foreign load >= 5 %), the stage runs once more; the verdict uses the clean run, or the second run with a note. L1 does not gate gap 142.

## Outputs
- `results/check.json`, `results/results.json`, `results/run.log` (aggregates only). Per-window decisions (both paths), checkpoints and times: `derived\p3-13\` only.
- results.md: every result, failures too.

## Rerun
| Step | Command (repo root) |
|---|---|
| Weights export (torch venv, CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-21-p3-13-streaming-crt-loop/export_params.py` |
| Full run (detached) | `.venv\Scripts\python.exe experiments/2026-11-21-p3-13-streaming-crt-loop/launch.py`; done when `C:\Users\zhang\bci-data\derived\p3-13\DONE` exists; stop: create `...\p3-13\STOP` (check resumes from its checkpoint) |
| Smoke (not counted) | `.venv\Scripts\python.exe -I experiments/2026-11-21-p3-13-streaming-crt-loop/run.py check --smoke 8` |
