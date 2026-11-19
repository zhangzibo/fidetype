"""Start run.py fully detached and hidden (pattern: experiments/2026-11-16-f2-e3-llm-grounding/launch_detached.py).

Process tree: this launcher (exits at once) -> ``python -m fidetype.utils.isolation run --class background
--threads 4`` -> ``run.py all``. Flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB.
run.py holds a keep-awake (SetThreadExecutionState) while it runs. CPU only; no GPU.

    .venv\\Scripts\\python.exe experiments/2026-11-19-p15-22-llm-learned/launch.py

Check: tail results/run.log, or C:/Users/zhang/bci-data/derived/p15-22/run.out; done when
C:/Users/zhang/bci-data/derived/p15-22/DONE exists.
Resume: run the same command again (finished arms are skipped: derived/p15-22/arm-<name>.json; caches persist).
Stop: stop the python process whose command line has ``p15-22-llm-learned``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p15-22")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    stages = sys.argv[1:] or ["all"]
    OWN.mkdir(parents=True, exist_ok=True)
    py = str(ROOT / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else sys.executable
    cmd = [py, "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
           py, "-I", str(HERE / "run.py"), *stages]
    out = open(OWN / "run.out", "ab")
    env = {k: v for k, v in os.environ.items() if not k.startswith("P1522_")}  # never a smoke setting
    env["PYTHONUNBUFFERED"] = "1"
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    kw = dict(cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched pid {p.pid} cmd={cmd}\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
