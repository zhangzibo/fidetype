---
title: Compute setup (GPU training on Windows with ROCm)
type: question
tags: [compute, rocm, gpu]
sources: []
updated: 2026-11-08
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

## Related pages
- [Architecture](architecture.md): the decoders that we train on this GPU.
- [Project plan](project-plan.md)
