"""Start the P15-25 run fully detached and hidden (pattern: experiments/2026-11-20-p11-07-emg-beam-lm/launch.py).

    .venv\\Scripts\\python.exe experiments/2026-11-20-p15-25-e1-same-lm/launch.py

It refuses to start while ``C:/Users/zhang/bci-data/derived/p3-12/DONE`` is missing (P3-12 needs a quiet machine).

Process tree: this launcher (exits at once) -> a hidden driver (this file, ``--drive``) ->
1. ``python -m fidetype.utils.isolation run --class background --threads 1 -- <ROCm python> -I logits.py``
   (GPU forward of the 41 E1a models; skipped when ``derived/p15-25/lp/DONE.json`` exists);
2. ``python -m fidetype.utils.isolation run --class background --threads 1 -- <python> -I run.py all``
   (CPU; run.py starts 6 single-thread worker processes).
Flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB. Both stages hold a keep-awake.

Check: tail results/run.log; done when C:/Users/zhang/bci-data/derived/p15-25/DONE exists.
Stop: create C:/Users/zhang/bci-data/derived/p15-25/STOP (workers finish their unit and exit), or stop the python
processes whose command line has ``p15-25-e1-same-lm``.
Resume: delete STOP, run the same command again (finished runs and units are skipped).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p15-25")
P3_12_DONE = Path("C:/Users/zhang/bci-data/derived/p3-12/DONE")
VENV = ROOT / ".venv" / "Scripts" / "python.exe"
ROCM = Path("C:/venvs/fidetype-rocm/Scripts/python.exe")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _log(msg: str) -> None:
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def drive() -> int:
    base = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    rc = 0
    if not (OWN / "lp" / "DONE.json").exists():
        cmd = [str(VENV), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "1", "--",
               str(ROCM), "-I", str(HERE / "logits.py")]
        _log(f"driver start {cmd}")
        rc = subprocess.call(cmd, cwd=ROOT, env=base, stdin=subprocess.DEVNULL)
        _log(f"driver exit {rc} for logits")
        if rc != 0:
            return rc
    env = dict(base, HIP_VISIBLE_DEVICES="", CUDA_VISIBLE_DEVICES="")
    cmd = [str(VENV), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "1", "--",
           str(VENV), "-I", str(HERE / "run.py"), "all"]
    _log(f"driver start {cmd}")
    rc2 = subprocess.call(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    _log(f"driver exit {rc2} for run.py all")
    return rc2


def main() -> int:
    if sys.argv[1:2] == ["--drive"]:
        return drive()
    if not P3_12_DONE.exists():
        print(f"refused: {P3_12_DONE} does not exist yet (P3-12 timing needs a quiet machine)")
        return 2
    OWN.mkdir(parents=True, exist_ok=True)
    out = open(OWN / "run.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    cmd = [str(VENV), str(HERE / "launch.py"), "--drive"]
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched driver pid {p.pid} cmd={cmd}\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
