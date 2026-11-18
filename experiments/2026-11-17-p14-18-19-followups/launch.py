"""Detached launch of the run.py queue (no window; own process group; outside the caller's job object).

  .venv\\Scripts\\python.exe -I experiments/2026-11-17-p14-18-19-followups/launch.py [stage]
Check: C:/Users/zhang/bci-data/derived/p14-18-19/run.log (queue.DONE at the end).
Stop: kill the PID printed here and its children. Resume: launch again (finished parts are skipped).
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DER = Path("C:/Users/zhang/bci-data/derived/p14-18-19")
DER.mkdir(parents=True, exist_ok=True)
stage = sys.argv[1] if len(sys.argv) > 1 else "queue"
env = {k: v for k, v in os.environ.items() if k != "P1419_SMOKE"}
py = str(REPO / ".venv/Scripts/python.exe")
flags = 0x08000000 | 0x00000200 | 0x01000000  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
with open(DER / "queue-launcher.log", "a", encoding="utf-8") as log:
    p = subprocess.Popen([py, "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
                          py, "-I", str(REPO / "experiments/2026-11-17-p14-18-19-followups/run.py"), "--stage", stage],
                         creationflags=flags, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                         cwd=str(REPO), close_fds=True)
print(p.pid)
