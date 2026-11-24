r"""Start the A1 run (a1run.py all) fully detached, with no visible window (P15-50 launcher pattern).

CREATE_NO_WINDOW + CREATE_NEW_PROCESS_GROUP and, when Windows allows it, CREATE_BREAKAWAY_FROM_JOB.

Run (repo root), only when the GPU is free:
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-24-a1-things-eeg2-image-gate\launch.py
Check:  type C:\Users\zhang\bci-data\derived\a1-things-eeg2\a1.log   (and run.out)
Stop:   create the file C:\Users\zhang\bci-data\derived\a1-things-eeg2\stop  (exits after the current epoch, code 3)
Resume: delete the stop file and run this launcher again (training resumes from latest.pt; finished stages skip).
Exit code 4 in run.out = results/gate_sub-XX.json waits for a commit + push; commit it, then launch again.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = Path(r"C:\Users\zhang\bci-data\derived\a1-things-eeg2")
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
    cmd = [str(GPU_PY), str(HERE / "a1run.py"), "all", *sys.argv[1:]]
    out = open(OUT / "run.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        breakaway = True
    except OSError:
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
