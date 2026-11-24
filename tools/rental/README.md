# Renting a GPU for the pre-registered training jobs

This kit helps you rent one GPU machine **only when a plan is ready**, check its speed in one hour, and then run a job. It needs no account from us, and it holds no tokens or keys. You choose the provider and you pay; nothing here spends money.

Files:

| file | what it does |
|---|---|
| `README.md` | these steps |
| `setup_cuda.sh` | sets up Python, PyTorch for CUDA and this repository on the rented Linux machine |
| `speed_test.py` | a one-hour test: it times training steps of the T15 decoder recipe and prints the projected GPU hours of two plans |
| `test_speed_test.py` | CPU unit tests of the speed test (run them locally first) |
| `upload-list.md` | exactly which data files to upload for each job, with their licences |

The plans that may use a rented GPU:

| plan | GPU hours (local, measured or estimated) | GPU hours (rented, our estimate) |
|---|---|---|
| [T15 calibration hold-out retrain](../../experiments/2026-11-23-t15-calibration-holdout/plan.md) | about 41 h | about 10-14 h |
| [Self-teaching replay on T15](../../experiments/2026-11-23-e2-self-teaching-t15/plan.md) | about 45-60 h | about 12-17 h |
| [Cross-body transfer at full data](../../experiments/2026-11-23-f3-full-data-controls/plan.md) | about 33-50 h | about 10-16 h (prefer local) |

The rented numbers assume a GPU about 3-4 times faster than the local one. **This is not measured.** Step 5 measures it.

## Step 1. Before you rent (local, free)

1. Run the unit tests on your computer:
   `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider tools/rental/test_speed_test.py`
2. Make sure the plan you want to run is committed (pre-registration first).
3. Collect the files of your job from `upload-list.md` into one folder on your computer.

## Step 2. Choose the machine

You can use any provider. Choose by these properties, not by name:

| property | choose | why |
|---|---|---|
| GPU | one NVIDIA data-centre GPU with at least 40 GB memory (A100 40/80 GB or H100 80 GB class). A 24 GB card (L40S, A6000, RTX 4090 class) also works and costs less | the T15 recipe used up to about 12 GB on the local 16 GB card; more memory gives room |
| number of GPUs | **one** | the code trains on one GPU; a second GPU stays idle and you pay for it |
| CPU | at least 16 vCPU (32 is better for the self-teaching job) | word decoding and calibration draws run on the CPU |
| RAM | at least 64 GB | the trainer holds all T15 features (about 9 GB as float16) in memory |
| disk | at least 100 GB | data, checkpoints, logs |
| system image | Ubuntu 22.04 or 24.04 with the NVIDIA driver (550 or newer) and CUDA 12.x | `setup_cuda.sh` checks the driver |
| billing | per minute or per second; a spending limit or alert | you stop paying when you stop the machine |
| interruptible ("spot") machines | acceptable | the trainers save a checkpoint every 4 minutes and resume exactly; an interruption loses at most minutes |
| access | SSH with a key pair that stays on your computer | no passwords, no tokens in files |

Set a spending alert at the provider before you start the machine.

## Step 3. Start the machine and get the code

```bash
ssh <user>@<machine>
git clone https://github.com/zhangzibo/fidetype.git fidetype
cd fidetype
```

The repository is public; no token is needed. Never paste a token or key into a file on the machine.

## Step 4. Set up and upload

```bash
bash tools/rental/setup_cuda.sh          # about 5-10 minutes; ends with a GPU smoke test
```

From your computer, copy the job's files (see `upload-list.md`), for example:

```bash
scp C:/Users/zhang/bci-data/derived/m4-01-02-lookahead/t15.*.npz <user>@<machine>:/data/t15-derived/
scp C:/Users/zhang/bci-data/derived/m4-01-02-lookahead/sessions.json C:/Users/zhang/bci-data/derived/m4-01-02-lookahead/texts.json <user>@<machine>:/data/t15-derived/
```

(`rsync -av --partial` resumes a broken upload; it is available in Git Bash or WSL.)

## Step 5. The one-hour speed test

```bash
~/venvs/fidetype-cuda/bin/python tools/rental/speed_test.py --derived /data/t15-derived
```

It loads the data (a few minutes), times up to 1,000 full training steps and 1,000 short fit steps, and stops timing after 50 minutes. It prints, and writes to `speed_test_result.json`:

- `s_per_step_train_median`: seconds per training step (local reference: 1.27 s on the RX 7800 XT);
- `speedup_vs_local_ref`;
- `projected_gpu_hours`: the GPU hours of the calibration hold-out retrain and of the self-teaching replay;
- `max_gpu_mem_gib`.

Without data you can still check the machine: `speed_test.py --synthetic` (random inputs of the same shapes; the time per step is close, but not equal, to real data).

**Decide after the test:** multiply the projected hours by the provider's hourly price. Add about 50 % for a first run (setup, a failed launch, the CPU stage). If the result is not clearly cheaper or faster than the local GPU, stop the machine and run locally.

## Step 6. Run the job

Each plan names its launcher once its code is committed. Run it inside `tmux` or with `nohup` so that it survives a closed SSH session:

```bash
tmux new -s job
~/venvs/fidetype-cuda/bin/python <launcher of the plan>
# detach: Ctrl-b d ; re-attach: tmux attach -t job
```

Check, stop and resume as the plan says (a `stop` file in the run folder saves a checkpoint and exits).

## Step 7. Bring the results home and clean up

1. Copy back only the files that the plan names as outputs (aggregates, logs, and the checkpoint if the plan keeps one locally).
2. **Delete the uploaded data and the disk.** Destroy the machine and every volume or snapshot. Check the provider's billing page: nothing should still run.
3. Weights trained on research-only inputs never leave your own computer after this.

## What must change between ROCm (local) and CUDA (rented)

The code runs on the local AMD GPU with native Windows ROCm. On a rented NVIDIA machine:

| item | local (ROCm, Windows) | rented (CUDA, Linux) | where |
|---|---|---|---|
| PyTorch wheels | AMD ROCm 7.2.1 wheels for torch 2.9.1 (`tools/env/setup_rocm.ps1`) | torch 2.9.1 from the PyTorch CUDA index (`setup_cuda.sh`) | environment |
| cuDNN / MIOpen | the T15 trainer switches it **off** (`torch.backends.cudnn.enabled = False`), because the MIOpen GRU backward fails on the local ROCm build | can be **on** (cuDNN GRU, much faster). The speed test does this by default (`--cudnn auto`). The plans record the setting; results are not bit-identical across platforms | `experiments/2026-11-15-m4-13-long-train/train.py` (and the older T15 / T12 trainers) |
| CTC lengths on the CPU | a work-around for a stale-length bug on ROCm / Windows | harmless on CUDA; keep it | same trainer |
| TF32 | not used | keep it **off** (PyTorch default for matmul) so the numbers match fp32; the speed test has `--tf32` only to measure the difference | speed test, trainers |
| data paths | absolute Windows paths in each experiment's `config.json` (for example `C:/Users/zhang/bci-data/...`) | the new wrappers take the data folder as an argument (`--derived`); for old code, set the module paths after import (as the speed test does) | configs |
| Python path | `C:\venvs\fidetype-rocm\Scripts\python.exe` in the launchers | `~/venvs/fidetype-cuda/bin/python` | launchers |
| detached launch | Windows process flags (`CREATE_NO_WINDOW`, `CREATE_BREAKAWAY_FROM_JOB`) and `fidetype.utils.isolation` (Windows CPU sets) | `tmux` / `nohup`; CPU pinning with `taskset` if needed | launchers |
| keep-awake and priority | `SetThreadExecutionState`, `BELOW_NORMAL_PRIORITY_CLASS` | not needed (servers do not sleep); the code already uses `os.nice` off Windows | `fidetype.utils.power`, `t15.below_normal_priority` |
| CPU LLM | prebuilt CPU wheel of `llama-cpp-python` for Windows | the Linux CPU wheel (`WITH_LLM=1 bash tools/rental/setup_cuda.sh`), or keep this stage local | calibration hold-out plan, CPU stage |
| long paths | the venv must stay at a short path (Windows `MAX_PATH`) | no limit | environment |

## Safety notes

- The repository never holds secrets. Do not add provider keys, tokens or e-mail addresses to any file here.
- Upload only the files in `upload-list.md`. Research-only files (marked there) are private copies for non-commercial research: never share or publish them, and delete them with the machine.
- One GPU job at a time on each machine.
