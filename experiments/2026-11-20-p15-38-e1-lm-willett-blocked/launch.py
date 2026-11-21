"""Start the P15-38 run fully detached and hidden (pattern: the P15-25 / P11-07 ``launch.py``). CPU only.

    .venv\\Scripts\\python.exe experiments/2026-11-20-p15-38-e1-lm-willett-blocked/launch.py

Process tree: this launcher (exits at once) -> a hidden driver (this file, ``--drive``) -> for each step
``python -m fidetype.utils.isolation run --class background --threads 1 -- <python> -I run.py <stages>``:
(1) ``blocks lm0`` (2) ``lm`` (3) ``overlap check lmonly test summary`` (run.py starts 4 single-thread workers).
The LM builds run in their own processes so that their memory is freed before the decode stage.
Flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB. run.py holds a keep-awake.

Check: tail results/run.log; done when C:/Users/zhang/bci-data/derived/p15-38/DONE exists.
Stop: create C:/Users/zhang/bci-data/derived/p15-38/STOP (workers finish their unit and exit; the driver
stops before the next step).
Resume: delete STOP, run the same command again (finished stages and units are skipped).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p15-38")
VENV = ROOT / ".venv" / "Scripts" / "python.exe"
STEPS = (["blocks", "lm0"], ["lm"], ["overlap", "check", "lmonly", "test", "summary"])
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _log(msg: str) -> None:
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def drive() -> int:
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", HIP_VISIBLE_DEVICES="",
               CUDA_VISIBLE_DEVICES="")
    for step in STEPS:
        if (OWN / "STOP").exists():
            _log("STOP file seen; driver exits")
            return 3
        cmd = [str(VENV), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "1", "--",
               str(VENV), "-I", str(HERE / "run.py"), *step]
        _log(f"driver start {cmd}")
        rc = subprocess.call(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
        _log(f"driver exit {rc} for {step}")
        if rc != 0:
            return rc
    return 0


def main() -> int:
    if sys.argv[1:2] == ["--drive"]:
        return drive()
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
