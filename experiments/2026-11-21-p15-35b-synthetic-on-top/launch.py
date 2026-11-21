r"""Start the P15-35b run (p35b.py all) fully detached, with no visible window.

Same pattern as the P15-08 launcher: CREATE_NO_WINDOW (hidden
console), CREATE_NEW_PROCESS_GROUP and, when Windows allows it, CREATE_BREAKAWAY_FROM_JOB. Never use
Start-Process -WindowStyle Hidden (it can open a visible terminal; closing it kills the run).

Run (repo root): .venv\Scripts\python.exe experiments\2026-11-21-p15-35b-synthetic-on-top\launch.py
Re-running resumes from the latest checkpoints (finished parts are skipped). Remove the pause / stop
file first. p35b.py keeps the machine awake (SetThreadExecutionState) while it runs.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-35b")
GPU_PY = Path(r"C:\venvs\fidetype-rocm\Scripts\python.exe")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("pause", "stop"):
        if (OUT / f).exists():
            print(f"{OUT / f} exists: remove it first", file=sys.stderr)
            return 2
    cmd = [str(GPU_PY), str(HERE / "p35b.py"), "all"]
    out = open(OUT / "run.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        breakaway = True
    except OSError:  # the caller's job does not allow breakaway
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    (OUT / "run.pid").write_text(str(p.pid), encoding="utf-8")
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched pid {p.pid} breakaway={breakaway}\n"
    with open(OUT / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
