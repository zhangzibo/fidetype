r"""Start the P15-54 run (f3s.py all) fully detached, with no visible window.

Same pattern as the P15-50 / P15-49 launchers: CREATE_NO_WINDOW (hidden console), CREATE_NEW_PROCESS_GROUP and,
when Windows allows it, CREATE_BREAKAWAY_FROM_JOB. Never use Start-Process -WindowStyle Hidden.

Run (repo root): C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-25-f3-small-data-falcon\launch.py
Stability pilot (amendment 2, opt-in, val only, about 0.8 GPU h, cap 1.5 h): ... launch.py pilot
Exit code 4 of f3s.py (see run.log) = waiting for a commit of results/session_roles.json, selection.json or selection-ext.json: commit + push it, then run this again.
Re-running resumes from the latest checkpoints (finished parts are skipped). Remove the pause / stop file first.
A FAILED marker of an earlier launch is renamed to FAILED.prev. f3s.py keeps the machine awake while it runs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-54")
GPU_PY = Path(r"C:\venvs\fidetype-rocm\Scripts\python.exe")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main(argv: list[str] | None = None) -> int:
    """argv: [] -> 'all' (the main run); ['pilot'] -> the opt-in stability pilot of amendment 2."""
    args = sys.argv[1:] if argv is None else argv
    stage = args[0] if args else "all"
    if stage not in ("all", "pilot"):
        print("usage: launch.py [pilot]", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("pause", "stop"):
        if (OUT / f).exists():
            print(f"{OUT / f} exists: remove it first", file=sys.stderr)
            return 2
    if (OUT / "DONE").exists():
        print(f"{OUT / 'DONE'} exists: the run is finished", file=sys.stderr)
        return 2
    pid = OUT / "run.pid"
    if pid.exists():
        old = pid.read_text(encoding="utf-8").strip()
        r = subprocess.run(["tasklist", "/FI", f"PID eq {old}", "/NH"], capture_output=True, text=True)
        if old and old in r.stdout and "python" in r.stdout.lower():
            print(f"pid {old} is still running: stop it first (README)", file=sys.stderr)
            return 2
    if (OUT / "FAILED").exists():
        os.replace(OUT / "FAILED", OUT / "FAILED.prev")
    cmd = [str(GPU_PY), "-I", "-u", str(HERE / "f3s.py"), stage]
    out = open(OUT / "run.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        breakaway = True
    except OSError:  # the caller's job does not allow breakaway
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    pid.write_text(str(p.pid), encoding="utf-8")
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched {stage} pid {p.pid} breakaway={breakaway}\n"
    with open(OUT / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
