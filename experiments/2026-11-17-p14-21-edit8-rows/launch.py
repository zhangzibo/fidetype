"""Detached launch of the run.py queue (no window; own process group; outside the caller's job object).

  .venv/Scripts/python.exe -I experiments/2026-11-17-p14-21-edit8-rows/launch.py
Check: C:/Users/zhang/bci-data/derived/p14-21/run.log (queue.DONE at the end).
Stop: create C:/Users/zhang/bci-data/derived/p14-21/stop (after the current stage), or kill the PID printed
here and its children. Resume: launch again (finished stages have a done/ marker and are skipped).
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DER = Path("C:/Users/zhang/bci-data/derived/p14-21")
DER.mkdir(parents=True, exist_ok=True)
py = str(REPO / ".venv/Scripts/python.exe")
flags = 0x08000000 | 0x00000200 | 0x01000000  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
with open(DER / "queue-launcher.log", "a", encoding="utf-8") as log:
    p = subprocess.Popen([py, "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
                          py, "-I", str(REPO / "experiments/2026-11-17-p14-21-edit8-rows/run.py"), "--stage", "queue"],
                         creationflags=flags, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         env=dict(os.environ), cwd=str(REPO), close_fds=True)
print(p.pid)
