"""Start the soak supervisor fully detached from the calling shell (M6-15).

The process tree is: this launcher (exits at once) -> ``python -m fidetype.utils.isolation run --class timing``
-> ``soak.py supervise``. The isolation launcher starts with DETACHED_PROCESS (no console, so no console
close or Ctrl-C event can reach it), in a new process group, and breaks away from the caller's job object
when Windows allows it. Output goes to ``<run dir>/supervisor.out``.

    python experiments/2026-11-13-m6-13-soak/launch_detached.py --run-dir C:/Users/zhang/bci-data/soak/m6-15 \
        --results-dir experiments/2026-11-13-m6-13-soak/results-full [--resume] [-- extra supervise args]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--planned-s", type=float, default=25200.0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--label", default="M6-15 soak 7 h (M6-13 harness)")
    a, extra = ap.parse_known_args()
    run, res = Path(a.run_dir), Path(a.results_dir)
    if not res.is_absolute():
        res = ROOT / res
    run.mkdir(parents=True, exist_ok=True)
    res.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SOAK_RUN_DIR=str(run), SOAK_RESULTS_DIR=str(res), PYTHONUNBUFFERED="1")
    cmd = [sys.executable, "-m", "fidetype.utils.isolation", "run", "--class", "timing", "--threads", "1",
           "--wait", "0", "--env-json", str(res / "measurement_env.json"), "--label", a.label, "--",
           sys.executable, str(HERE / "soak.py"), "supervise", "--planned-s", str(a.planned_s),
           *(["--resume"] if a.resume else []), *[x for x in extra if x != "--"]]
    out = open(run / "supervisor.out", "ab")
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    kw = dict(cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
        breakaway = os.name == "nt"
    except OSError:  # the caller's job does not allow breakaway
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} launched pid {p.pid} breakaway={breakaway} cmd={cmd}\n"
    with open(run / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
