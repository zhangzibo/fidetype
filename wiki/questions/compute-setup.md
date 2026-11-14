---
title: Compute setup (GPU training on Windows with ROCm)
type: question
tags: [compute, rocm, gpu, latency, cpu-isolation, parallel]
sources: []
updated: 2026-11-14
---

# Compute setup: GPU training on Windows with ROCm

**Question asked:** How do we train models on the local AMD GPU?

**Answer:** We use AMD's native Windows ROCm 7.2.1 build of PyTorch 2.9.1. The venv is at the short path `C:\venvs\fidetype-rocm`. The script `tools/env/setup_rocm.ps1` builds it again from zero.

## Hardware

| Part | Value |
|---|---|
| OS | Windows 11 Home (10.0.26200) |
| GPU | AMD Radeon RX 7800 XT, architecture `gfx1101` (RDNA 3), 16 GiB VRAM |
| Driver | AMD Adrenalin 26.10.1 |
| Python | CPython 3.12.16, through uv 0.13.7 |

## Chosen path: native Windows ROCm 7.2.1 + torch 2.9.1

AMD publishes ROCm wheels for Windows at https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/. We install these files from that folder:

| Package | Version | File |
|---|---|---|
| rocm (meta package) | 7.2.1 | `rocm-7.2.1.tar.gz` |
| rocm-sdk-core | 7.2.1 | `rocm_sdk_core-7.2.1-py3-none-win_amd64.whl` |
| rocm-sdk-devel | 7.2.1 | `rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl` |
| rocm-sdk-libraries-custom | 7.2.1 | `rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl` |
| torch | 2.9.1+rocm7.2.1 | `torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl` |
| torchaudio | 2.9.1+rocm7.2.1 | `torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl` |

The folder also has `torchvision-0.24.1+rocm7.2.1`. We do not install it now.

The venv also has numpy 2.5.4, scipy 1.18.1, mne 1.13.2, pytest 9.2.0 and the `fidetype` package (editable install).

AMD documentation:
- Install guide: [Install PyTorch on Windows (Radeon)](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html)
- [Windows compatibility matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html)

In PyTorch, the ROCm GPU uses the `cuda` device name. Thus `torch.cuda.is_available()` is `True` and code uses `device="cuda"`.

## The MAX_PATH catch and its fix

**Problem:** Windows limits a file path to 260 characters (MAX_PATH). rocBLAS loads its GEMM kernel files from `<venv>\Lib\site-packages\_rocm_sdk_libraries_custom\bin\rocblas\library\`. The kernel file names are long. If the venv path is long (for example, inside OneDrive or a temp folder), the full paths go over 260 characters. rocBLAS then crashes with `0xC0000005` (access violation) during the first GEMM.

**Fix:** Put the venv at a short path: `C:\venvs\fidetype-rocm`. Never put it inside OneDrive or inside the repo.

| Measurement (in `C:\venvs\fidetype-rocm`) | Length |
|---|---|
| Longest file path under the rocBLAS library folder | 174 characters |
| Longest file path under the whole venv | 199 characters |

The setup script prints the longest path. It gives a warning above 240 characters. It also refuses a venv path that contains `OneDrive`.

## Benchmarks

### Test agent results (2026-11-08)

| Benchmark | GPU | CPU |
|---|---|---|
| 4096 fp32 matmul | 14.05 ms, 9.8 TFLOPS | 171 ms, 0.80 TFLOPS |
| 4096 bf16 matmul | 2.66 ms, 51.7 TFLOPS | 45 ms, 3.05 TFLOPS |
| 4096 fp16 matmul | 2.52 ms, 54.5 TFLOPS | — |
| training step | 14.2 ms fp32 / 9.3 ms bf16 | 143 ms |
| first step (kernel load) | 7.4 s fp32 / 4.9 s bf16 | — |

The peak memory was 4.0 GB. This run included a 4 GiB allocation test. For training, the GPU is about 10–15× faster than the CPU.

The training model is a small Conv1d + Transformer encoder (2 Conv1d layers, 4 Transformer layers, d = 128). The batch is 64 × 270 channels × 100 time steps.

### Smoke test in the permanent venv (2026-11-08)

`tools/env/gpu_smoke.py`, run by the setup script on a fresh venv:

| Check | Result |
|---|---|
| 4096 fp32 matmul | 14.83 ms, 9.3 TFLOPS (first call 49 ms) |
| fp32 GPU vs CPU | max abs error 9.9e-04; relative to the max value 2.9e-06 |
| 4096 bf16 matmul | 2.77 ms, 49.6 TFLOPS (first call 85 ms) |
| training, bf16 autocast, 10 steps | first step 960 ms; median of steps 2–10 9.6 ms; loss 2.258 → 0.166 |
| peak memory (training only) | 0.27 GiB |
| `import fidetype` | OK |

An earlier run in the same venv gave 14.30 ms (9.6 TFLOPS) fp32, 2.66 ms (51.7 TFLOPS) bf16 and a 9.2 ms training step. The repo test suite (41 tests) also passes in this venv.

> **Our take:** The first step took about 1 s here, not 4.9 s. The likely cause is a warm file cache: the kernel files were read shortly before. Expect a few seconds in a cold process.

## Caveats

- **torch is pinned at 2.9.1.** AMD publishes the Windows wheels for each ROCm release. A new torch version needs a new AMD wheel set.
- **SDPA flash and memory-efficient attention are experimental.** torch prints a warning for each. To try them, set `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1`. Without it, torch uses the math attention kernel.
- **hipBLASLt is not supported on Windows.** Only rocBLAS does GEMM. (The hipBLASLt files are in the wheel, but torch does not use them.)
- **Kernel loading costs a few seconds per process.** The first GEMM or training step in each new process is slow. Do not include it in timings.
- **torch-directml is dead.** Its last release supports torch ≤ 2.3.1. Do not use it.
- **WSL was not tested.**
- **uv hardlinks can fail.** On this machine, a hardlink from the uv cache failed with `os error 396`. The setup script sets `UV_LINK_MODE=copy` to avoid this.

## Training notes from the M1-B decoder (2026-11-08)

Source: [M1-B decoder results](../../experiments/2026-11-08-m1b-decoder/results.md), "GPU memory and speed".

- **MIOpen searches convolution kernels for each new input shape.** With variable segment lengths, the first run spent minutes per batch. Fix 1: set `MIOPEN_FIND_MODE=FAST`. `fidetype.decoders.train` and `infer` set it. Fix 2: pad the lengths to a multiple of 100 samples (`data.pad_multiple`). This gives few distinct shapes. The model masks the padding, so the outputs do not change.
- **CPU contention slows the GPU by 10x or more.** Kernel dispatch needs CPU time. When preprocessing uses most of the 16 threads, a training step becomes very slow. Set `train.torch_threads = 4`, and do not run training at the same time as heavy preprocessing if you can avoid it.
- **Fallback without MIOpen:** `FIDETYPE_CONV_IMPL=gemm` runs the convolutions as unfold + matmul. The result and the speed are the same. It uses about 70 % more memory, so the default stays `native`.
- **Size:** the 10 M-parameter decoder uses 1.07 to 1.74 GB of GPU memory at batch 16, and an epoch takes 1.2 to 3.3 s on 1 to 5 subjects.
- **Process-exit hang (found in M1-C, 2026-11-08).** A process that ran MIOpen convolutions does not end after `sys.exit` or `os._exit`. It spins one CPU core and keeps about 3.6 GB. Fix: `fidetype.decoders.train.hard_exit()` calls `TerminateProcess`, which skips the HIP DLL-detach code. Source: [M1-C results](../../experiments/2026-11-08-m1c-decoder-aux/results.md).

## Driver crash (2026-11-08)

### What happened
- At about 16:44 on 2026-11-08 the PC blue-screened: bugcheck 0x7E in the AMD driver `amdkmdag` (`DMM_PowerManagement::GetPowerState`).
- **The cause is not confirmed.** It can be a driver bug in either AMD driver branch, or a hardware fault.
- The minidump `C:\WINDOWS\Minidump\110826-18843-01.dmp` can show which device's driver failed (WinDbg `!analyze -v`). Nobody has analysed it yet.

### The two driver versions are by design
- The iGPU (AMD Radeon(TM) Graphics) has driver 32.0.21045.16010. The RX 7800 XT has driver 32.0.32015.7029.
- Both come from **one package, AMD Adrenalin 26.10.1**. The registry value `RadeonSoftwareVersion` is 26.10.1 on both devices.
- Since Adrenalin 25.10.2, AMD ships RDNA1/RDNA2 GPUs (this includes Ryzen iGPUs) on a separate "maintenance" driver branch ([HotHardware](https://hothardware.com/news/amd-addresses-confusion-radeon-gpu-driver-strategy)). So two versions are expected. A reinstall cannot make them the same.
- An earlier note called this a "driver mismatch" and the likely cause. That was wrong.

### Training stack and driver needs
| Item | Value |
|---|---|
| torch | 2.9.1+rocm7.2.1 (wheels from repo.radeon.com/rocm/windows/rocm-rel-7.2.1) |
| HIP runtime | inside the venv; no system HIP SDK |
| GPU that torch sees | RX 7800 XT (`gfx1101`) only. torch does not use the iGPU |
| Monitors | both on the RX 7800 XT |
| Driver needed | 26.2.2 or newer for the 7.2.1 PyTorch release ([AMD guide](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html)). The guide gives no upper limit |
| Driver now | 26.10.1 (works) |
| Newest driver | 26.10.2 (bug-fix release, 2026-10-30; [release notes](https://www.amd.com/en/resources/support-articles/release-notes/RN-RAD-WIN-26-10-2.html)). Very likely safe |

- Do **not** install AMD's separate "ROCm 10.1" driver (26.10.41.05). It targets a newer ROCm.
- A driver update does not need a venv reinstall. Fallback: `tools\env\setup_rocm.ps1`.

### Plan
1. Disable the iGPU: Device Manager → Display adapters → AMD Radeon(TM) Graphics → Disable device. Or disable it in the BIOS.
2. Optional: reinstall Adrenalin 26.10.2 with Factory Reset. Use DDU only if the crash occurs again.
3. Verify, in this order:
   ```powershell
   C:\venvs\fidetype-rocm\Scripts\python.exe -c "import torch;print(torch.__version__,torch.version.hip,torch.cuda.is_available(),torch.cuda.get_device_name(0))"
   C:\venvs\fidetype-rocm\Scripts\python.exe tools\env\gpu_smoke.py
   ```
   Then run a short training job, followed by 10–20 min idle. This repeats the crash condition.
- **Result (2026-11-08):** with the iGPU disabled, the stress test **passed**: 721 s ConvCTC training, then 1200 s idle with the CUDA context alive. No crash. The event log has no ID 41/1001/4101, WHEA or amdkmdag events. The preprocessing resumed at 18:38. The cause stays unconfirmed.
- Preprocessing stays paused until step 3 passes. After that, run at most one heavy job (GPU training OR preprocessing, never both).

## How to use it

Two environments exist. Each has one job:

| Environment | Path | Use |
|---|---|---|
| GPU (ROCm) | `C:\venvs\fidetype-rocm` | Training and GPU experiments. |
| CPU (uv-managed) | `<repo>\.venv` | Tests and CI. `uv run` and `uv sync` use it. Keep it. |

Use the GPU venv in one of two ways:

```powershell
# 1. Activate it
C:\venvs\fidetype-rocm\Scripts\Activate.ps1
python my_training_script.py

# 2. Or call its python directly
C:\venvs\fidetype-rocm\Scripts\python.exe my_training_script.py
```

In Git Bash, use `/c/venvs/fidetype-rocm/Scripts/python.exe`.

To build the venv again (or to repair it), run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\env\setup_rocm.ps1
# Optional: another short path
powershell -ExecutionPolicy Bypass -File tools\env\setup_rocm.ps1 -VenvPath C:\Users\zhang\venvs\fidetype-rocm
```

The script is idempotent. It skips the steps that are done, and it ends with the smoke test. To run only the smoke test:

```powershell
C:\venvs\fidetype-rocm\Scripts\python.exe tools\env\gpu_smoke.py
```

The `fidetype` package is an editable install. Code changes in `src/fidetype` take effect at once. If `pyproject.toml` gets new dependencies, install them into the GPU venv too (run the script again, or use `uv pip install --python C:\venvs\fidetype-rocm\Scripts\python.exe <package>`).

## CPU isolation for latency measurements (2026-11-13, M0-22)

Up to 4 agents can run at the same time. Their CPU load distorts latency numbers. `fidetype.utils.isolation` splits the CPUs into two classes. It uses Windows process affinity, a job object and priority classes (ctypes only, no psutil).

| Class | CPUs on this PC (Ryzen 7 9800X3D) | Priority | Threads (OMP, MKL, OpenBLAS, NumExpr, torch hint) | How many at once |
|---|---|---|---|---|
| `timing` | 8, 10, 12, 14 (one per physical core 4-7); siblings 9, 11, 13, 15 stay idle | above normal | 4 | 1 (file lock) |
| `background` | 0-7 (physical cores 0-3, both SMT threads) | below normal | 8 (set `--threads` lower if several share) | any |

**Rule: latency experiments use the timing class. Other heavy CPU jobs (training, preprocessing, test suites) should use the background class.**

Run a command. Children inherit the class, also through a venv `python.exe` (a job object holds the whole process tree):

```
.venv/Scripts/python -m fidetype.utils.isolation run --class timing --env-json run-env.json -- .venv/Scripts/python my_latency_test.py
.venv/Scripts/python -m fidetype.utils.isolation run --class background --threads 4 -- C:/venvs/fidetype-rocm/Scripts/python.exe train.py
.venv/Scripts/python -m fidetype.utils.isolation show
```

`show` prints the CPU split, the lock holder and the registered jobs. A second timing job fails at once with exit code 75 and names the holder. Add `--wait 600` (seconds; `-1` = forever) to wait instead. The lock is `C:\Users\zhang\bci-data\runs\cpu-isolation\timing.lock`. Windows frees it when the holder process ends, also after a crash.

In-process (records the conditions into your results JSON):

```python
from fidetype.utils.isolation import isolated

with isolated("timing", wait_s=600, label="M4-xx latency") as iso:
    lat = run_my_benchmark()
results["measurement_env"] = iso.record
```

The record holds the class, CPUs, priority, CPU model, wall time, own CPU time, the load on the class CPUs, the foreign load (load from other processes), the load on the idle SMT siblings and on the whole machine. `clean` is true only if the timing lock was held, affinity and priority were set, and the foreign load stayed below 5 %. `clean_reasons` lists what failed. Set the thread variables before you import numpy or torch: `isolated()` sets them in `os.environ`, and this only affects libraries loaded later (it calls `torch.set_num_threads` at once if torch is loaded).

**Check (2026-11-13, `experiments/2026-11-13-cpu-isolation/results.md`):** a 0.33 ms single-thread workload had p50 / p95 0.335 / 0.645 ms alone in the timing class, 0.501 / 0.661 ms with an 8-process load in the background class, and 0.659 / 1.126 ms (max 16 ms) with the same load and no isolation. The timing class removes the long tail. The p50 still rises: the L3 cache and memory are shared, and unpinned processes still use the timing cores.

Limits:
- Isolation only works if the other heavy jobs also use the background class. Unpinned processes (desktop apps, the M6-13 soak, agents that do not use the tool) can still run on the timing cores. The record shows this as foreign load.
- Shared L3 cache and memory bandwidth are not isolated (one CCD).
- The GPU is not covered. Only CPU time is isolated.
- The CPU split assumes one processor group (at most 64 logical CPUs).
- Linux: affinity works. Raising priority needs root, so the timing class runs at normal priority there.

## Parallel CPU experiments with pmap (2026-11-14, M0-24)

Most CPU experiments run one loop in one process: refits, repeated splits, replays of 816 trials. `fidetype.utils.parallel.pmap` runs such a loop in a pool of worker processes. The output does not change.

```python
from fidetype.utils.parallel import add_workers_arg, pmap

_CTX = {}
def init(path):                  # once per worker: load the large read-only data
    _CTX["ctx"] = load_context(path)
def one_split(r, seed):          # a module-level function (spawn imports it by name)
    return evaluate(_CTX["ctx"], r, np.random.default_rng(seed))

if __name__ == "__main__":       # required: each worker imports the script again
    ap = argparse.ArgumentParser(); add_workers_arg(ap); a = ap.parse_args()
    rows = pmap(one_split, range(200), seed=3, initializer=init, initargs=(path,),
                workers=a.workers, exact=a.exact_workers, checkpoint=out / "ckpt", mem_per_worker_gb=1.6)
```

What pmap guarantees:

| Property | How |
|---|---|
| Same output as a loop | Results come back in input order. Item `i` gets the seed `item_seed(seed, i)` (NumPy `SeedSequence([seed, i])`). The seed does not depend on the worker, the worker count or the chunk size. |
| Background CPU class | Spawned workers (also on Linux), pinned to the background CPUs (0-7 here) at below-normal priority, 1 thread each (OMP, MKL, OpenBLAS, NumExpr, torch). It never takes the timing lock. |
| Automatic worker count | Background CPUs minus the slots of other registered jobs (`isolation show`), at least 1. With `mem_per_worker_gb`, also at most free RAM / that value. `--workers N` and the env variable `FIDETYPE_WORKERS` are caps. `--exact-workers` uses `--workers` as given. While it runs, pmap registers itself with its worker count, so other pmap runs see it. |
| Shared data | The `initializer` loads large read-only data once per worker, not once per task. For large NumPy tables, `save_shared` / `load_shared` write `.npy` files and memory-map them; the OS shares the pages. |
| Resume | With `checkpoint=DIR`, each finished chunk is saved at once. A rerun with the same items loads them and runs only the rest. A checkpoint of other items is refused. After a failure in one task, the running tasks finish and are saved, then the error is raised. |
| Serial fallback | `workers=1` (or one free slot) runs in the calling process, with the same initializer, seeds, order and checkpoints. Tests and CI use it. |

Rules:
- Use pmap for loops of independent items that each take more than a few seconds: refits per split or per fit, per-session replays, per-condition simulator runs. A loop that takes less than about 30 s in total gets no gain (spawn and initializer cost).
- The task function must be pure: its output may depend only on the item, its seed and the read-only shared data. Memo caches are allowed (they do not change values).
- **Do not use pmap for latency numbers.** Parallel workers share caches and memory bandwidth. Use it for decisions and metrics; measure latency serially in the timing class.
- Each worker loads its own copy of the decoder context. The B2T '25 context is about 0.9-1.3 GB per worker, so set `mem_per_worker_gb` (1.6 is safe). With 31 GB RAM and other agents running, RAM is often the limit, not CPUs.
- Workers do not share memo caches. If one item fills a decode cache that a later item reuses, a serial run is faster than its CPU sum suggests. Save new decodes to disk and load them in the initializer (M2-18 `t15_eval.py` does this now).

Scripts that use it (`--workers N`, default auto):

| Script | Unit of work | Equality check (2026-11-14) |
|---|---|---|
| `experiments/2026-11-13-m2-18-empty-commits/t15_eval.py` | one of the 6 Paper 1 T15 fits | `t15.json` equal to serial and to the committed file (wall-time keys ignored); `t15.md` byte-equal |
| `experiments/2026-11-12-paper1-r4-analyses/split-tables/run.py --stage b2t --workers N [--out DIR --jobs ... --r-from --r-to]` | one repeated-split item table | full R = 200 rebuild (700 tables): 699 byte-equal to the R4 cache, 1 differs only in the `new_decodes` counter; M3-02 repeated-split rows equal to the committed `splits.json` |
| `experiments/2026-11-13-m4-06-real-replay/run.py uncached --workers N [--out DIR]` | one session (post-implant day) of the 816-trial B2T replay | 816/816 decisions equal to serial (all fields except `latency_s`) |

Measured speed-ups (2026-11-14, while 3-5 other jobs used the background class and only 4-7 GB RAM was free, so the auto sizing chose 2-4 workers): T15 6 fits 255 -> 120 s (2.1x, 2 workers); split tables 16-table subset 208 -> 71 s (2.9x, 4 workers), full 300 guard-on tables about 6,600 -> 1,958 s (about 3.4x, 4 workers); M4-06 uncached replay 158 -> 85 s (1.9x, 2 workers). On a free machine expect more (8 background CPUs = 4 cores with SMT); not measured. Full checks: [M0-24 results](../../experiments/2026-11-14-m0-24-parallel/results.md).

## Related pages
- [Architecture](architecture.md): the decoders that we train on this GPU.
- [Project plan](project-plan.md)
- CPU isolation code: `src/fidetype/utils/isolation.py`. Check: `experiments/2026-11-13-cpu-isolation/results.md`.
- [Decoder M1 results](decoder-m1-results.md)
