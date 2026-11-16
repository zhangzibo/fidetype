r"""Start the P11-01 cache build (prep.py features, CPU only) fully detached, with no visible window.

Same pattern as experiments/2026-11-15-m4-13-long-train/launch.py: CREATE_NO_WINDOW (hidden console),
CREATE_NEW_PROCESS_GROUP and, when Windows allows it, CREATE_BREAKAWAY_FROM_JOB. Never use
Start-Process -WindowStyle Hidden (it can open a visible terminal; closing it kills the job).

Run (repo root): .venv\Scripts\python.exe experiments\2026-11-16-p11-01-emg-decoder\launch_prep.py
Re-running resumes: sessions with a .done.json marker are skipped.
Check: Get-Content C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\prep.log -Tail 5
Pause / stop: New-Item C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\pause   (remove it before a resume)
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = Path(r"C:\Users\zhang\bci-data\raw\emg2qwerty\extracted\emg2qwerty-data-2021-08")
OUT = Path(r"C:\Users\zhang\bci-data\derived\p11-01-emg-decoder")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    py = str(ROOT / ".venv" / "Scripts" / "python.exe")
    cmd = [py, "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--label", "p11-01-prep",
           "--", py, "-I", str(HERE / "prep.py"), "features", str(DATA), str(OUT), "--workers", "4"]
    out = open(OUT / "prep.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        breakaway = True
    except OSError:  # the caller's job does not allow breakaway
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    (OUT / "prep.pid").write_text(str(p.pid), encoding="utf-8")
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched prep pid {p.pid} breakaway={breakaway}\n"
    with open(OUT / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
