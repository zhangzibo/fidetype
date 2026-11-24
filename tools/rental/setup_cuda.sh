#!/usr/bin/env bash
# Set up the Fidetype training environment on a rented Linux machine with an NVIDIA GPU (CUDA).
#
# The local machine uses native Windows ROCm (tools/env/setup_rocm.ps1). This script is the CUDA
# equivalent. It is idempotent: run it again at any time. It does NOT download data and it needs
# no token, key or account of any kind.
#
# Usage (on the rented machine, inside the cloned repo):
#   bash tools/rental/setup_cuda.sh                 # venv at ~/venvs/fidetype-cuda
#   VENV=/workspace/venv bash tools/rental/setup_cuda.sh
#   TORCH_INDEX=https://download.pytorch.org/whl/cu126 bash tools/rental/setup_cuda.sh
#
# Steps: 1. check the GPU driver; 2. create a Python 3.12 venv; 3. install torch 2.9.1 for CUDA
# (the same torch version as the local ROCm build); 4. install numpy, scipy, h5py, pytest and the
# repo (editable); 5. optional CPU LLM wheel; 6. run the GPU smoke test and the CPU unit tests.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="${VENV:-$HOME/venvs/fidetype-cuda}"
PYVER="${PYVER:-3.12}"
TORCH_VERSION="${TORCH_VERSION:-2.9.1}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu128}"
WITH_LLM="${WITH_LLM:-0}"   # 1: also install llama-cpp-python (CPU build) for the LLM rescoring stage

echo "==> repo: $REPO"
echo "==> venv: $VENV"

# 1. GPU driver
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "FAIL: nvidia-smi not found. Pick a machine image with the NVIDIA driver installed." >&2
  exit 1
fi
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

# 2. venv (uv if present, else python -m venv)
if [ ! -x "$VENV/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python "$PYVER" "$VENV"
  elif command -v "python$PYVER" >/dev/null 2>&1; then
    "python$PYVER" -m venv "$VENV"
  else
    echo "FAIL: neither uv nor python$PYVER found. Install one (for example: pip install uv)." >&2
    exit 1
  fi
fi
PY="$VENV/bin/python"
if command -v uv >/dev/null 2>&1; then PIP=(uv pip install --python "$PY"); else PIP=("$PY" -m pip install); "$PY" -m pip install -U pip; fi

# 3. torch for CUDA (replaces the ROCm 7.2.1 wheels of tools/env/setup_rocm.ps1)
"${PIP[@]}" "torch==${TORCH_VERSION}" --index-url "$TORCH_INDEX"

# 4. the rest
"${PIP[@]}" numpy scipy h5py pytest
"${PIP[@]}" -e "$REPO"

# 5. optional: CPU LLM for the rescoring stage of the calibration hold-out plan
if [ "$WITH_LLM" = "1" ]; then
  "${PIP[@]}" llama-cpp-python --only-binary llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu || \
    echo "WARN: no prebuilt llama-cpp-python wheel; run the LLM stage on the local machine instead."
fi

# 6. checks
"$PY" "$REPO/tools/env/gpu_smoke.py"
"$PY" -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'cudnn', torch.backends.cudnn.version())"
"$PY" -m pytest -q -p no:cacheprovider "$REPO/tools/rental/test_speed_test.py"

echo
echo "Done. Python: $PY"
echo "Next: upload the data (tools/rental/upload-list.md), then:"
echo "  $PY tools/rental/speed_test.py --derived <folder with the T15 session NPZ files>"
