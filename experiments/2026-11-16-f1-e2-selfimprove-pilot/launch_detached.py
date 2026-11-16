"""Start one P15-01 stage hidden and detached (pattern of experiments/2026-11-13-m6-13-soak/launch_detached.py).

Tree: this launcher (exits at once) -> ``python -m fidetype.utils.isolation run --class background --threads 4``
-> ``C:/venvs/fidetype-rocm/Scripts/python.exe -u <stage script> [args]`` (CPU only; common.py hides the GPU).
Flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB (no visible window; never
``Start-Process -WindowStyle Hidden``). Output: ``C:/Users/zhang/bci-data/derived/f1-e2-pilot/<name>.out``.

    .venv/Scripts/python.exe experiments/2026-11-16-f1-e2-selfimprove-pilot/launch_detached.py train_base.py
    .venv/Scripts/python.exe experiments/2026-11-16-f1-e2-selfimprove-pilot/launch_detached.py replay.py --name replay-a -- frozen oracle
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path(os.environ.get("F1E2_LAUNCH_OWN", "C:/Users/zhang/bci-data/derived/f1-e2-pilot"))  # P15-02: -gated
TORCH_PY = "C:/venvs/fidetype-rocm/Scripts/python.exe"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--name", default=None)
    a, extra = ap.parse_known_args()
    name = a.name or Path(a.script).stem
    OWN.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUNBUFFERED="1", HIP_VISIBLE_DEVICES="-1", ROCR_VISIBLE_DEVICES="-1",
               CUDA_VISIBLE_DEVICES="-1")
    cmd = [sys.executable, "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
           TORCH_PY, "-u", str(HERE / a.script), *[x for x in extra if x != "--"]]
    out = open(OWN / f"{name}.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    kw = dict(cwd=HERE, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
        breakaway = os.name == "nt"
    except OSError:  # the caller's job does not allow breakaway
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    (OWN / f"{name}.pid").write_text(str(p.pid), encoding="utf-8")
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} launched {name} pid {p.pid} breakaway={breakaway} cmd={cmd}\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
