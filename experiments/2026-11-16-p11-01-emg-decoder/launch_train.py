r"""Start P11-01 GPU training (train.py all) fully detached, with no visible window.

Same pattern as experiments/2026-11-15-m4-13-long-train/launch.py: CREATE_NO_WINDOW (hidden console),
CREATE_NEW_PROCESS_GROUP and, when Windows allows it, CREATE_BREAKAWAY_FROM_JOB. Never use
Start-Process -WindowStyle Hidden (it can open a visible terminal; closing it kills the run).

Run (repo root): .venv\Scripts\python.exe experiments\2026-11-16-p11-01-emg-decoder\launch_train.py [--wait-for FILE]
--wait-for FILE: the hidden child first waits (polls every 60 s, no GPU use) until FILE exists, for
example C:\Users\zhang\bci-data\runs\m4-13-queue.DONE (read only; this script never writes in runs\).
Re-running resumes every stage from its latest.pt. Remove the pause / stop file first.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = Path(r"C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train")
GPU_PY = Path(r"C:\venvs\fidetype-rocm\Scripts\python.exe")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-for", default=None)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("pause", "stop"):
        if (OUT / f).exists():
            print(f"{OUT / f} exists: remove it first", file=sys.stderr)
            return 2
    train = [str(GPU_PY), str(HERE / "train.py"), "all"]
    if a.wait_for:
        wait = Path(a.wait_for)
        # A small hidden waiter in the CPU venv: no torch import, no GPU use while it waits.
        code = (f"import pathlib,subprocess,sys,time\n"
                f"w=pathlib.Path(r'{wait}')\n"
                f"while not w.exists():\n"
                f"    if pathlib.Path(r'{OUT / 'stop'}').exists(): sys.exit(0)\n"
                f"    time.sleep(60)\n"
                f"sys.exit(subprocess.call({train!r}))\n")
        cmd = [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-c", code]
    else:
        cmd = train
    out = open(OUT / "train.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        breakaway = True
    except OSError:  # the caller's job does not allow breakaway
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    (OUT / "train.pid").write_text(str(p.pid), encoding="utf-8")
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched pid {p.pid} breakaway={breakaway} wait_for={a.wait_for}\n"
    with open(OUT / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
