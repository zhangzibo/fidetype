"""Start run.py fully detached and hidden (pattern: experiments/2026-11-13-m6-13-soak/launch_detached.py).

Process tree: this launcher (exits at once) -> ``python -m fidetype.utils.isolation run --class background
--threads 4`` -> ``run.py <set> arms``. CREATE_NO_WINDOW gives a hidden console that the children share, so no
window opens. Output: C:/Users/zhang/bci-data/derived/f2-e3-llm-grounding/run-<set>.out; progress also in
results/run.log.

    .venv\\Scripts\\python.exe experiments/2026-11-16-f2-e3-llm-grounding/launch_detached.py t15

Resume: run the same command again. Finished arms are skipped (results/results-<set>.json), and the base
n-best, LLM scores and rewrites come from the caches in the derived folder.
Check: tail results/run.log. Stop: find the python process whose command line has ``f2-e3`` and stop it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/f2-e3-llm-grounding")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    sets = sys.argv[1:] or ["t15"]
    OWN.mkdir(parents=True, exist_ok=True)
    py = str(ROOT / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else sys.executable
    # one isolation process per set, run in sequence by a tiny shell-free chain: run.py takes one set
    for s in sets:
        cmd = [py, "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
               py, "-I", str(HERE / "run.py"), s, "arms"]
        out = open(OWN / f"run-{s}.out", "ab")
        env = dict(os.environ, PYTHONUNBUFFERED="1")
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
        if len(sets) > 1:
            p.wait()  # sets run one after the other (the launcher then stays alive; use one set per call)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
