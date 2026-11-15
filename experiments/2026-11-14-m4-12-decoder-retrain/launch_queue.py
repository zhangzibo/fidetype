"""Start queue.ps1 fully detached with no visible window (M4-12). Our own code; same approach as
experiments/2026-11-13-m6-13-soak/launch_detached.py.

powershell starts with CREATE_NO_WINDOW (a hidden console), CREATE_NEW_PROCESS_GROUP and, when Windows
allows it, CREATE_BREAKAWAY_FROM_JOB. queue.ps1 starts its children with -NoNewWindow, so they share
that hidden console. (DETACHED_PROCESS, pythonw.exe or Start-Process -WindowStyle Hidden can open a
visible Windows Terminal window; closing it kills the run with 0xC000013A.)

Run (repo root): .venv\\Scripts\\python.exe experiments\\2026-11-14-m4-12-decoder-retrain\\launch_queue.py
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = Path(r"C:\Users\zhang\bci-data\runs")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "queue.ps1")]
    out = open(RUNS / "m4-12-queue.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        breakaway = True
    except OSError:  # the caller's job does not allow breakaway
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched queue pid {p.pid} breakaway={breakaway}\n"
    with open(RUNS / "m4-12-launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
