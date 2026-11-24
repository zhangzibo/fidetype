# P15-49 E2 self-teaching on T15: how to run it

The pre-registration is [plan.md](plan.md) (commit `29c1dc9`, frozen). [amendment-1.md](amendment-1.md) (2026-11-24, before any GPU run) records the six points where the plan is ambiguous or defective and the wrapper's choices. This folder adds the run wrapper (roadmap P15-52, gap 212, E2 part). No result exists yet.

| file | what it does |
|---|---|
| `e2.py` | the runner: base decoder, start guard, S8 grid, commit gate, 20 replay runs, rules P1-P5, outcome |
| `config.json` | the plan values in one place, plus the choices that the plan does not fix (keys that end in `_choice`) |
| `launch.py` | starts `e2.py all` detached, with no visible window |
| `test_e2.py` | CPU tests (no data, no GPU) |

## What the runner calls unchanged
- The M4-13 trainer (`../2026-11-15-m4-13-long-train/train.py`, `t15.py`). For the base decoder, the wrapper sets only the run folder, a run entry, `--steps 30000` and a `load_part` that keeps S0-S7. The fits use the M4-13 `collate` (augmentation), `micro_chunks`, `patch_model` (input dropout) and the CTC loss.
- `fidetype.trust`: `calibrate`, `GuardedUpdateLoop`, `TrustGuardUpdater`, `FeedbackUser`, `ProvenanceLedger`. The wrapper does not re-implement the gate.
- The P14-03 / P15-05 T15 word route (`common.word_decoder` + `make_decode_fn`).

## Stages
```
base (30,000 steps, about 10.6 h) -> base stop check (S0-S7 val PER > 0.30: outcome N, stop)
  -> start guard (calibrate on S8) -> grid on S8 -> results/grid.json
  -> gate: wait until results/grid.json is committed and on origin/main (exit code 4)
  -> 20 replay runs in plan order (GPU cap 90 h, checked before each part)
  -> summary.json + results/results.json (aggregates only, no text)
```
All outputs go to `C:\Users\zhang\bci-data\derived\p15-49` (plan.md names `derived/e2-t15`; the task brief names `p15-49`; this is a path change only). The runner refuses any other folder under `derived`. Per-item records, ledgers and checkpoints stay there. They contain sentence texts, so never commit them.

## Commands (PowerShell, from the repo root)
Launch (hidden window, detached; it resumes if a checkpoint exists):
```powershell
C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-e2-self-teaching-t15\launch.py
```
Check:
```powershell
Get-Content C:\Users\zhang\bci-data\derived\p15-49\run.log -Tail 20
Get-Process -Id (Get-Content C:\Users\zhang\bci-data\derived\p15-49\run.pid) -ErrorAction SilentlyContinue
Get-Content C:\Users\zhang\bci-data\derived\p15-49\base\m4-13-p15-49-base\train.log -Tail 3   # during the base stage
Get-Content C:\Users\zhang\bci-data\derived\p15-49\gpu_clock.json
```
Stop (clean: the job stops at the next safe point and exits with code 3):
```powershell
New-Item -ItemType File C:\Users\zhang\bci-data\derived\p15-49\stop
```
Hard stop (only if the clean stop does not end the process): `Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\derived\p15-49\run.pid)`. This loses at most 4 min of the base stage or the current replay session (3-15 min).

Resume:
```powershell
Remove-Item C:\Users\zhang\bci-data\derived\p15-49\stop
C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-e2-self-teaching-t15\launch.py
```
After the grid (exit code 4 in `run.log`: "the replay waits"): commit and push `results/grid.json`, then launch again.

Status files in the output folder: `DONE` (finished, cap reached, or base stop), `FAILED` (error text; the launcher renames it to `FAILED.prev`), `run.pid`, `run.out` (stdout).

## Checkpoints and resume
| part | checkpoint | resume |
|---|---|---|
| base | `latest.pt` every 4 min (train.py), exact step and RNG position | `train.py --resume` |
| start guard, grid | written once; a finished part is skipped | the part runs again from its start |
| replay run | after every session: model deltas, the loop state, both guards (`TrustGuard.save`), a copy of the ledger | the ledger is restored to the checkpoint copy, then the next session runs |

The dry run proves that a run stopped after one session and resumed gives the same records as a run without a stop.

## Choices not fixed by the plan (made before any run)
| item | choice | why |
|---|---|---|
| challenger of session d when a nightly version exists | update 1 starts from the nightly version of d - 1 (its day layer d - 1 copied to d); one challenger per session | plan.md step 7 makes the nightly version "the challenger of session d + 1 at its phase B", and step 3 makes the update-1 fit "the challenger"; one gate per check block keeps the error level of the test |
| candidate guard of a proposal | a copy of the start guard; `TrustGuardUpdater` raises `commit_p` to the session threshold on accept | the check block calibrates; a candidate made from a copy of the live guard would only ever raise `commit_p` |
| ACI start value `lambda_1` | `commit_p` of the start guard | "choose ... the start guard" on S8 |
| offer list | the top-1 text, then the word n-best in order, distinct, 5 at most | plan.md: offer = top 5. The guard itself shows 1 choice (`offer_max_k` 1) |
| fit optimiser | AdamW with torch defaults (eps 1e-8), constant LR, new optimiser per fit, M4-13 weight-decay groups, clip 10, batch 32 | plan.md: "the M4-13 CTC step ... with AdamW"; the M4-13 eps 0.1 makes LR 1e-4 steps almost zero |
| nightly LR | the chosen update-1 LR | plan.md has one LR grid only |
| nightly labels | the arm's labels of S9 .. d, all phases; no base-session labels | "all labels of sessions <= d that the arm may use" |
| SH permutation | update 1: inside the phase-A label set; nightly: a new permutation of the whole label pool each night | "permuted at random inside each training set" |
| grid | each LR runs once on S8; both step cells get its result | the nightly fit comes after phase C, so it cannot change the S8 phase-C WER (see below) |
| GPU clock | wall time of the job | the job blocks the GPU while it runs, also while the CPU decodes |

## Points in the plan to note (not changed; on record in [amendment-1.md](amendment-1.md))
1. **The grid cannot choose the nightly steps.** The rule uses the S8 phase-C WER, and the nightly fit runs after phase C. The two step values always tie, and the tie rule picks 150 steps. The plan's default of 300 steps is therefore never used.
2. **The nightly LR is not given.** The wrapper uses the update-1 LR.
3. **"From the champion" vs "the nightly version becomes the challenger".** See the first row of the table above.
4. **Stage 2 (T12) is not wired.** The plan starts it only after the T15 U1 runs and only if the cap leaves 8 h. It needs a wrapper for the T12 v2 recipe.
5. eWPM and safe WPM v0.2 (descriptive) are not computed by the runner. The per-item records keep what they need (action, right / wrong, texts, bins).

## Estimated time on the local RX 7800 XT
| part | estimate |
|---|---|
| base | 30,000 x 1.27 s = 10.6 h (M4-13 speed) |
| fits | 16 runs x 36 sessions x (100 update-1 + 150 nightly) steps x about 0.5 s = about 20 h (about 30 h if the nightly step count were 300) |
| forward passes | about 0.3 h per run, about 6 h in all (our estimate) |
| word decoding (CPU, in the job) | measured 0.06 s per guard decision; about 25,000 per run: about 0.4 h per run, about 8 h in all |
| **total wall time** | **about 45 h** (the plan said 45-60 h); the cap is 90 h |

## Dry run (CPU only, scratch folder, no GPU)
```powershell
$env:HIP_VISIBLE_DEVICES="-1"; $env:CUDA_VISIBLE_DEVICES="-1"
C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-e2-self-teaching-t15\e2.py dry --out <scratch folder> --device cpu --threads 2 --dry-ckpt C:\Users\zhang\bci-data\runs\m4-13-long0\best.pt
```
It trains the base decoder for 3 steps on S0-S7 (CPU), then uses the M4-13 checkpoint (read only) as a strong stand-in decoder for the plumbing. It runs the start guard, the grid and all five arms on two pseudo-sessions made of S8 items, and the stop / resume test. It reads no replay session (S9-S44) and writes nothing into `results/`. Its numbers are not results.

## Tests
```powershell
C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q experiments\2026-11-23-e2-self-teaching-t15\test_e2.py
```
