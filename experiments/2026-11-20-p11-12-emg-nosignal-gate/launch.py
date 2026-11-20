"""Start run.py fully detached and hidden (pattern: experiments/2026-11-19-p11-09-emg-trust/launch.py).

    .venv\\Scripts\\python.exe experiments/2026-11-20-p11-12-emg-nosignal-gate/launch.py            # all stages
    .venv\\Scripts\\python.exe experiments/2026-11-20-p11-12-emg-nosignal-gate/launch.py gate         # some stages

Process tree: this launcher (exits at once) -> a hidden driver (this file, ``--drive``) ->
``python -m fidetype.utils.isolation run --class background --threads 4 -- <python> -I run.py <stages>``.
Flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB. run.py holds a keep-awake.
CPU only; no GPU (HIP_VISIBLE_DEVICES and CUDA_VISIBLE_DEVICES are empty).

Check: tail results/run.log, or C:/Users/zhang/bci-data/derived/p11-12/run.out; done when
C:/Users/zhang/bci-data/derived/p11-12/DONE exists.
Resume: run the same command again (finished stages and arms are skipped).
Stop: stop the python processes whose command line has ``p11-12-emg-nosignal-gate``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p11-12")
VENV = ROOT / ".venv" / "Scripts" / "python.exe"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def drive(stages: list[str]) -> int:
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", HIP_VISIBLE_DEVICES="",
               CUDA_VISIBLE_DEVICES="")
    cmd = [str(VENV), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
           str(VENV), "-I", str(HERE / "run.py"), *stages]
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} driver start {cmd}\n")
    rc = subprocess.call(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} driver exit {rc} for {stages}\n")
    return rc


def main() -> int:
    if sys.argv[1:2] == ["--drive"]:
        return drive(sys.argv[2:])
    stages = sys.argv[1:] or ["all"]
    OWN.mkdir(parents=True, exist_ok=True)
    out = open(OWN / "run.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    cmd = [str(VENV), str(HERE / "launch.py"), "--drive", *stages]
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
