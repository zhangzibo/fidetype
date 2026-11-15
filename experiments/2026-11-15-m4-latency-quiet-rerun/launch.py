"""Start rerun.py detached and without a window (CREATE_NO_WINDOW + new process group + job breakaway).

    .venv\\Scripts\\python.exe experiments/2026-11-15-m4-latency-quiet-rerun/launch.py
Check: Get-Content experiments/2026-11-15-m4-latency-quiet-rerun/results/run.log -Tail 5 ; results/DONE marks the end.
Stop:  taskkill /T /F /PID (Get-Content C:/Users/zhang/bci-data/runs/m4-02r.pid). No resume: start again (about 25 min).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = Path("C:/Users/zhang/bci-data/runs")
CREATE_NO_WINDOW, CREATE_NEW_PROCESS_GROUP, CREATE_BREAKAWAY_FROM_JOB = 0x08000000, 0x00000200, 0x01000000


def main() -> int:
    cmd = [sys.executable, "-I", str(HERE / "rerun.py")]
    out = open(RUNS / "m4-02r.out", "ab")
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    (RUNS / "m4-02r.pid").write_text(str(p.pid), encoding="ascii")
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched pid {p.pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
