"""Detached launch of run.py (no window; own process group; outside the caller's job object). Our own code.

  .venv/Scripts/python.exe -I experiments/2026-11-18-p15-24-recal-rule/launch.py
Check: Get-Content experiments/2026-11-18-p15-24-recal-rule/results/run.log -Tail 5
       (C:/Users/zhang/bci-data/derived/p15-24/DONE at the end).
Stop: kill the PID printed here and its children. Resume: launch again (finished runs are skipped; an
unfinished run is redone as a whole, about 20 min).
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DER = Path("C:/Users/zhang/bci-data/derived/p15-24")
DER.mkdir(parents=True, exist_ok=True)
py = str(REPO / ".venv/Scripts/python.exe")
flags = 0x08000000 | 0x00000200 | 0x01000000  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
with open(DER / "launcher.log", "a", encoding="utf-8") as log:
    p = subprocess.Popen([py, "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
                          py, "-I", str(REPO / "experiments/2026-11-18-p15-24-recal-rule/run.py")],
                         creationflags=flags, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         env=dict(os.environ), cwd=str(REPO), close_fds=True)
(DER / "run.pid").write_text(str(p.pid), encoding="utf-8")
print(p.pid)
