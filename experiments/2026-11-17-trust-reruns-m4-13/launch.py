r"""Start the trust-rerun queue (run_queue.py) fully detached, with no visible window.

Same pattern as experiments/2026-11-16-p11-01-emg-decoder/launch_train.py: CREATE_NO_WINDOW (hidden console),
CREATE_NEW_PROCESS_GROUP and, when Windows allows it, CREATE_BREAKAWAY_FROM_JOB. Never use
Start-Process -WindowStyle Hidden (it can open a visible terminal; closing it kills the run).

Run (repo root): .venv\Scripts\python.exe experiments\2026-11-17-trust-reruns-m4-13\launch.py
The hidden queue polls every 60 s (CPU venv, no torch, no GPU) until C:\Users\zhang\bci-data\runs\m4-13-queue.DONE
exists (read only), then runs the CPU stages. Re-running resumes: done stages are skipped.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
Q = Path(r"C:\Users\zhang\bci-data\derived\trust-reruns-m4-13")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    Q.mkdir(parents=True, exist_ok=True)
    for f in ("pause", "stop"):
        if (Q / f).exists():
            print(f"{Q / f} exists: remove it first", file=sys.stderr)
            return 2
    cmd = [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-u", str(HERE / "run_queue.py"), *sys.argv[1:]]
    out = open(Q / "queue.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        breakaway = True
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched pid {p.pid} breakaway={breakaway} args={sys.argv[1:]}\n"
    with open(Q / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
